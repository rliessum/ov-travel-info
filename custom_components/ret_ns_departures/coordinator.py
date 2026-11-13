"""Data coordinator for RET & NS Departures."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api_disruptions import NSDisruptionsAPIClient
from .api_ns import NSAPIClient
from .api_ret import RETAPIClient
from .api_spoorkaart import NSSpoorkaartClient
from .api_virtual_train import NSVirtualTrainClient
from .const import (
    CONF_LINE_FILTER,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_MAX_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
    DISRUPTIONS_MAX_AGE,
    DOMAIN,
    MAX_DEPARTURES_LIMIT,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)

_LOGGER = logging.getLogger(__name__)


class DeparturesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching departure data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator."""
        config: dict[str, Any] = {**entry.data, **entry.options}
        self.config = config
        self.operator = config.get(CONF_OPERATOR)

        # Initialize API clients
        session = async_get_clientsession(hass)

        self.disruptions_client = None
        self.spoorkaart_client = None
        self.virtual_train_client = None

        if self.operator == STOP_TYPE_RET:
            self.api_client = RETAPIClient(session)
            self.location_id = config.get(CONF_STOP_ID)
        elif self.operator == STOP_TYPE_NS:
            api_key = config.get(CONF_NS_API_KEY, "")
            self.api_client = NSAPIClient(session, api_key)
            self.location_id = config.get(CONF_STATION_CODE)
            self.virtual_train_client = NSVirtualTrainClient(session, api_key)
            # Initialize disruptions client if monitoring is enabled
            monitor_disruptions = config.get(CONF_MONITOR_DISRUPTIONS, False)
            if monitor_disruptions:
                self.disruptions_client = NSDisruptionsAPIClient(session, api_key)
                self.spoorkaart_client = NSSpoorkaartClient(session, api_key)
        else:
            raise ValueError(f"Unknown operator: {self.operator}")

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{self.operator}_{self.location_id}",
            update_interval=update_interval or DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            max_departures = _clamped_max_departures(
                self.config.get(CONF_MAX_DEPARTURES)
            )

            if self.operator == STOP_TYPE_RET:
                line_filter = self.config.get(CONF_LINE_FILTER)
                # Convert comma-separated string to list if needed
                if isinstance(line_filter, str) and line_filter:
                    line_filter = [l.strip() for l in line_filter.split(",")]
                elif not line_filter:
                    line_filter = None

                departures = await self.api_client.async_get_departures(
                    self.location_id,
                    max_results=max_departures,
                    line_filter=line_filter,
                )
            elif self.operator == STOP_TYPE_NS:
                departures = await self.api_client.async_get_departures(
                    self.location_id,
                    max_results=max_departures,
                )
            else:
                raise UpdateFailed(f"Unknown operator: {self.operator}")

            _LOGGER.debug(
                "Fetched %d departures for %s %s",
                len(departures),
                self.operator,
                self.location_id,
            )

            result = {
                "departures": departures,
                "last_update": dt_util.utcnow(),
            }

            if self.operator == STOP_TYPE_RET and not departures:
                await self._async_attach_ret_notice(result, line_filter)

            # Fetch disruptions if monitoring is enabled for NS
            if self.disruptions_client and self.operator == STOP_TYPE_NS:
                await self._async_attach_disruptions(result)

            if self.virtual_train_client and self.operator == STOP_TYPE_NS:
                await self._async_attach_train_image(result, departures)

            return result

        except ClientResponseError as err:
            # Only 401 means a bad key. NS answers 403 for other refusals, such
            # as an exhausted quota, and an auth failure stops polling for good.
            if self.operator == STOP_TYPE_NS and err.status == 401:
                raise ConfigEntryAuthFailed("NS rejected the API key") from err
            raise UpdateFailed(f"Error fetching departures: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching departures: {err}") from err

    async def _async_attach_disruptions(self, result: dict[str, Any]) -> None:
        """Attach NS disruptions, falling back to the last known list."""
        now = dt_util.utcnow()
        try:
            disruptions = await self.disruptions_client.async_get_station_disruptions(
                self.location_id
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Error fetching disruptions: %s", err)
            # A failed fetch is not an all-clear. Keep the last known list for
            # a while, then report the state as unknown instead of guessing.
            previous = self.data or {}
            updated = previous.get("disruptions_updated")
            if updated is not None and now - updated <= DISRUPTIONS_MAX_AGE:
                result["disruptions"] = previous.get("disruptions", [])
                result["disruptions_updated"] = updated
            else:
                result["disruptions"] = []
                result["disruptions_updated"] = updated
                result["disruptions_stale"] = True
            return

        result["disruptions"] = disruptions
        result["disruptions_updated"] = now
        _LOGGER.debug(
            "Fetched %d disruptions for %s %s",
            len(disruptions),
            self.operator,
            self.location_id,
        )
        await self._async_attach_storing_geo(disruptions)

    async def _async_attach_ret_notice(
        self,
        result: dict[str, Any],
        line_filter: list[str] | None,
    ) -> None:
        """Attach RET omleidingen text when a halt has no departures."""
        try:
            notice = await self.api_client.async_get_service_notice(
                self.location_id,
                stop_name=self.config.get(CONF_STOP_NAME),
                line_filter=line_filter,
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("RET service notice unavailable: %s", err)
            return
        if notice:
            result["disruptions"] = [notice]

    async def _async_attach_train_image(
        self, result: dict[str, Any], departures: list[dict[str, Any]]
    ) -> None:
        """Attach a Virtual Train getImage result for the next service."""
        next_departure = next(
            (
                departure
                for departure in departures
                if not departure.get("cancelled") and departure.get("trip_number")
            ),
            None,
        )
        if next_departure is None or self.virtual_train_client is None:
            return

        scheduled = next_departure.get("scheduled_time")
        date = scheduled.date().isoformat() if scheduled is not None else None
        try:
            image = await self.virtual_train_client.async_get_image(
                str(next_departure["trip_number"]),
                station=self.location_id,
                date=date,
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Virtual train image unavailable: %s", err)
            return
        if not image:
            return

        result["train_image"] = image.get("bytes")
        result["train_image_content_type"] = image.get("content_type")
        result["train_image_url"] = image.get("url")
        result["train_image_updated"] = image.get("fetched_at") or dt_util.utcnow()
        if image.get("composition"):
            result["train_composition"] = image["composition"]

    async def _async_attach_storing_geo(
        self, disruptions: list[dict[str, Any]]
    ) -> None:
        """Attach Spoorkaart getStoring map data to each disruption."""
        client = self.spoorkaart_client
        if not client or client.disabled:
            return

        live_ids = {
            str(disruption["id"])
            for disruption in disruptions
            if disruption.get("id")
        }
        client.prune_cache(live_ids)

        async def _fetch(storing_id: str) -> tuple[str, dict[str, Any] | None]:
            try:
                return storing_id, await client.async_get_storing(storing_id)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.debug("Spoorkaart getStoring error for %s: %s", storing_id, err)
                return storing_id, None

        results = await asyncio.gather(*(_fetch(storing_id) for storing_id in live_ids))
        geo_by_id = {storing_id: geo for storing_id, geo in results if geo}
        for disruption in disruptions:
            storing_id = str(disruption["id"]) if disruption.get("id") else ""
            geo = geo_by_id.get(storing_id)
            if geo:
                disruption["geo"] = geo


def _clamped_max_departures(value: Any) -> int:
    """Return a stored max_departures value as an int within 1..limit."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = DEFAULT_MAX_DEPARTURES
    return min(max(number, 1), MAX_DEPARTURES_LIMIT)


RETNSConfigEntry = ConfigEntry[DeparturesCoordinator]

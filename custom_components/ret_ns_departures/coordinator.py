"""Data coordinator for RET & NS Departures."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_disruptions import NSDisruptionsAPIClient
from .api_ns import NSAPIClient
from .api_ret import RETAPIClient
from .const import (
    CONF_LINE_FILTER,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STOP_ID,
    DEFAULT_MAX_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)

_LOGGER = logging.getLogger(__name__)


class DeparturesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching departure data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.entry_id = entry_id
        self.config = config
        self.operator = config.get(CONF_OPERATOR)
        
        # Initialize API clients
        session = async_get_clientsession(hass)
        
        if self.operator == STOP_TYPE_RET:
            self.api_client = RETAPIClient(session)
            self.location_id = config.get(CONF_STOP_ID)
            self.disruptions_client = None
        elif self.operator == STOP_TYPE_NS:
            api_key = config.get(CONF_NS_API_KEY, "")
            self.api_client = NSAPIClient(session, api_key)
            self.location_id = config.get(CONF_STATION_CODE)
            # Initialize disruptions client if monitoring is enabled
            monitor_disruptions = config.get(CONF_MONITOR_DISRUPTIONS, False)
            if monitor_disruptions:
                self.disruptions_client = NSDisruptionsAPIClient(session, api_key)
            else:
                self.disruptions_client = None
        else:
            raise ValueError(f"Unknown operator: {self.operator}")
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.operator}_{self.location_id}",
            update_interval=update_interval or DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            max_departures = self.config.get(CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES)
            
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
                "last_update": self.hass.loop.time(),
            }
            
            # Fetch disruptions if monitoring is enabled for NS
            if self.disruptions_client and self.operator == STOP_TYPE_NS:
                try:
                    disruptions = await self.disruptions_client.async_get_station_disruptions(
                        self.location_id
                    )
                    result["disruptions"] = disruptions
                    _LOGGER.debug(
                        "Fetched %d disruptions for %s %s",
                        len(disruptions),
                        self.operator,
                        self.location_id,
                    )
                except Exception as err:
                    _LOGGER.warning("Error fetching disruptions: %s", err)
                    # Don't fail the entire update if disruptions fail
                    result["disruptions"] = []
            
            return result
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching departures: {err}") from err

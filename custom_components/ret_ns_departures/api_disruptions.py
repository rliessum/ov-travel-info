"""NS Disruptions API client for fetching disruption information."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    NS_DISRUPTIONS_API_BASE_URL,
    NS_DISRUPTIONS_BASE_URL,
    TIMEZONE,
)

_LOGGER = logging.getLogger(__name__)


class NSDisruptionsAPIClient:
    """Client for interacting with NS Disruptions API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the NS Disruptions API client."""
        self._session = session
        self._api_key = api_key
        self._base_url = NS_DISRUPTIONS_BASE_URL
        self._tz = ZoneInfo(TIMEZONE)

    async def async_get_disruptions(
        self,
        station_code: str | None = None,
        is_active: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Fetch disruptions.

        Args:
            station_code: Optional station code to filter disruptions
            is_active: Filter for active disruptions only

        Returns:
            List of disruption dictionaries
        """
        params: dict[str, Any] = {}
        if station_code:
            params["station"] = station_code
        if is_active:
            params["isActive"] = "true"

        _LOGGER.debug("Fetching disruptions from %s", NS_DISRUPTIONS_API_BASE_URL)

        try:
            data = await self._async_get_json(NS_DISRUPTIONS_API_BASE_URL, params)
        except ClientResponseError as err:
            if err.status == 401:
                raise
            _LOGGER.info(
                "Disruptions API v3 returned %s, falling back to Reisinformatie",
                err.status,
            )
            data = await self._async_get_json(
                f"{self._base_url}/disruptions", params
            )
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.info("Disruptions API v3 error, falling back: %s", err)
            data = await self._async_get_json(
                f"{self._base_url}/disruptions", params
            )

        items = _disruption_items(data)
        if items is None:
            _LOGGER.warning("Unexpected disruption response format: %s", type(data))
            return []
        return self._parse_disruptions(items)

    def _parse_disruptions(
        self,
        data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Parse NS Disruptions API response into disruption list."""
        disruptions = []

        for disruption_data in data:
            # Skip if not a disruption or calamity
            disruption_type = disruption_data.get("type")
            if not disruption_type:
                continue

            # Extract basic information
            disruption_id = disruption_data.get("id", "")
            is_active = disruption_data.get("isActive", False)
            title = disruption_data.get("title", "Unknown disruption")

            # Parse timestamps
            start_time = disruption_data.get("start")
            end_time = disruption_data.get("end")

            try:
                if start_time:
                    start_dt = datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    )
                    start_dt = start_dt.astimezone(self._tz)
                else:
                    start_dt = None

                if end_time:
                    end_dt = datetime.fromisoformat(
                        end_time.replace("Z", "+00:00")
                    )
                    end_dt = end_dt.astimezone(self._tz)
                else:
                    end_dt = None

            except (ValueError, AttributeError) as err:
                _LOGGER.debug("Error parsing disruption time: %s", err)
                start_dt = None
                end_dt = None

            # Extract phase and impact
            phase = disruption_data.get("phase", {})
            phase_label = phase.get("label", "") if isinstance(phase, dict) else ""

            impact = disruption_data.get("impact", {})
            impact_value = impact.get("value", 0) if isinstance(impact, dict) else 0

            # Extract affected stations from publication sections
            stations = []
            publication_sections = disruption_data.get("publicationSections", [])
            for section in publication_sections:
                section_data = section.get("section", {})
                section_stations = section_data.get("stations", [])
                for station in section_stations:
                    station_name = station.get("name", "")
                    if station_name and station_name not in stations:
                        stations.append(station_name)

            # Extract cause / situation / extra travel time from the first timespan
            cause = ""
            situation = ""
            extra_travel_time = ""
            timespans = disruption_data.get("timespans", [])
            if timespans:
                first_timespan = timespans[0]
                cause_data = first_timespan.get("cause", {})
                if isinstance(cause_data, dict):
                    cause = cause_data.get("label", "")
                situation_data = first_timespan.get("situation", {})
                if isinstance(situation_data, dict):
                    situation = situation_data.get("label", "")
                extra = first_timespan.get("additionalTravelTime")
                if isinstance(extra, dict):
                    extra_travel_time = extra.get("label") or extra.get("description") or ""

            if not extra_travel_time:
                summary = disruption_data.get("summaryAdditionalTravelTime")
                if isinstance(summary, dict):
                    extra_travel_time = (
                        summary.get("label") or summary.get("description") or ""
                    )

            # Build disruption dictionary
            disruption = {
                "id": disruption_id,
                "type": disruption_type,
                "title": title,
                "is_active": is_active,
                "start": start_dt,
                "end": end_dt,
                "phase": phase_label,
                "impact": impact_value,
                "stations": stations,
                "cause": cause,
                "situation": situation,
                "additional_travel_time": extra_travel_time,
                "description": disruption_data.get("description") or "",
                "period": disruption_data.get("period", ""),
            }

            # Add expected duration if available
            expected_duration = disruption_data.get("expectedDuration", {})
            if isinstance(expected_duration, dict):
                disruption["expected_duration"] = expected_duration.get("description", "")

            disruptions.append(disruption)

        return disruptions

    async def async_get_station_disruptions(
        self,
        station_code: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch disruptions for a specific station.

        Args:
            station_code: The station code

        Returns:
            List of disruption dictionaries
        """
        return await self.async_get_disruptions(station_code=station_code)

    def _headers(self) -> dict[str, str]:
        """Return subscription-key headers for NS APIs."""
        return {"Ocp-Apim-Subscription-Key": self._api_key}

    async def _async_get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET JSON from an NS disruptions endpoint."""
        async with asyncio.timeout(10):
            async with self._session.get(
                url, params=params, headers=self._headers()
            ) as response:
                response.raise_for_status()
                return await response.json()


def _disruption_items(data: Any) -> list[Any] | None:
    """Extract a list of disruption objects from a v3 API response."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return None
    payload = data.get("payload", data)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("disruptions")
        if isinstance(items, list):
            return items
    return None

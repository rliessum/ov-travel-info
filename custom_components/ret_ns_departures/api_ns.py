"""NS API client for fetching train departure information."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from aiohttp import ClientError, ClientSession
import pytz

from .const import NS_API_BASE_URL, OPERATOR_NS, TIMEZONE

_LOGGER = logging.getLogger(__name__)


class NSAPIClient:
    """Client for interacting with NS API for train departures."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the NS API client."""
        self._session = session
        self._api_key = api_key
        self._base_url = NS_API_BASE_URL
        self._tz = pytz.timezone(TIMEZONE)

    async def async_get_departures(
        self,
        station_code: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Fetch train departures for an NS station.

        Args:
            station_code: The station code (e.g., "Rtd" for Rotterdam Centraal)
            max_results: Maximum number of departures to return

        Returns:
            List of departure dictionaries
        """
        url = f"{self._base_url}/departures"
        params = {
            "station": station_code,
            "maxJourneys": max_results,
        }
        
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
        }
        
        _LOGGER.debug("Fetching NS departures from %s for station %s", url, station_code)

        try:
            async with asyncio.timeout(10):
                async with self._session.get(
                    url, params=params, headers=headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
            _LOGGER.debug("Received NS data: %s", str(data)[:200])
            
            return self._parse_departures(data, max_results)

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching NS departures for station %s", station_code)
            raise
        except ClientError as err:
            _LOGGER.warning(
                "Error fetching NS departures for station %s: %s", station_code, err
            )
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching NS departures: %s", err)
            raise

    def _parse_departures(
        self,
        data: dict[str, Any],
        max_results: int,
    ) -> list[dict[str, Any]]:
        """Parse NS API response into departure list."""
        departures = []
        
        payload = data.get("payload", {})
        departures_data = payload.get("departures", [])
        
        for departure_data in departures_data[:max_results]:
            # Extract departure information
            planned_datetime_str = departure_data.get("plannedDateTime")
            actual_datetime_str = departure_data.get("actualDateTime")
            
            if not planned_datetime_str:
                continue
            
            try:
                # Parse times (NS API uses ISO format)
                scheduled_dt = datetime.fromisoformat(
                    planned_datetime_str.replace("Z", "+00:00")
                )
                scheduled_dt = scheduled_dt.astimezone(self._tz)
                
                if actual_datetime_str:
                    actual_dt = datetime.fromisoformat(
                        actual_datetime_str.replace("Z", "+00:00")
                    )
                    actual_dt = actual_dt.astimezone(self._tz)
                    delay_minutes = int((actual_dt - scheduled_dt).total_seconds() / 60)
                else:
                    actual_dt = scheduled_dt
                    delay_minutes = 0
                    
            except (ValueError, AttributeError) as err:
                _LOGGER.debug("Error parsing time: %s", err)
                continue
            
            # Get route stations for destination
            route_stations = departure_data.get("routeStations", [])
            destination = route_stations[-1].get("mediumName", "Unknown") if route_stations else "Unknown"
            
            # Check for cancellation
            cancelled = departure_data.get("cancelled", False)
            
            departure = {
                "line": departure_data.get("trainCategory", ""),
                "operator": departure_data.get("product", {}).get("operatorName", OPERATOR_NS),
                "destination": destination,
                "platform": departure_data.get("actualTrack") or departure_data.get("plannedTrack", ""),
                "delay": delay_minutes if not cancelled else None,
                "scheduled_time": scheduled_dt,
                "actual_time": actual_dt if not cancelled else None,
                "train_type": departure_data.get("trainCategory", ""),
                "trip_number": departure_data.get("product", {}).get("number", ""),
                "cancelled": cancelled,
                "departure_status": departure_data.get("departureStatus", ""),
            }
            
            departures.append(departure)
        
        return departures

    async def async_validate_station(self, station_code: str) -> bool:
        """
        Validate that a station code exists.

        Args:
            station_code: The station code to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            departures = await self.async_get_departures(station_code, max_results=1)
            return True
        except ClientError as err:
            # 404 or 400 means invalid station
            if hasattr(err, 'status') and err.status in (400, 404):
                return False
            # Other errors - assume station might be valid
            return True
        except Exception:
            # Timeout or other errors - assume station might be valid
            return True

    async def async_list_stations(self) -> list[dict[str, Any]]:
        """
        List all available NS stations.

        Returns:
            List of station dictionaries with code and name
        """
        url = f"{self._base_url}/stations"
        
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
        }
        
        try:
            async with asyncio.timeout(10):
                async with self._session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
            stations = []
            payload = data.get("payload", [])
            
            for station in payload:
                stations.append({
                    "code": station.get("code"),
                    "name": station.get("namen", {}).get("lang", ""),
                    "country": station.get("land", ""),
                })
            
            return stations
            
        except Exception as err:
            _LOGGER.warning("Error fetching NS stations: %s", err)
            return []

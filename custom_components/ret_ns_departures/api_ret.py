"""RET API client for fetching departure information."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any

from aiohttp import ClientError, ClientSession
import pytz

from .const import OPERATOR_RET, OVAPI_BASE_URL, TIMEZONE

_LOGGER = logging.getLogger(__name__)


class RETAPIClient:
    """Client for interacting with OVapi for RET departures."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the RET API client."""
        self._session = session
        self._base_url = OVAPI_BASE_URL
        self._tz = pytz.timezone(TIMEZONE)

    async def async_get_departures(
        self,
        stop_id: str,
        max_results: int = 5,
        line_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch departures for a RET stop.

        Args:
            stop_id: The stop ID (e.g., "NL:Q:31000539" or just the numeric part)
            max_results: Maximum number of departures to return
            line_filter: Optional list of line numbers to filter by

        Returns:
            List of departure dictionaries
        """
        # Ensure stop_id is in the correct format for OVapi
        if not stop_id.startswith("NL:Q:"):
            stop_id = f"NL:Q:{stop_id}"

        url = f"{self._base_url}/stopareacode/{stop_id}"
        
        _LOGGER.debug("Fetching RET departures from %s", url)

        try:
            async with asyncio.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
            _LOGGER.debug("Received RET data: %s", str(data)[:200])
            
            return self._parse_departures(data, max_results, line_filter)

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching RET departures for stop %s", stop_id)
            raise
        except ClientError as err:
            _LOGGER.warning("Error fetching RET departures for stop %s: %s", stop_id, err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching RET departures: %s", err)
            raise

    def _parse_departures(
        self,
        data: dict[str, Any],
        max_results: int,
        line_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse OVapi response into departure list."""
        departures = []
        
        # OVapi structure: {stop_area_code: {stop_code: {stop_data}}}
        for stop_area_code, stop_area_data in data.items():
            if not isinstance(stop_area_data, dict):
                continue
                
            for stop_code, stop_data in stop_area_data.items():
                if not isinstance(stop_data, dict):
                    continue
                
                passes = stop_data.get("Passes", {})
                
                for pass_id, pass_data in passes.items():
                    if not isinstance(pass_data, dict):
                        continue
                    
                    # Extract departure information
                    line_public_number = pass_data.get("LinePublicNumber", "")
                    
                    # Apply line filter if specified
                    if line_filter and line_public_number not in line_filter:
                        continue
                    
                    destination = pass_data.get("DestinationName50", "Unknown")
                    
                    # Get timing information
                    target_departure_time = pass_data.get("TargetDepartureTime")
                    expected_departure_time = pass_data.get("ExpectedDepartureTime")
                    
                    if not target_departure_time:
                        continue
                    
                    # Parse times (OVapi uses ISO format strings)
                    try:
                        scheduled_dt = datetime.fromisoformat(
                            target_departure_time.replace("Z", "+00:00")
                        )
                        scheduled_dt = scheduled_dt.astimezone(self._tz)
                        
                        if expected_departure_time:
                            actual_dt = datetime.fromisoformat(
                                expected_departure_time.replace("Z", "+00:00")
                            )
                            actual_dt = actual_dt.astimezone(self._tz)
                            delay_minutes = int((actual_dt - scheduled_dt).total_seconds() / 60)
                        else:
                            actual_dt = scheduled_dt
                            delay_minutes = 0
                            
                    except (ValueError, AttributeError) as err:
                        _LOGGER.debug("Error parsing time: %s", err)
                        continue
                    
                    departure = {
                        "line": line_public_number,
                        "operator": OPERATOR_RET,
                        "destination": destination,
                        "platform": pass_data.get("TargetArrivalPlatform", ""),
                        "delay": delay_minutes,
                        "scheduled_time": scheduled_dt,
                        "actual_time": actual_dt,
                        "transport_type": pass_data.get("TransportType", ""),
                        "trip_number": pass_data.get("TripStopStatus", ""),
                    }
                    
                    departures.append(departure)
        
        # Sort by actual departure time
        departures.sort(key=lambda x: x["actual_time"])
        
        # Return only future departures, limited to max_results
        now = datetime.now(self._tz)
        future_departures = [d for d in departures if d["actual_time"] > now]
        
        return future_departures[:max_results]

    async def async_validate_stop(self, stop_id: str) -> bool:
        """
        Validate that a stop ID exists and has data.

        Args:
            stop_id: The stop ID to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            departures = await self.async_get_departures(stop_id, max_results=1)
            # Even if no departures right now, if we get a response, the stop is valid
            return True
        except ClientError:
            return False
        except Exception:
            # Timeout or other errors - assume stop might be valid
            return True

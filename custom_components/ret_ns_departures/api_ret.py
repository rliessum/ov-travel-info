"""RET API client for fetching departure information."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import re
import json
from typing import Any

from aiohttp import ClientError, ClientSession
from bs4 import BeautifulSoup
import pytz

from .const import OPERATOR_RET, RET_BASE_URL, TIMEZONE

_LOGGER = logging.getLogger(__name__)


class RETAPIClient:
    """Client for interacting with RET website for departures."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the RET API client."""
        self._session = session
        self._base_url = RET_BASE_URL
        self._tz = pytz.timezone(TIMEZONE)

    async def async_get_departures(
        self,
        stop_id: str,
        max_results: int = 5,
        line_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch departures for a RET stop by scraping the website.

        Args:
            stop_id: The stop name (e.g., "schiekade", "beurs")
            max_results: Maximum number of departures to return
            line_filter: Optional list of line numbers to filter by

        Returns:
            List of departure dictionaries
        """
        # Convert stop_id to lowercase URL format
        stop_name = stop_id.lower().replace(" ", "-")
        url = f"{self._base_url}/{stop_name}.html"
        
        _LOGGER.debug("Fetching RET departures from %s", url)

        try:
            async with asyncio.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    html_content = await response.text()
                    
            _LOGGER.debug("Received RET HTML page, parsing departures")
            
            return await self._parse_departures(
                html_content, max_results, line_filter
            )

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching RET departures for stop %s", stop_id)
            raise
        except ClientError as err:
            _LOGGER.warning("Error fetching RET departures for stop %s: %s", stop_id, err)
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error fetching RET departures: %s", err)
            raise

    async def _parse_departures(
        self,
        html_content: str,
        max_results: int,
        line_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse HTML content and extract departure information."""
        departures = []
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all departure rows
            departure_rows = soup.find_all('a', class_='modal__toggle--generated')
            
            for row in departure_rows:
                # Extract line name (e.g., "Tram 8")
                line_info = row.find('span', class_='favorite__info')
                if not line_info:
                    continue
                    
                line_text = line_info.get_text(strip=True)
                
                # Extract just the line number/letter from "Tram 8" or "Bus 33"
                line_match = re.search(r'(\d+[A-Z]?|[A-Z])$', line_text)
                line_number = line_match.group(1) if line_match else line_text
                
                # Apply line filter if specified
                if line_filter and line_number not in line_filter:
                    continue
                
                # Extract direction
                direction_div = row.find('div', class_='favorite__stop')
                destination = "Unknown"
                if direction_div:
                    direction_spans = direction_div.find_all('span', class_='favorite__info')
                    if direction_spans:
                        destination = direction_spans[-1].get_text(strip=True)
                
                # Extract departure time
                time_spans = row.find_all('span', class_='favorite__time__amount')
                if not time_spans:
                    continue
                    
                time_str = time_spans[0].get_text(strip=True)
                
                # Extract minutes until departure
                minutes_str = None
                minutes_span = row.find('span', class_='favorite__time__amount minutes')
                if minutes_span:
                    minutes_str = minutes_span.get_text(strip=True)
                
                # Parse departure time
                try:
                    # Current date with departure time
                    now = datetime.now(self._tz)
                    hour, minute = map(int, time_str.split(':'))
                    
                    scheduled_dt = now.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    
                    # If the time is in the past, assume it's for tomorrow
                    if scheduled_dt < now:
                        from datetime import timedelta
                        scheduled_dt += timedelta(days=1)
                    
                    # Calculate actual time based on minutes
                    actual_dt = scheduled_dt
                    delay_minutes = 0
                    
                    # If we have relative minutes, use that for actual time
                    if minutes_str and minutes_str.lower() != 'nu':
                        try:
                            minutes_until = int(minutes_str)
                            from datetime import timedelta
                            actual_dt = now + timedelta(minutes=minutes_until)
                            # Calculate delay
                            expected_scheduled = actual_dt.replace(
                                hour=hour, minute=minute, second=0, microsecond=0
                            )
                            if expected_scheduled < actual_dt:
                                delay_minutes = int(
                                    (actual_dt - expected_scheduled).total_seconds() / 60
                                )
                        except ValueError:
                            pass
                    
                except (ValueError, AttributeError) as err:
                    _LOGGER.debug("Error parsing time '%s': %s", time_str, err)
                    continue
                
                # Extract transport type from line text
                transport_type = "tram"
                if "Bus" in line_text:
                    transport_type = "bus"
                elif "Metro" in line_text:
                    transport_type = "metro"
                
                departure = {
                    "line": line_number,
                    "operator": OPERATOR_RET,
                    "destination": destination,
                    "platform": "",
                    "delay": delay_minutes,
                    "scheduled_time": scheduled_dt,
                    "actual_time": actual_dt,
                    "transport_type": transport_type,
                    "trip_number": "",
                }
                
                departures.append(departure)
        
        except Exception as err:
            _LOGGER.error("Error parsing RET HTML: %s", err)
            raise
        
        # Sort by actual departure time
        departures.sort(key=lambda x: x["actual_time"])
        
        # Return only future departures, limited to max_results
        now = datetime.now(self._tz)
        future_departures = [d for d in departures if d["actual_time"] > now]
        
        return future_departures[:max_results]
        future_departures = [d for d in departures if d["actual_time"] > now]
        
        return future_departures[:max_results]

    async def async_validate_stop(self, stop_id: str) -> bool:
        """
        Validate that a stop ID exists and has data.

        Args:
            stop_id: The stop name to validate (e.g., "schiekade")

        Returns:
            True if valid, False otherwise
        """
        try:
            await self.async_get_departures(stop_id, max_results=1)
            # If we get a response without error, the stop is valid
            return True
        except ClientError:
            return False
        except Exception:  # noqa: BLE001
            # Timeout or other errors - assume stop might be valid
            return True

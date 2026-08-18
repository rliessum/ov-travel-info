"""RET API client for fetching departure information."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import re
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientSession
from bs4 import BeautifulSoup

from .api_ret_diversions import (
    extract_dienstregeling_urls,
    extract_halt_lines,
    extract_halt_name,
    match_stop_notice,
    parse_diversion_articles,
)
from .const import (
    OPERATOR_RET,
    RET_BASE_URL,
    RET_DIVERSIONS_CACHE_SECONDS,
    RET_DIVERSIONS_URL,
    RET_SEARCH_CATEGORY_HALTES,
    RET_SEARCH_TYPE,
    RET_SITE_URL,
    RET_STOP_ALIASES,
    TIMEZONE,
)

_LOGGER = logging.getLogger(__name__)

_HALTE_SLUG_RE = re.compile(
    r"/home/reizen/halte/([a-z0-9-]+)\.html", re.IGNORECASE
)
_INACTIVE_NOTICE = "niet gereden"


def _normalize_stop_id(stop_id: str) -> str:
    """Turn a configured stop id into a ret.nl halt slug."""
    return stop_id.strip().lower().replace(" ", "-")


def _slug_from_halte_url(url: str) -> str | None:
    """Extract the halt slug from a ret.nl halte URL."""
    match = _HALTE_SLUG_RE.search(url)
    return match.group(1).lower() if match else None


def _is_inactive_halt(html_content: str) -> bool:
    """Return True when RET says this halt page is not in service."""
    soup = BeautifulSoup(html_content, "html.parser")
    notice = soup.select_one(".timetable__notice__content")
    if notice is None:
        return False
    return _INACTIVE_NOTICE in notice.get_text(" ", strip=True).lower()


@dataclass
class _LastHalt:
    """Cached title and serving lines from the last halt page."""

    name: str = ""
    lines: list[str] = field(default_factory=list)
    line_urls: dict[str, str] = field(default_factory=dict)


class RETAPIClient:
    """Client for interacting with RET website for departures."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the RET API client."""
        self._session = session
        self._base_url = RET_BASE_URL
        self._tz = ZoneInfo(TIMEZONE)
        self._resolved_slugs: dict[str, str] = {}
        self._last_halt = _LastHalt()
        self._diversions_cache: tuple[float, list[dict[str, Any]]] | None = None

    def resolved_stop_id(self, stop_id: str) -> str | None:
        """Return the live halt slug last resolved for ``stop_id``, if any."""
        return self._resolved_slugs.get(_normalize_stop_id(stop_id))

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
        try:
            loaded = await self._async_load_halt_page(stop_id)
            if loaded is None:
                _LOGGER.warning("No usable RET halt page for stop %s", stop_id)
                return []

            slug, html_content = loaded
            _LOGGER.debug("Received RET HTML page for %s, parsing departures", slug)
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

    async def _async_load_halt_page(self, stop_id: str) -> tuple[str, str] | None:
        """Return ``(slug, html)`` for the halt that currently has a board."""
        requested = _normalize_stop_id(stop_id)
        if requested in self._resolved_slugs:
            slug = self._resolved_slugs[requested]
            html = await self._async_fetch_halt_html(slug)
            if html is not None and not _is_inactive_halt(html):
                self._remember_halt(html)
                return slug, html
            self._resolved_slugs.pop(requested, None)

        tried: set[str] = set()
        for slug in self._candidate_slugs(requested):
            tried.add(slug)
            html = await self._async_fetch_halt_html(slug)
            if html is None or _is_inactive_halt(html):
                if html is not None:
                    _LOGGER.debug("RET halt %s is marked out of service", slug)
                continue
            self._resolved_slugs[requested] = slug
            self._remember_halt(html)
            if slug != requested:
                _LOGGER.info("RET halt %s resolved to %s", requested, slug)
            return slug, html

        for found in await self._async_search_halt_slugs(requested):
            if found in tried:
                continue
            tried.add(found)
            html = await self._async_fetch_halt_html(found)
            if html is None or _is_inactive_halt(html):
                continue
            departures = await self._parse_departures(html, max_results=1)
            if not departures:
                continue
            self._resolved_slugs[requested] = found
            self._remember_halt(html)
            _LOGGER.info("RET halt %s resolved to %s via search", requested, found)
            return found, html

        return None

    def _remember_halt(self, html: str) -> None:
        """Keep halt title and serving lines from the last successful page."""
        self._last_halt = _LastHalt(
            name=extract_halt_name(html),
            lines=extract_halt_lines(html),
            line_urls=extract_dienstregeling_urls(html),
        )

    async def async_get_service_notice(
        self,
        stop_id: str,
        stop_name: str | None = None,
        line_filter: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a RET omleiding that explains why this halt has no times."""
        slug = self.resolved_stop_id(stop_id) or _normalize_stop_id(stop_id)
        halt_name = stop_name or self._last_halt.name or slug.replace("-", " ")
        lines = line_filter or self._last_halt.lines
        notices = await self.async_get_diversions()
        return match_stop_notice(
            notices,
            stop_name=halt_name,
            stop_slug=slug,
            lines=lines,
            line_urls=self._last_halt.line_urls,
        )

    async def async_get_diversions(self) -> list[dict[str, Any]]:
        """Fetch and cache RET omleidingen / verstoringen articles."""
        now = datetime.now(self._tz).timestamp()
        if self._diversions_cache is not None:
            cached_at, notices = self._diversions_cache
            if now - cached_at < RET_DIVERSIONS_CACHE_SECONDS:
                return notices

        _LOGGER.debug("Fetching RET diversions from %s", RET_DIVERSIONS_URL)
        async with asyncio.timeout(10):
            async with self._session.get(RET_DIVERSIONS_URL) as response:
                response.raise_for_status()
                html = await response.text()
        notices = parse_diversion_articles(html)
        self._diversions_cache = (now, notices)
        return notices

    def _candidate_slugs(self, slug: str) -> list[str]:
        """Requested slug plus known replacements from the dienstregeling."""
        candidates = [slug]
        for alias in RET_STOP_ALIASES.get(slug, ()):
            if alias not in candidates:
                candidates.append(alias)
        return candidates

    async def _async_fetch_halt_html(self, slug: str) -> str | None:
        """Fetch a halt page. 404 returns None; other HTTP errors raise."""
        url = f"{self._base_url}/{slug}.html"
        _LOGGER.debug("Fetching RET departures from %s", url)
        async with asyncio.timeout(10):
            async with self._session.get(url) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                return await response.text()

    async def _async_search_halt_slugs(self, stop_id: str) -> list[str]:
        """Look up halt slugs on ret.nl (same search as the website)."""
        queries: list[str] = []
        words = stop_id.replace("-", " ").strip()
        if words:
            queries.append(words)
        parts = words.split()
        if len(parts) > 1:
            queries.append(parts[0])

        found: list[str] = []
        seen: set[str] = set()
        for query in queries:
            params = urlencode(
                {
                    "type": RET_SEARCH_TYPE,
                    "tx_retsearch_search[query]": query,
                    "tx_retsearch_search[category]": RET_SEARCH_CATEGORY_HALTES,
                }
            )
            url = f"{RET_SITE_URL}?{params}"
            try:
                async with asyncio.timeout(10):
                    async with self._session.get(url) as response:
                        response.raise_for_status()
                        payload = await response.json(content_type=None)
            except (asyncio.TimeoutError, ClientError, TypeError, ValueError) as err:
                _LOGGER.debug("RET halt search for %r failed: %s", query, err)
                continue

            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict):
                    continue
                slug = _slug_from_halte_url(str(item.get("url") or ""))
                if slug and slug not in seen:
                    seen.add(slug)
                    found.append(slug)
        return found

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

                    # A time slightly in the past is a delayed or just-missed
                    # departure; only far-past times belong to tomorrow.
                    if scheduled_dt < now - timedelta(hours=6):
                        scheduled_dt += timedelta(days=1)

                    # Calculate actual time based on minutes
                    actual_dt = scheduled_dt
                    delay_minutes = 0

                    # If we have relative minutes, use that for actual time
                    if minutes_str and minutes_str.lower() != 'nu':
                        try:
                            minutes_until = int(minutes_str)
                            actual_dt = now + timedelta(minutes=minutes_until)
                            delay_minutes = max(
                                0,
                                round(
                                    (actual_dt - scheduled_dt).total_seconds() / 60
                                ),
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

    async def async_validate_stop(self, stop_id: str) -> bool:
        """
        Validate that a stop ID exists and has data.

        Args:
            stop_id: The stop name to validate (e.g., "schiekade")

        Returns:
            True if valid, False otherwise
        """
        try:
            loaded = await self._async_load_halt_page(stop_id)
            return loaded is not None
        except ClientError:
            return False
        except Exception:  # noqa: BLE001
            # Timeout or other errors - assume stop might be valid
            return True

"""NS API client for fetching train departure information."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from math import asin, cos, radians, sin, sqrt
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    DEFAULT_STATION_RESULTS,
    MIN_STATION_QUERY_LENGTH,
    NS_API_BASE_URL,
    NS_STATIONS_API_BASE_URL,
    OPERATOR_NS,
    TIMEZONE,
)

_LOGGER = logging.getLogger(__name__)

_EARTH_RADIUS_KM = 6371.0


class NSAPIClient:
    """Client for interacting with NS API for train departures."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the NS API client."""
        self._session = session
        self._api_key = api_key
        self._base_url = NS_API_BASE_URL
        self._tz = ZoneInfo(TIMEZONE)

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

            # The API's "direction" field is the destination; fall back to the
            # last route station for older/partial payloads.
            destination = departure_data.get("direction")
            if not destination:
                route_stations = departure_data.get("routeStations", [])
                destination = (
                    route_stations[-1].get("mediumName", "Unknown")
                    if route_stations
                    else "Unknown"
                )

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
            await self.async_get_departures(station_code, max_results=1)
            return True
        except ClientError as err:
            # 404 or 400 means invalid station
            if getattr(err, "status", None) in (400, 404):
                return False
            # Other errors - assume station might be valid
            return True
        except Exception:
            # Timeout or other errors - assume station might be valid
            return True

    def _headers(self) -> dict[str, str]:
        """Return subscription-key headers for NS APIs."""
        return {"Ocp-Apim-Subscription-Key": self._api_key}

    async def _async_get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> Any:
        """GET JSON from an NS API endpoint."""
        async with asyncio.timeout(10):
            async with self._session.get(
                url, params=params, headers=self._headers()
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def async_validate_api_key(self) -> bool | None:
        """
        Check whether the subscription key is accepted by NS.

        Returns:
            True if valid, False if rejected, None if the check could not run.
        """
        url = f"{self._base_url}/stations"
        try:
            async with asyncio.timeout(10):
                async with self._session.get(url, headers=self._headers()) as response:
                    if response.status in (401, 403):
                        return False
                    response.raise_for_status()
                    return True
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Could not validate NS API key: %s", err)
            return None
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Unexpected error validating NS API key: %s", err)
            return None

    async def async_get_nearest_stations(
        self,
        lat: float,
        lng: float,
        limit: int = DEFAULT_STATION_RESULTS,
    ) -> list[dict[str, Any]]:
        """
        Find stations near a location via NS App Stations getNearestStations.

        Args:
            lat: Latitude
            lng: Longitude
            limit: Maximum number of stations to return

        Returns:
            List of station dictionaries (code, name, country, lat, lng)
        """
        url = f"{NS_STATIONS_API_BASE_URL}/nearest"
        params = {
            "lat": lat,
            "lng": lng,
            "limit": limit,
        }
        _LOGGER.debug("Fetching nearest NS stations from %s", url)
        data = await self._async_get_json(url, params)
        return parse_ns_stations(data)

    async def async_search_stations(
        self,
        query: str,
        limit: int = DEFAULT_STATION_RESULTS,
    ) -> list[dict[str, Any]]:
        """
        Search NS stations by name or code via the NS App Stations API.

        Args:
            query: Station name or code fragment
            limit: Maximum number of stations to return

        Returns:
            List of station dictionaries (code, name, country, lat, lng)
        """
        url = NS_STATIONS_API_BASE_URL
        params = {
            "q": query,
            "limit": limit,
        }
        _LOGGER.debug("Searching NS stations at %s for %s", url, query)
        data = await self._async_get_json(url, params)
        return parse_ns_stations(data)

    async def async_find_stations(
        self,
        query: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        limit: int = DEFAULT_STATION_RESULTS,
    ) -> list[dict[str, Any]]:
        """
        Resolve stations for the config flow.

        Prefers the NS App Stations API (name search or getNearestStations).
        Falls back to the Reisinformatie station list when that API is
        unavailable for the subscription key.
        """
        cleaned = (query or "").strip()
        stations: list[dict[str, Any]] = []

        try:
            if len(cleaned) >= MIN_STATION_QUERY_LENGTH:
                stations = await self.async_search_stations(cleaned, limit=limit)
            elif lat is not None and lng is not None:
                stations = await self.async_get_nearest_stations(
                    lat, lng, limit=limit
                )
        except ClientResponseError as err:
            _LOGGER.info(
                "NS App Stations API returned %s, falling back to station list",
                err.status,
            )
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.info("NS App Stations API error, falling back: %s", err)

        if stations:
            return annotate_station_distances(stations, lat, lng)[:limit]

        fallback = await self.async_list_stations()
        if cleaned:
            needle = cleaned.lower()
            fallback = [
                station
                for station in fallback
                if needle in (station.get("name") or "").lower()
                or needle in (station.get("code") or "").lower()
            ]
        fallback = annotate_station_distances(fallback, lat, lng)
        if lat is not None and lng is not None:
            fallback.sort(key=lambda station: station.get("distance_km", 1e9))
        else:
            fallback.sort(key=lambda station: (station.get("name") or "").lower())
        return fallback[:limit]

    async def async_list_stations(self) -> list[dict[str, Any]]:
        """
        List all available NS stations.

        Returns:
            List of station dictionaries with code and name
        """
        url = f"{self._base_url}/stations"

        try:
            data = await self._async_get_json(url)
            return parse_ns_stations(data)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Error fetching NS stations: %s", err)
            return []


def parse_ns_stations(data: Any) -> list[dict[str, Any]]:
    """Normalize NS station payloads (v2, v3, and Reisinformatie shapes)."""
    stations: list[dict[str, Any]] = []
    for item in _station_items(data):
        if not isinstance(item, dict):
            continue
        raw = item
        nested = item.get("station")
        if isinstance(nested, dict):
            raw = {**nested, **{k: v for k, v in item.items() if k != "station"}}

        code = _station_code(raw)
        if not code:
            continue

        lat, lng = _station_coords(raw)
        country = raw.get("land") or raw.get("country") or raw.get("countryCode") or ""
        station: dict[str, Any] = {
            "code": code,
            "name": _station_name(raw) or code,
            "country": country,
        }
        if lat is not None:
            station["lat"] = lat
        if lng is not None:
            station["lng"] = lng
        stations.append(station)
    return stations


def annotate_station_distances(
    stations: list[dict[str, Any]],
    lat: float | None,
    lng: float | None,
) -> list[dict[str, Any]]:
    """Add distance_km when both the query point and station have coordinates."""
    if lat is None or lng is None:
        return stations
    annotated: list[dict[str, Any]] = []
    for station in stations:
        station_lat = station.get("lat")
        station_lng = station.get("lng")
        if station_lat is None or station_lng is None:
            annotated.append(station)
            continue
        try:
            distance = _haversine_km(
                float(lat), float(lng), float(station_lat), float(station_lng)
            )
        except (TypeError, ValueError):
            annotated.append(station)
            continue
        updated = dict(station)
        updated["distance_km"] = distance
        annotated.append(updated)
    return annotated


def _station_items(data: Any) -> list[Any]:
    """Extract a list of station objects from an NS API response."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    payload = data.get("payload", data)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("stations", "nearestStations"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    stations = data.get("stations")
    if isinstance(stations, list):
        return stations
    return []


def _station_code(raw: dict[str, Any]) -> str | None:
    """Read a station code from v2/v3 field names."""
    ident = raw.get("id")
    if isinstance(ident, dict):
        code = ident.get("code")
        if code:
            return str(code)
    for key in ("code", "stationCode"):
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _station_name(raw: dict[str, Any]) -> str:
    """Read a display name from v2/v3 field names."""
    namen = raw.get("namen") if isinstance(raw.get("namen"), dict) else {}
    names = raw.get("names") if isinstance(raw.get("names"), dict) else {}
    return (
        namen.get("lang")
        or names.get("long")
        or raw.get("name")
        or namen.get("middel")
        or names.get("medium")
        or namen.get("kort")
        or names.get("short")
        or ""
    )


def _station_coords(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    """Read latitude/longitude from v2/v3 field names."""
    loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    lat = raw.get("lat", loc.get("lat"))
    lng = raw.get("lng", loc.get("lng", raw.get("lon", loc.get("lon"))))
    try:
        return (
            float(lat) if lat is not None else None,
            float(lng) if lng is not None else None,
        )
    except (TypeError, ValueError):
        return None, None


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    delta_lat = radians(lat2 - lat1)
    delta_lng = radians(lng2 - lng1)
    chord = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lng / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(chord))

"""NS Spoorkaart API client (getStoring)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import NS_SPOORKAART_API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class NSSpoorkaartClient:
    """Client for the NS Spoorkaart API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the Spoorkaart client."""
        self._session = session
        self._api_key = api_key
        self.disabled = False
        self._cache: dict[str, dict[str, Any] | None] = {}

    def _headers(self) -> dict[str, str]:
        """Return subscription-key headers."""
        return {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Accept": "application/json",
        }

    def prune_cache(self, live_ids: set[str]) -> None:
        """Drop cached getStoring results that are no longer active."""
        for stale_id in list(self._cache):
            if stale_id not in live_ids:
                del self._cache[stale_id]

    async def async_get_storing(self, disruption_id: str) -> dict[str, Any] | None:
        """
        Fetch GeoJSON for one disruption via getStoring.

        IDs come from the Disruptions API (getDisruptions_v3). Returns a
        compact map summary (centroid, bbox, station codes), or None when
        the id has no geometry. Results are cached per id.
        """
        if self.disabled:
            return None

        storing_id = str(disruption_id or "").strip()
        if not storing_id:
            return None
        if storing_id in self._cache:
            return self._cache[storing_id]

        url = f"{NS_SPOORKAART_API_BASE_URL}/storingen/{storing_id}"
        _LOGGER.debug("Fetching Spoorkaart getStoring %s", storing_id)

        try:
            async with asyncio.timeout(10):
                async with self._session.get(url, headers=self._headers()) as response:
                    if response.status in (400, 404):
                        self._cache[storing_id] = None
                        return None
                    response.raise_for_status()
                    data = await response.json()
        except ClientResponseError as err:
            if err.status in (401, 403):
                self.disabled = True
                _LOGGER.info(
                    "Spoorkaart getStoring not available (%s); skipping map data",
                    err.status,
                )
                return None
            raise
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Spoorkaart getStoring error for %s: %s", storing_id, err)
            raise

        parsed = parse_storing_payload(data)
        self._cache[storing_id] = parsed
        return parsed


def parse_storing_payload(data: Any) -> dict[str, Any] | None:
    """Turn a getStoring FeatureCollection into a compact map summary."""
    features = _storing_features(data)
    if not features:
        return None

    points: list[tuple[float, float]] = []
    station_codes: list[str] = []
    niveau = ""
    map_type = ""
    geometry_type = ""
    feature_id = ""

    for feature in features:
        if not feature_id:
            feature_id = str(feature.get("id") or "")
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        for code in props.get("stations") or []:
            text = str(code).strip()
            if text and text not in station_codes:
                station_codes.append(text)
        if not niveau and props.get("niveau"):
            niveau = str(props["niveau"])
        if not map_type and props.get("disruptionType"):
            map_type = str(props["disruptionType"])

        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        if not geometry_type and geometry.get("type"):
            geometry_type = str(geometry["type"])
        points.extend(_geometry_points(geometry))

    if not points:
        return {
            "id": feature_id,
            "station_codes": station_codes,
            "level": niveau,
            "map_type": map_type,
            "geometry_type": geometry_type,
            "feature_count": len(features),
        }

    lngs = [point[0] for point in points]
    lats = [point[1] for point in points]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)
    return {
        "id": feature_id,
        "latitude": (min_lat + max_lat) / 2,
        "longitude": (min_lng + max_lng) / 2,
        "bbox": [min_lng, min_lat, max_lng, max_lat],
        "station_codes": station_codes,
        "level": niveau,
        "map_type": map_type,
        "geometry_type": geometry_type,
        "feature_count": len(features),
    }


def _storing_features(data: Any) -> list[dict[str, Any]]:
    """Extract GeoJSON features from a getStoring response."""
    if not isinstance(data, dict):
        return []
    payload = data.get("payload", data)
    if isinstance(payload, dict):
        if payload.get("type") == "Feature" or "geometry" in payload:
            return [payload]
        features = payload.get("features")
        if isinstance(features, list):
            return [item for item in features if isinstance(item, dict)]
    features = data.get("features")
    if isinstance(features, list):
        return [item for item in features if isinstance(item, dict)]
    return []


def _geometry_points(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    """Collect [lng, lat] pairs from a GeoJSON geometry."""
    return _collect_lng_lat(geometry.get("coordinates"))


def _collect_lng_lat(coords: Any) -> list[tuple[float, float]]:
    """Walk nested GeoJSON coordinates and return (lng, lat) tuples."""
    if not isinstance(coords, (list, tuple)) or not coords:
        return []
    first = coords[0]
    if isinstance(first, (int, float)) and len(coords) >= 2:
        try:
            return [(float(coords[0]), float(coords[1]))]
        except (TypeError, ValueError):
            return []
    points: list[tuple[float, float]] = []
    for item in coords:
        points.extend(_collect_lng_lat(item))
    return points

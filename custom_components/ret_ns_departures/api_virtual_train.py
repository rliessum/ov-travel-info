"""NS Virtual Train API client (getImage)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    MAX_TRAIN_IMAGE_BYTES,
    NS_VIRTUAL_TRAIN_API_BASE_URL,
    TRAIN_IMAGE_REFRESH_SECONDS,
    TRAIN_IMAGE_RETRY_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class NSVirtualTrainClient:
    """Client for the NS Virtual Train API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the Virtual Train client."""
        self._session = session
        self._api_key = api_key
        self._cached: (
            tuple[tuple[str, str | None, str | None], dict[str, Any], float] | None
        ) = None
        self._failed: tuple[tuple[str, str | None, str | None], float] | None = None

    def _headers(self) -> dict[str, str]:
        """Return subscription-key headers."""
        return {"Ocp-Apim-Subscription-Key": self._api_key}

    async def async_get_image(
        self,
        rit_nummer: str,
        station: str | None = None,
        date: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Fetch the train image for a service via getImage.

        The last result is reused for the same service, so a train that is
        still the next departure costs no further requests until the result
        is TRAIN_IMAGE_REFRESH_SECONDS old. A service with no image is
        retried after TRAIN_IMAGE_RETRY_SECONDS.
        """
        rit = str(rit_nummer).strip()
        if not rit:
            return None

        key = (rit, station, date)
        previous = self._cached[1] if self._cached and self._cached[0] == key else None
        if previous is not None and monotonic() < self._cached[2]:
            return previous
        if self._failed and self._failed[0] == key and monotonic() < self._failed[1]:
            return previous

        try:
            result = await self._async_fetch_image(rit, station, date)
        except Exception:
            self._failed = (key, monotonic() + TRAIN_IMAGE_RETRY_SECONDS)
            if previous is not None:
                return previous
            raise
        if not result:
            self._failed = (key, monotonic() + TRAIN_IMAGE_RETRY_SECONDS)
            return previous
        # An unchanged picture keeps its timestamp, so the image entity does
        # not report an update that did not happen.
        unchanged = previous is not None and previous.get("bytes") == result.get("bytes")
        result["fetched_at"] = (
            previous["fetched_at"] if unchanged else datetime.now(timezone.utc)
        )
        self._cached = (key, result, monotonic() + TRAIN_IMAGE_REFRESH_SECONDS)
        return result

    async def _async_fetch_image(
        self, rit: str, station: str | None, date: str | None
    ) -> dict[str, Any] | None:
        """Try the dedicated image routes, then the train details payload."""
        params = _clean_params({"station": station, "date": date})
        candidates = [
            (f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image/{rit}", params),
            (
                f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image",
                _clean_params(
                    {"ritNummer": rit, "treinNummer": rit, "station": station, "date": date}
                ),
            ),
            (f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/{rit}/image", params),
        ]

        for url, query in candidates:
            result = await self._async_try_image_url(url, query)
            if result:
                return result

        if station:
            details_url = f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/{rit}/{station}"
            result = await self._async_try_image_url(details_url, params)
            if result:
                return result

        return None

    async def _async_try_image_url(
        self, url: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """GET a virtual-train URL and parse an image or image URL."""
        try:
            async with asyncio.timeout(10):
                async with self._session.get(
                    url, params=params or None, headers=self._headers()
                ) as response:
                    if response.status in (404, 400):
                        return None
                    response.raise_for_status()
                    content_type = (response.content_type or "").lower()
                    if content_type.startswith("image/") or "svg" in content_type:
                        body = await _async_read_capped(response)
                        if body is None:
                            return None
                        return {"bytes": body, "content_type": content_type}
                    if "json" in content_type or content_type.endswith("+json"):
                        data = await response.json()
                        parsed = image_from_virtual_train_payload(data)
                        if parsed and parsed.get("url") and not parsed.get("bytes"):
                            downloaded = await self._async_download_public_image(
                                parsed["url"]
                            )
                            if downloaded:
                                parsed.update(downloaded)
                        return parsed
        except ClientResponseError as err:
            if err.status in (401, 403):
                _LOGGER.debug("Virtual Train API not available: %s", err.status)
                raise
            _LOGGER.debug("Virtual Train request failed for %s: %s", url, err)
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Virtual Train request error for %s: %s", url, err)
        return None

    async def _async_download_public_image(self, url: str) -> dict[str, Any] | None:
        """Download a public rolling-stock image URL from a JSON payload."""
        if not url.startswith("https://"):
            return None
        try:
            async with asyncio.timeout(10):
                async with self._session.get(url) as response:
                    if response.status >= 400:
                        return None
                    content_type = (response.content_type or "").lower()
                    if not (
                        content_type.startswith("image/") or "svg" in content_type
                    ):
                        return None
                    body = await _async_read_capped(response)
                    if body is None:
                        return None
                    return {"bytes": body, "content_type": content_type, "url": url}
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Could not download train image %s: %s", url, err)
        return None


async def _async_read_capped(response: Any) -> bytes | None:
    """Read a body in chunks, or None once it exceeds the image size cap."""
    declared = response.content_length
    if isinstance(declared, int) and declared > MAX_TRAIN_IMAGE_BYTES:
        return None
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.content.iter_chunked(64 * 1024):
        total += len(chunk)
        if total > MAX_TRAIN_IMAGE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def image_from_virtual_train_payload(data: Any) -> dict[str, Any] | None:
    """Extract an image URL and composition metadata from a train payload."""
    if not isinstance(data, dict):
        if isinstance(data, list) and data and isinstance(data[0], dict):
            data = data[0]
        else:
            return None

    result: dict[str, Any] = {"composition": data}
    direct = _first_image_url(data)
    if direct:
        result["url"] = direct
        return result

    parts = data.get("materieeldelen") or data.get("materieelDelen") or []
    urls: list[str] = []
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            url = _first_image_url(part)
            if url:
                urls.append(url)
    if urls:
        result["url"] = urls[0]
        result["urls"] = urls
        return result
    return result if data else None


def _first_image_url(payload: dict[str, Any]) -> str | None:
    """Return the first http(s) image URL on a dict."""
    for key in ("url", "imageUrl", "image", "afbeelding"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            nested = value.get("url")
            if isinstance(nested, str) and nested.startswith("http"):
                return nested
    return None


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop empty query parameters."""
    return {key: value for key, value in params.items() if value}

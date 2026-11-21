"""NS Virtual Train API client (getImage)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import ipaddress
import logging
from time import monotonic
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    MAX_TRAIN_IMAGE_BYTES,
    NS_VIRTUAL_TRAIN_API_BASE_URL,
    TRAIN_IMAGE_REFRESH_SECONDS,
    TRAIN_IMAGE_RETRY_SECONDS,
)

_LOGGER = logging.getLogger(__name__)
_MAX_IMAGE_REDIRECTS = 2


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
        self._forbidden_until: float = 0.0
        self._route = 0

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
        if self._should_reuse_cached(key, previous, monotonic()):
            return previous

        try:
            result = await self._async_fetch_image(rit, station, date)
        except Exception as err:
            retry_at = monotonic() + TRAIN_IMAGE_RETRY_SECONDS
            self._failed = (key, retry_at)
            if getattr(err, "status", None) == 403:
                self._forbidden_until = retry_at
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

    def _should_reuse_cached(
        self,
        key: tuple[str, str | None, str | None],
        previous: dict[str, Any] | None,
        now: float,
    ) -> bool:
        """Return True when the cache is fresh or retries are cooling down."""
        if previous is not None and self._cached and now < self._cached[2]:
            return True
        if now < self._forbidden_until:
            return True
        return bool(self._failed and self._failed[0] == key and now < self._failed[1])

    async def _async_fetch_image(
        self, rit: str, station: str | None, date: str | None
    ) -> dict[str, Any] | None:
        """Try the dedicated image routes, then the train details payload."""
        quoted_rit = quote(rit, safe="")
        params = _clean_params({"station": station, "date": date})
        candidates = [
            (f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image/{quoted_rit}", params),
            (
                f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image",
                _clean_params(
                    {"ritNummer": rit, "treinNummer": rit, "station": station, "date": date}
                ),
            ),
            (f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/{quoted_rit}/image", params),
        ]

        if station:
            quoted_station = quote(str(station).strip(), safe="")
            candidates.append(
                (
                    f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/{quoted_rit}/{quoted_station}",
                    params,
                )
            )

        # Start with the route that answered last time, then try the others.
        order = sorted(range(len(candidates)), key=lambda index: index != self._route)
        for index in order:
            url, query = candidates[index]
            result = await self._async_try_image_url(url, query)
            if result:
                self._route = index
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
                    return await self._async_parse_image_response(response)
        except ClientResponseError as err:
            if err.status in (401, 403):
                _LOGGER.debug("Virtual Train API not available: %s", err.status)
                raise
            _LOGGER.debug("Virtual Train request failed for %s: %s", url, err)
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Virtual Train request error for %s: %s", url, err)
        return None

    async def _async_parse_image_response(
        self, response: Any
    ) -> dict[str, Any] | None:
        """Read an image directly or resolve and download a JSON image URL."""
        if response.status in (404, 400):
            return None
        response.raise_for_status()
        content_type = (response.content_type or "").lower()
        if content_type.startswith("image/") or "svg" in content_type:
            body = await _async_read_capped(response)
            return {"bytes": body, "content_type": content_type} if body is not None else None
        if "json" in content_type or content_type.endswith("+json"):
            data = await response.json()
            parsed = image_from_virtual_train_payload(data)
            if parsed and parsed.get("url"):
                downloaded = await self._async_download_public_image(parsed["url"])
                if downloaded:
                    parsed.update(downloaded)
                    return parsed
        return None

    async def _async_download_public_image(self, url: str) -> dict[str, Any] | None:
        """Download a public rolling-stock image URL from a JSON payload."""
        current_url = url
        try:
            for _ in range(_MAX_IMAGE_REDIRECTS + 1):
                if not _is_safe_image_url(current_url):
                    break
                async with asyncio.timeout(10):
                    async with self._session.get(
                        current_url, allow_redirects=False
                    ) as response:
                        if response.status in (301, 302, 303, 307, 308):
                            location = response.headers.get("Location")
                            if not location:
                                break
                            current_url = urljoin(current_url, location)
                            continue
                        return await _async_read_public_image(response, current_url)
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Could not download train image %s: %s", current_url, err)
        return None


async def _async_read_public_image(
    response: Any, url: str
) -> dict[str, Any] | None:
    """Validate status, content type, and size cap for a downloaded image."""
    if response.status >= 400:
        return None
    content_type = (response.content_type or "").lower()
    if not (content_type.startswith("image/") or "svg" in content_type):
        return None
    body = await _async_read_capped(response)
    if body is None:
        return None
    return {"bytes": body, "content_type": content_type, "url": url}


def _is_safe_image_url(url: str) -> bool:
    """Allow only public HTTPS URLs without credentials or local/private hosts."""
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost"} or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return address.is_global


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

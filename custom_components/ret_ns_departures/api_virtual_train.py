"""NS Virtual Train API client (getImage)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import NS_VIRTUAL_TRAIN_API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class NSVirtualTrainClient:
    """Client for the NS Virtual Train API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the Virtual Train client."""
        self._session = session
        self._api_key = api_key

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

        Tries the dedicated image routes first, then the train details
        payload (materieeldelen.afbeelding) as a fallback.
        """
        rit = str(rit_nummer).strip()
        if not rit:
            return None

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
                        return {
                            "bytes": await response.read(),
                            "content_type": content_type,
                        }
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
                    return {
                        "bytes": await response.read(),
                        "content_type": content_type,
                        "url": url,
                    }
        except (asyncio.TimeoutError, ClientError) as err:
            _LOGGER.debug("Could not download train image %s: %s", url, err)
        return None


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

"""Tests for the NS Virtual Train API client."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.ret_ns_departures import api_virtual_train
from custom_components.ret_ns_departures.api_virtual_train import (
    NSVirtualTrainClient,
    image_from_virtual_train_payload,
)
from custom_components.ret_ns_departures.const import (
    MAX_TRAIN_IMAGE_BYTES,
    NS_VIRTUAL_TRAIN_API_BASE_URL,
)

from tests.helpers import attach_get_with_response, mock_aiohttp_response, set_body


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def vt_client(mock_session):
    return NSVirtualTrainClient(mock_session, "test-key")


def test_image_from_payload_direct_url():
    parsed = image_from_virtual_train_payload(
        {"afbeelding": "https://example.test/train.png", "type": "VIRM"}
    )
    assert parsed is not None
    assert parsed["url"] == "https://example.test/train.png"
    assert parsed["composition"]["type"] == "VIRM"


def test_image_from_payload_materieeldelen():
    parsed = image_from_virtual_train_payload(
        {
            "ritnummer": 2834,
            "type": "ICM",
            "lengte": 6,
            "ingekort": False,
            "materieeldelen": [
                {"afbeelding": {"url": "https://example.test/car1.png"}},
                {"afbeelding": "https://example.test/car2.png"},
            ],
        }
    )
    assert parsed is not None
    assert parsed["url"] == "https://example.test/car1.png"
    assert parsed["urls"] == [
        "https://example.test/car1.png",
        "https://example.test/car2.png",
    ]


@pytest.mark.asyncio
async def test_get_image_returns_png_bytes(vt_client, mock_session):
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    set_body(response, b"\x89PNG")
    attach_get_with_response(mock_session, response)

    result = await vt_client.async_get_image("2834", station="Rtd", date="2024-11-16")

    assert result is not None
    assert result["bytes"] == b"\x89PNG"
    assert result["content_type"] == "image/png"
    called_url = mock_session.get.call_args[0][0]
    assert called_url == f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image/2834"
    assert mock_session.get.call_args[1]["params"]["station"] == "Rtd"


@pytest.mark.asyncio
async def test_get_image_falls_back_after_404(vt_client, mock_session):
    png = mock_aiohttp_response()
    png.content_type = "image/svg+xml"
    set_body(png, b"<svg/>")
    not_found = MagicMock()
    not_found.status = 404
    not_found.content_type = "application/json"
    not_found.raise_for_status = MagicMock()
    first_cm = MagicMock()
    first_cm.__aenter__ = AsyncMock(return_value=not_found)
    first_cm.__aexit__ = AsyncMock(return_value=False)
    success_cm = MagicMock()
    success_cm.__aenter__ = AsyncMock(return_value=png)
    success_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = [first_cm, success_cm]

    result = await vt_client.async_get_image("500")

    assert result is not None
    assert result["bytes"] == b"<svg/>"
    assert mock_session.get.call_count == 2
    assert mock_session.get.call_args[0][0] == (
        f"{NS_VIRTUAL_TRAIN_API_BASE_URL}/trein/image"
    )


@pytest.mark.asyncio
async def test_get_image_parses_json_and_downloads_url(vt_client, mock_session):
    json_response = mock_aiohttp_response(
        json_data={
            "type": "VIRM",
            "lengte": 4,
            "materieeldelen": [
                {"afbeelding": "https://vt.example/car.png"},
            ],
        }
    )
    json_response.content_type = "application/json"
    png = mock_aiohttp_response()
    png.status = 200
    png.content_type = "image/png"
    set_body(png, b"img")
    json_cm = MagicMock()
    json_cm.__aenter__ = AsyncMock(return_value=json_response)
    json_cm.__aexit__ = AsyncMock(return_value=False)
    png_cm = MagicMock()
    png_cm.__aenter__ = AsyncMock(return_value=png)
    png_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = [json_cm, png_cm]

    result = await vt_client.async_get_image("13960", station="WT")

    assert result is not None
    assert result["bytes"] == b"img"
    assert result["url"] == "https://vt.example/car.png"
    assert result["composition"]["type"] == "VIRM"


async def test_get_image_reuses_result_for_same_service(vt_client, mock_session):
    """The same train is fetched once, and a different train is fetched again."""
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    set_body(response, b"\x89PNG")
    attach_get_with_response(mock_session, response)

    first = await vt_client.async_get_image("2834", station="Rtd", date="2024-11-16")
    second = await vt_client.async_get_image("2834", station="Rtd", date="2024-11-16")

    assert second["bytes"] == b"\x89PNG"
    assert second["fetched_at"] == first["fetched_at"]
    assert mock_session.get.call_count == 1

    await vt_client.async_get_image("2836", station="Rtd", date="2024-11-16")
    assert mock_session.get.call_count == 2


async def test_get_image_rejects_oversized_body(vt_client, mock_session):
    """An image larger than the cap is dropped."""
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    response.content_length = MAX_TRAIN_IMAGE_BYTES + 1
    set_body(response, b"\x89PNG")
    attach_get_with_response(mock_session, response)

    assert await vt_client.async_get_image("2834", station="Rtd") is None


async def test_get_image_rejects_undeclared_oversized_body(vt_client, mock_session):
    """A body with no declared length is dropped once it passes the cap."""
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    response.content_length = None
    set_body(response, b"x" * (MAX_TRAIN_IMAGE_BYTES + 1), chunk_size=1024 * 1024)
    attach_get_with_response(mock_session, response)

    assert await vt_client.async_get_image("2834", station="Rtd") is None


async def test_get_image_refreshes_an_old_result(vt_client, mock_session, monkeypatch):
    """The same train is fetched again once the result is old enough."""
    clock = [1000.0]
    monkeypatch.setattr(api_virtual_train, "monotonic", lambda: clock[0])
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    set_body(response, b"long train")
    attach_get_with_response(mock_session, response)

    first = await vt_client.async_get_image("2834", station="Rtd")
    clock[0] += api_virtual_train.TRAIN_IMAGE_REFRESH_SECONDS + 1
    same = await vt_client.async_get_image("2834", station="Rtd")

    assert mock_session.get.call_count == 2
    assert same["fetched_at"] == first["fetched_at"]

    set_body(response, b"short train")
    clock[0] += api_virtual_train.TRAIN_IMAGE_REFRESH_SECONDS + 1
    changed = await vt_client.async_get_image("2834", station="Rtd")

    assert changed["bytes"] == b"short train"
    assert changed["fetched_at"] >= first["fetched_at"]


async def test_get_image_keeps_old_result_when_refresh_fails(
    vt_client, mock_session, monkeypatch
):
    """A failed refresh keeps showing the picture already fetched."""
    clock = [1000.0]
    monkeypatch.setattr(api_virtual_train, "monotonic", lambda: clock[0])
    response = mock_aiohttp_response()
    response.content_type = "image/png"
    set_body(response, b"train")
    attach_get_with_response(mock_session, response)
    await vt_client.async_get_image("2834", station="Rtd")

    response.status = 404
    clock[0] += api_virtual_train.TRAIN_IMAGE_REFRESH_SECONDS + 1
    result = await vt_client.async_get_image("2834", station="Rtd")

    assert result["bytes"] == b"train"


async def test_get_image_starts_with_the_route_that_worked(vt_client, mock_session):
    """After a fallback route answers, the next train tries that route first."""
    not_found = MagicMock()
    not_found.status = 404
    png = mock_aiohttp_response()
    png.content_type = "image/png"
    set_body(png, b"img")

    def _get(url, **_kwargs):
        response = png if url.endswith("/trein/image") else not_found
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=response)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    mock_session.get.side_effect = _get

    await vt_client.async_get_image("500")
    assert mock_session.get.call_count == 2

    await vt_client.async_get_image("502")
    assert mock_session.get.call_count == 3

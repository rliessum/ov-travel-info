"""Tests for the NS Virtual Train API client."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.ret_ns_departures.api_virtual_train import (
    NSVirtualTrainClient,
    image_from_virtual_train_payload,
)
from custom_components.ret_ns_departures.const import NS_VIRTUAL_TRAIN_API_BASE_URL

from tests.helpers import attach_get_with_response, mock_aiohttp_response


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
    response.read = AsyncMock(return_value=b"\x89PNG")
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
    png.read = AsyncMock(return_value=b"<svg/>")
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
    png.read = AsyncMock(return_value=b"img")
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

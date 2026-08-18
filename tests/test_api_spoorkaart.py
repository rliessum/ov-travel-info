"""Tests for the NS Spoorkaart API client (getStoring)."""
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from custom_components.ret_ns_departures.api_spoorkaart import (
    NSSpoorkaartClient,
    parse_storing_payload,
)
from custom_components.ret_ns_departures.const import NS_SPOORKAART_API_BASE_URL

from tests.helpers import attach_get_with_response, mock_aiohttp_response


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def spoorkaart_client(mock_session):
    return NSSpoorkaartClient(mock_session, "test-key")


def _feature_collection(*features):
    return {"payload": {"type": "FeatureCollection", "features": list(features)}}


def test_parse_storing_payload_computes_bbox_center():
    parsed = parse_storing_payload(
        _feature_collection(
            {
                "id": "6066934",
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [[4.0, 52.0], [4.2, 52.0], [4.2, 52.4]],
                    ],
                },
                "properties": {
                    "stations": ["HFD", "LEDN"],
                    "niveau": "MINDER_TREINEN",
                    "disruptionType": "STORING",
                },
            }
        )
    )

    assert parsed is not None
    assert parsed["id"] == "6066934"
    assert parsed["latitude"] == pytest.approx(52.2)
    assert parsed["longitude"] == pytest.approx(4.1)
    assert parsed["bbox"] == [4.0, 52.0, 4.2, 52.4]
    assert parsed["station_codes"] == ["HFD", "LEDN"]
    assert parsed["level"] == "MINDER_TREINEN"
    assert parsed["map_type"] == "STORING"
    assert parsed["geometry_type"] == "MultiLineString"
    assert parsed["feature_count"] == 1


def test_parse_storing_payload_empty_features_returns_none():
    assert parse_storing_payload(_feature_collection()) is None


def test_parse_storing_payload_accepts_bare_feature():
    parsed = parse_storing_payload(
        {
            "payload": {
                "type": "Feature",
                "id": "1",
                "geometry": {"type": "Point", "coordinates": [4.5, 52.1]},
                "properties": {"stations": ["RTD"]},
            }
        }
    )
    assert parsed is not None
    assert parsed["latitude"] == pytest.approx(52.1)
    assert parsed["longitude"] == pytest.approx(4.5)
    assert parsed["station_codes"] == ["RTD"]


@pytest.mark.asyncio
async def test_async_get_storing_success(spoorkaart_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data=_feature_collection(
                {
                    "id": "7008128",
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[4.3, 52.0], [4.7, 51.8]],
                    },
                    "properties": {
                        "stations": ["GVC", "RTD"],
                        "niveau": "MINDER_TREINEN",
                        "disruptionType": "WERKZAAMHEID",
                    },
                }
            )
        ),
    )

    result = await spoorkaart_client.async_get_storing("7008128")

    assert result is not None
    assert result["station_codes"] == ["GVC", "RTD"]
    assert result["map_type"] == "WERKZAAMHEID"
    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert args[0] == f"{NS_SPOORKAART_API_BASE_URL}/storingen/7008128"
    assert kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"


@pytest.mark.asyncio
async def test_async_get_storing_empty_id_skips_request(spoorkaart_client, mock_session):
    assert await spoorkaart_client.async_get_storing("  ") is None
    mock_session.get.assert_not_called()


@pytest.mark.asyncio
async def test_async_get_storing_404_returns_none(spoorkaart_client, mock_session):
    response = mock_aiohttp_response(json_data={})
    response.status = 404
    attach_get_with_response(mock_session, response)

    assert await spoorkaart_client.async_get_storing("missing") is None


@pytest.mark.asyncio
async def test_async_get_storing_403_disables_client(spoorkaart_client, mock_session):
    denied = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="Forbidden",
    )
    mock_session.get.side_effect = denied

    assert await spoorkaart_client.async_get_storing("6066934") is None
    assert spoorkaart_client.disabled is True
    assert await spoorkaart_client.async_get_storing("6066934") is None
    assert mock_session.get.call_count == 1


@pytest.mark.asyncio
async def test_async_get_storing_caches_result(spoorkaart_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data=_feature_collection(
                {
                    "id": "1",
                    "geometry": {"type": "Point", "coordinates": [4.5, 52.1]},
                    "properties": {},
                }
            )
        ),
    )

    first = await spoorkaart_client.async_get_storing("1")
    second = await spoorkaart_client.async_get_storing("1")

    assert first == second
    assert mock_session.get.call_count == 1
    spoorkaart_client.prune_cache(set())
    assert spoorkaart_client._cache == {}

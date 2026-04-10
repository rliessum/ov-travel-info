"""Tests for the NS disruptions API client."""
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientError

from custom_components.ret_ns_departures.api_disruptions import NSDisruptionsAPIClient

from tests.helpers import attach_get_with_response, mock_aiohttp_response


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def disruptions_client(mock_session):
    return NSDisruptionsAPIClient(mock_session, "test-key")


def test_parse_disruptions_minimal(disruptions_client):
    """Parser builds disruption dicts from API-shaped JSON."""
    raw = [
        {
            "id": "d1",
            "type": "DISRUPTION",
            "title": "Test storing",
            "isActive": True,
            "start": "2024-11-16T08:00:00Z",
            "end": "2024-11-16T12:00:00Z",
            "phase": {"label": "In progress"},
            "impact": {"value": 3},
            "publicationSections": [
                {
                    "section": {
                        "stations": [
                            {"name": "Rotterdam Centraal"},
                            {"name": "Utrecht Centraal"},
                        ]
                    }
                }
            ],
            "timespans": [{"cause": {"label": "Signalling"}}],
            "period": "morning",
            "expectedDuration": {"description": "~4h"},
        }
    ]

    parsed = disruptions_client._parse_disruptions(raw)

    assert len(parsed) == 1
    d = parsed[0]
    assert d["id"] == "d1"
    assert d["type"] == "DISRUPTION"
    assert d["title"] == "Test storing"
    assert d["is_active"] is True
    assert d["phase"] == "In progress"
    assert d["impact"] == 3
    assert d["stations"] == ["Rotterdam Centraal", "Utrecht Centraal"]
    assert d["cause"] == "Signalling"
    assert d["period"] == "morning"
    assert d["expected_duration"] == "~4h"


def test_parse_disruptions_skips_without_type(disruptions_client):
    """Entries without type are skipped."""
    raw = [{"id": "x", "title": "No type"}]
    assert disruptions_client._parse_disruptions(raw) == []


@pytest.mark.asyncio
async def test_async_get_disruptions_success(disruptions_client, mock_session):
    payload = [
        {
            "id": "1",
            "type": "MAINTENANCE",
            "title": "Work",
            "isActive": True,
            "phase": {},
            "impact": {},
            "publicationSections": [],
            "timespans": [],
        }
    ]
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=payload))

    result = await disruptions_client.async_get_disruptions(
        station_code="Rtd", is_active=True
    )

    assert len(result) == 1
    assert result[0]["id"] == "1"
    mock_session.get.assert_called_once()
    args, kwargs = mock_session.get.call_args
    assert "/disruptions" in args[0]
    assert kwargs["params"]["station"] == "Rtd"
    assert kwargs["params"]["isActive"] == "true"
    assert kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"


@pytest.mark.asyncio
async def test_async_get_disruptions_non_list_returns_empty(disruptions_client, mock_session):
    attach_get_with_response(
        mock_session, mock_aiohttp_response(json_data={"not": "a list"})
    )

    result = await disruptions_client.async_get_disruptions()

    assert result == []


@pytest.mark.asyncio
async def test_async_get_station_disruptions_delegates(disruptions_client, mock_session):
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=[]))

    await disruptions_client.async_get_station_disruptions("Ut")

    _args, kwargs = mock_session.get.call_args
    assert kwargs["params"]["station"] == "Ut"


@pytest.mark.asyncio
async def test_async_get_disruptions_propagates_client_error(disruptions_client, mock_session):
    mock_session.get.side_effect = ClientError("fail")

    with pytest.raises(ClientError):
        await disruptions_client.async_get_disruptions()

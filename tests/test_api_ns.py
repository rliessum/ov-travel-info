"""Tests for the NS API client."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError

from custom_components.ret_ns_departures.api_ns import NSAPIClient

from tests.helpers import attach_get_with_response, mock_aiohttp_response


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def ns_client(mock_session):
    return NSAPIClient(mock_session, "test_api_key")


@pytest.fixture
def mock_ns_response():
    return {
        "payload": {
            "departures": [
                {
                    "plannedDateTime": "2024-11-16T10:30:00+01:00",
                    "actualDateTime": "2024-11-16T10:32:00+01:00",
                    "trainCategory": "Intercity",
                    "routeStations": [
                        {"mediumName": "Rotterdam Centraal"},
                        {"mediumName": "Den Haag Centraal"},
                        {"mediumName": "Amsterdam Centraal"},
                    ],
                    "plannedTrack": "5",
                    "actualTrack": "5",
                    "cancelled": False,
                    "departureStatus": "INCOMING",
                    "product": {
                        "number": "2834",
                        "operatorName": "NS",
                    },
                },
                {
                    "plannedDateTime": "2024-11-16T10:35:00+01:00",
                    "actualDateTime": "2024-11-16T10:35:00+01:00",
                    "trainCategory": "Sprinter",
                    "routeStations": [
                        {"mediumName": "Rotterdam Centraal"},
                        {"mediumName": "Delft"},
                        {"mediumName": "Den Haag Centraal"},
                    ],
                    "plannedTrack": "3",
                    "actualTrack": "3",
                    "cancelled": False,
                    "departureStatus": "ON_STATION",
                    "product": {
                        "number": "5432",
                        "operatorName": "NS",
                    },
                },
            ]
        }
    }


@pytest.mark.asyncio
async def test_get_departures_success(ns_client, mock_session, mock_ns_response):
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=mock_ns_response))

    departures = await ns_client.async_get_departures("Rtd", max_results=5)

    assert len(departures) == 2
    assert departures[0]["line"] == "Intercity"
    assert departures[0]["destination"] == "Amsterdam Centraal"
    assert departures[0]["delay"] == 2
    assert departures[0]["platform"] == "5"
    assert departures[1]["line"] == "Sprinter"
    assert departures[1]["destination"] == "Den Haag Centraal"


@pytest.mark.asyncio
async def test_get_departures_with_cancellation(ns_client, mock_session):
    mock_response_data = {
        "payload": {
            "departures": [
                {
                    "plannedDateTime": "2024-11-16T10:30:00+01:00",
                    "actualDateTime": None,
                    "trainCategory": "Intercity",
                    "routeStations": [
                        {"mediumName": "Rotterdam Centraal"},
                        {"mediumName": "Amsterdam Centraal"},
                    ],
                    "plannedTrack": "5",
                    "cancelled": True,
                    "departureStatus": "CANCELLED",
                    "product": {
                        "number": "2834",
                        "operatorName": "NS",
                    },
                },
            ]
        }
    }

    attach_get_with_response(
        mock_session, mock_aiohttp_response(json_data=mock_response_data)
    )

    departures = await ns_client.async_get_departures("Rtd", max_results=5)

    assert len(departures) == 1
    assert departures[0]["cancelled"] is True
    assert departures[0]["actual_time"] is None
    assert departures[0]["delay"] is None


@pytest.mark.asyncio
async def test_get_departures_api_key_header(ns_client, mock_session, mock_ns_response):
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=mock_ns_response))

    await ns_client.async_get_departures("Rtd", max_results=5)

    mock_session.get.assert_called_once()
    call_kwargs = mock_session.get.call_args[1]
    assert "headers" in call_kwargs
    assert call_kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "test_api_key"


@pytest.mark.asyncio
async def test_get_departures_network_error(ns_client, mock_session):
    mock_session.get.side_effect = ClientError("Network error")

    with pytest.raises(ClientError):
        await ns_client.async_get_departures("Rtd")


@pytest.mark.asyncio
async def test_validate_station_success(ns_client, mock_session, mock_ns_response):
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=mock_ns_response))

    assert await ns_client.async_validate_station("Rtd") is True


@pytest.mark.asyncio
async def test_validate_station_invalid(ns_client, mock_session):
    err = ClientError("Not found")
    err.status = 404
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=err)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = cm

    assert await ns_client.async_validate_station("INVALID") is False


@pytest.mark.asyncio
async def test_list_stations(ns_client, mock_session):
    mock_response_data = {
        "payload": [
            {
                "code": "Rtd",
                "namen": {"lang": "Rotterdam Centraal"},
                "land": "NL",
            },
            {
                "code": "Asd",
                "namen": {"lang": "Amsterdam Centraal"},
                "land": "NL",
            },
        ]
    }

    attach_get_with_response(
        mock_session, mock_aiohttp_response(json_data=mock_response_data)
    )

    stations = await ns_client.async_list_stations()

    assert len(stations) == 2
    assert stations[0]["code"] == "Rtd"
    assert stations[0]["name"] == "Rotterdam Centraal"
    assert stations[1]["code"] == "Asd"


@pytest.mark.asyncio
async def test_get_departures_respects_max_results(ns_client, mock_session):
    """Parser slices to max_results."""
    deps = [
        {
            "plannedDateTime": f"2024-11-16T{10 + i:02d}:00:00+01:00",
            "actualDateTime": f"2024-11-16T{10 + i:02d}:00:00+01:00",
            "trainCategory": "Sprinter",
            "routeStations": [
                {"mediumName": "A"},
                {"mediumName": "B"},
            ],
            "plannedTrack": "1",
            "cancelled": False,
            "product": {"number": str(i), "operatorName": "NS"},
        }
        for i in range(5)
    ]
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(json_data={"payload": {"departures": deps}}),
    )

    departures = await ns_client.async_get_departures("Rtd", max_results=2)

    assert len(departures) == 2

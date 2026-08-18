"""Tests for the NS API client."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponseError

from custom_components.ret_ns_departures.api_ns import (
    NSAPIClient,
    annotate_station_distances,
    parse_ns_stations,
)
from custom_components.ret_ns_departures.const import NS_STATIONS_API_BASE_URL

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
                "lat": 51.9244,
                "lng": 4.4694,
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
    assert stations[0]["lat"] == 51.9244
    assert stations[1]["code"] == "Asd"


@pytest.mark.asyncio
async def test_get_departures_prefers_direction_field(ns_client, mock_session):
    """The API's direction field wins over the last route station."""
    payload = {
        "payload": {
            "departures": [
                {
                    "plannedDateTime": "2024-11-16T10:30:00+01:00",
                    "actualDateTime": "2024-11-16T10:30:00+01:00",
                    "direction": "Groningen",
                    "trainCategory": "Intercity",
                    "routeStations": [{"mediumName": "Zwolle"}],
                    "plannedTrack": "5",
                    "cancelled": False,
                    "product": {"number": "500", "operatorName": "NS"},
                },
            ]
        }
    }
    attach_get_with_response(mock_session, mock_aiohttp_response(json_data=payload))

    departures = await ns_client.async_get_departures("Rtd")

    assert departures[0]["destination"] == "Groningen"


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


def test_parse_ns_stations_v2_payload():
    """Reisinformatie / nsapp-stations v2 uses namen + code."""
    stations = parse_ns_stations(
        {
            "payload": [
                {
                    "code": "RTD",
                    "namen": {"lang": "Rotterdam Centraal", "middel": "Rotterdam C"},
                    "land": "NL",
                    "lat": 51.9244,
                    "lng": 4.4694,
                }
            ]
        }
    )

    assert stations == [
        {
            "code": "RTD",
            "name": "Rotterdam Centraal",
            "country": "NL",
            "lat": 51.9244,
            "lng": 4.4694,
        }
    ]


def test_parse_ns_stations_v3_payload():
    """NS App Stations v3 uses id.code, names.long, and location."""
    stations = parse_ns_stations(
        {
            "payload": [
                {
                    "id": {"code": "ASD", "uicCode": "8400058"},
                    "names": {"long": "Amsterdam Centraal", "medium": "Amsterdam C"},
                    "location": {"lat": 52.3789, "lng": 4.9003},
                    "country": "NL",
                }
            ]
        }
    )

    assert stations[0]["code"] == "ASD"
    assert stations[0]["name"] == "Amsterdam Centraal"
    assert stations[0]["lat"] == 52.3789
    assert stations[0]["lng"] == 4.9003


def test_parse_ns_stations_nested_nearest_item():
    """getNearestStations may wrap the station and attach a distance."""
    stations = parse_ns_stations(
        {
            "payload": [
                {
                    "distance": 350,
                    "station": {
                        "code": "UT",
                        "namen": {"lang": "Utrecht Centraal"},
                        "land": "NL",
                    },
                }
            ]
        }
    )

    assert stations[0]["code"] == "UT"
    assert stations[0]["name"] == "Utrecht Centraal"


def test_parse_ns_stations_skips_items_without_code():
    assert not parse_ns_stations({"payload": [{"namen": {"lang": "Nowhere"}}]})


def test_annotate_station_distances_adds_distance_km():
    stations = [
        {"code": "ASD", "name": "Amsterdam Centraal", "lat": 52.3789, "lng": 4.9003},
        {"code": "RTD", "name": "Rotterdam Centraal", "lat": 51.9244, "lng": 4.4694},
    ]
    annotated = annotate_station_distances(stations, 51.9244, 4.4694)

    assert annotated[1]["code"] == "RTD"
    assert annotated[1]["distance_km"] < 0.05
    assert annotated[0]["distance_km"] > 20


@pytest.mark.asyncio
async def test_get_nearest_stations_calls_nsapp_endpoint(ns_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data={
                "payload": [
                    {
                        "code": "RTD",
                        "namen": {"lang": "Rotterdam Centraal"},
                        "land": "NL",
                    }
                ]
            }
        ),
    )

    stations = await ns_client.async_get_nearest_stations(51.9244, 4.4694, limit=5)

    assert stations[0]["code"] == "RTD"
    mock_session.get.assert_called_once()
    called_url = mock_session.get.call_args[0][0]
    called_params = mock_session.get.call_args[1]["params"]
    assert called_url == f"{NS_STATIONS_API_BASE_URL}/nearest"
    assert called_params["lat"] == 51.9244
    assert called_params["lng"] == 4.4694
    assert called_params["limit"] == 5
    assert mock_session.get.call_args[1]["headers"]["Ocp-Apim-Subscription-Key"] == (
        "test_api_key"
    )


@pytest.mark.asyncio
async def test_search_stations_calls_nsapp_endpoint(ns_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data={
                "payload": [
                    {
                        "id": {"code": "ASD"},
                        "names": {"long": "Amsterdam Centraal"},
                        "country": "NL",
                    }
                ]
            }
        ),
    )

    stations = await ns_client.async_search_stations("Amsterdam", limit=8)

    assert stations[0]["name"] == "Amsterdam Centraal"
    called_url = mock_session.get.call_args[0][0]
    called_params = mock_session.get.call_args[1]["params"]
    assert called_url == NS_STATIONS_API_BASE_URL
    assert called_params["q"] == "Amsterdam"
    assert called_params["limit"] == 8


@pytest.mark.asyncio
async def test_find_stations_uses_search_when_query_given(ns_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data={
                "payload": [
                    {"code": "RTD", "namen": {"lang": "Rotterdam Centraal"}, "land": "NL"}
                ]
            }
        ),
    )

    stations = await ns_client.async_find_stations(
        query="Rotterdam", lat=52.0, lng=5.0
    )

    assert stations[0]["code"] == "RTD"
    assert mock_session.get.call_args[1]["params"]["q"] == "Rotterdam"


@pytest.mark.asyncio
async def test_find_stations_uses_nearest_without_query(ns_client, mock_session):
    attach_get_with_response(
        mock_session,
        mock_aiohttp_response(
            json_data={
                "payload": [
                    {"code": "UT", "namen": {"lang": "Utrecht Centraal"}, "land": "NL"}
                ]
            }
        ),
    )

    stations = await ns_client.async_find_stations(lat=52.09, lng=5.11)

    assert stations[0]["code"] == "UT"
    assert mock_session.get.call_args[0][0].endswith("/nearest")


@pytest.mark.asyncio
async def test_find_stations_falls_back_to_reisinformatie_list(ns_client, mock_session):
    """When getNearestStations is not in the subscription, use /stations."""
    nearest_error = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="Forbidden",
    )
    fallback_response = mock_aiohttp_response(
        json_data={
            "payload": [
                {
                    "code": "ASD",
                    "namen": {"lang": "Amsterdam Centraal"},
                    "land": "NL",
                    "lat": 52.3789,
                    "lng": 4.9003,
                },
                {
                    "code": "RTD",
                    "namen": {"lang": "Rotterdam Centraal"},
                    "land": "NL",
                    "lat": 51.9244,
                    "lng": 4.4694,
                },
            ]
        }
    )
    error_cm = MagicMock()
    error_cm.__aenter__ = AsyncMock(side_effect=nearest_error)
    error_cm.__aexit__ = AsyncMock(return_value=False)
    success_cm = MagicMock()
    success_cm.__aenter__ = AsyncMock(return_value=fallback_response)
    success_cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = [error_cm, success_cm]

    stations = await ns_client.async_find_stations(lat=51.9244, lng=4.4694, limit=1)

    assert stations[0]["code"] == "RTD"
    assert stations[0]["distance_km"] < 0.05


@pytest.mark.asyncio
async def test_validate_api_key_rejects_unauthorized(ns_client, mock_session):
    response = MagicMock()
    response.status = 401
    response.raise_for_status = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = cm

    assert await ns_client.async_validate_api_key() is False


@pytest.mark.asyncio
async def test_validate_api_key_accepts_ok(ns_client, mock_session):
    response = MagicMock()
    response.status = 200
    response.raise_for_status = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = cm

    assert await ns_client.async_validate_api_key() is True

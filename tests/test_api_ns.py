"""Tests for the NS API client."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientError

from custom_components.ret_ns_departures.api_ns import NSAPIClient


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return AsyncMock()


@pytest.fixture
def ns_client(mock_session):
    """Create an NS API client with mocked session."""
    return NSAPIClient(mock_session, "test_api_key")


@pytest.fixture
def mock_ns_response():
    """Create a mock NS API response."""
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
    """Test successful departure retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ns_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
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
    """Test departure retrieval with cancelled train."""
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
    
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    departures = await ns_client.async_get_departures("Rtd", max_results=5)
    
    assert len(departures) == 1
    assert departures[0]["cancelled"] is True
    assert departures[0]["actual_time"] is None
    assert departures[0]["delay"] is None


@pytest.mark.asyncio
async def test_get_departures_api_key_header(ns_client, mock_session, mock_ns_response):
    """Test that API key is included in headers."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ns_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    await ns_client.async_get_departures("Rtd", max_results=5)
    
    # Verify the API key was included in headers
    mock_session.get.assert_called_once()
    call_kwargs = mock_session.get.call_args[1]
    assert "headers" in call_kwargs
    assert call_kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "test_api_key"


@pytest.mark.asyncio
async def test_get_departures_network_error(ns_client, mock_session):
    """Test handling of network errors."""
    mock_session.get.side_effect = ClientError("Network error")
    
    with pytest.raises(ClientError):
        await ns_client.async_get_departures("Rtd")


@pytest.mark.asyncio
async def test_validate_station_success(ns_client, mock_session, mock_ns_response):
    """Test successful station validation."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ns_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    is_valid = await ns_client.async_validate_station("Rtd")
    
    assert is_valid is True


@pytest.mark.asyncio
async def test_validate_station_invalid(ns_client, mock_session):
    """Test validation of invalid station."""
    error = ClientError("Not found")
    error.status = 404
    mock_session.get.side_effect = error
    
    is_valid = await ns_client.async_validate_station("INVALID")
    
    assert is_valid is False


@pytest.mark.asyncio
async def test_list_stations(ns_client, mock_session):
    """Test listing all stations."""
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
    
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    stations = await ns_client.async_list_stations()
    
    assert len(stations) == 2
    assert stations[0]["code"] == "Rtd"
    assert stations[0]["name"] == "Rotterdam Centraal"
    assert stations[1]["code"] == "Asd"

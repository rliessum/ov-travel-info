"""Tests for the RET API client."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientError

from custom_components.ret_ns_departures.api_ret import RETAPIClient


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return AsyncMock()


@pytest.fixture
def ret_client(mock_session):
    """Create a RET API client with mocked session."""
    return RETAPIClient(mock_session)


@pytest.fixture
def mock_ovapi_response():
    """Create a mock OVapi response."""
    return {
        "NL:Q:31000539": {
            "31000539": {
                "Stop": {
                    "StopCode": "31000539",
                    "StopName": "Beurs",
                },
                "Passes": {
                    "1": {
                        "LinePublicNumber": "2",
                        "DestinationName50": "Nesselande",
                        "TargetDepartureTime": "2024-11-16T10:30:00Z",
                        "ExpectedDepartureTime": "2024-11-16T10:32:00Z",
                        "TargetArrivalPlatform": "1",
                        "TransportType": "METRO",
                        "TripStopStatus": "DRIVING",
                    },
                    "2": {
                        "LinePublicNumber": "25",
                        "DestinationName50": "Schiedam Centrum",
                        "TargetDepartureTime": "2024-11-16T10:35:00Z",
                        "ExpectedDepartureTime": "2024-11-16T10:35:00Z",
                        "TargetArrivalPlatform": "2",
                        "TransportType": "TRAM",
                        "TripStopStatus": "PLANNED",
                    },
                },
            }
        }
    }


@pytest.mark.asyncio
async def test_get_departures_success(ret_client, mock_session, mock_ovapi_response):
    """Test successful departure retrieval."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ovapi_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    departures = await ret_client.async_get_departures("31000539", max_results=5)
    
    assert len(departures) == 2
    assert departures[0]["line"] == "2"
    assert departures[0]["destination"] == "Nesselande"
    assert departures[0]["delay"] == 2
    assert departures[1]["line"] == "25"
    assert departures[1]["destination"] == "Schiedam Centrum"


@pytest.mark.asyncio
async def test_get_departures_with_line_filter(ret_client, mock_session, mock_ovapi_response):
    """Test departure retrieval with line filter."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ovapi_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    departures = await ret_client.async_get_departures(
        "31000539", max_results=5, line_filter=["2"]
    )
    
    assert len(departures) == 1
    assert departures[0]["line"] == "2"


@pytest.mark.asyncio
async def test_get_departures_with_prefix(ret_client, mock_session, mock_ovapi_response):
    """Test that stop ID is properly prefixed."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ovapi_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    await ret_client.async_get_departures("NL:Q:31000539", max_results=5)
    
    # Verify the URL was called correctly
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args[0]
    assert "NL:Q:31000539" in call_args[0]


@pytest.mark.asyncio
async def test_get_departures_network_error(ret_client, mock_session):
    """Test handling of network errors."""
    mock_session.get.side_effect = ClientError("Network error")
    
    with pytest.raises(ClientError):
        await ret_client.async_get_departures("31000539")


@pytest.mark.asyncio
async def test_validate_stop_success(ret_client, mock_session, mock_ovapi_response):
    """Test successful stop validation."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_ovapi_response)
    mock_response.raise_for_status = Mock()
    
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    is_valid = await ret_client.async_validate_stop("31000539")
    
    assert is_valid is True


@pytest.mark.asyncio
async def test_validate_stop_invalid(ret_client, mock_session):
    """Test validation of invalid stop."""
    mock_session.get.side_effect = ClientError("Not found")
    
    is_valid = await ret_client.async_validate_stop("99999999")
    
    assert is_valid is False

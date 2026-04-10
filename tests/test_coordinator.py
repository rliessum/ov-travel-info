"""Tests for DeparturesCoordinator update logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ret_ns_departures.const import (
    CONF_LINE_FILTER,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STOP_ID,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)
from custom_components.ret_ns_departures.coordinator import DeparturesCoordinator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.mark.asyncio
async def test_coordinator_ret_passes_line_filter(hass, mock_session):
    """RET updates split comma-separated line filter and fetch departures."""
    config = {
        CONF_OPERATOR: STOP_TYPE_RET,
        CONF_STOP_ID: "beurs",
        CONF_MAX_DEPARTURES: 5,
        CONF_LINE_FILTER: "2, 9",
    }
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coord = DeparturesCoordinator(hass, "entry_1", config)

    sample = [
        {
            "line": "2",
            "operator": "RET",
            "destination": "X",
            "platform": "",
            "delay": 0,
            "scheduled_time": None,
            "actual_time": None,
        }
    ]
    with patch.object(
        coord.api_client,
        "async_get_departures",
        new=AsyncMock(return_value=sample),
    ) as mock_get:
        data = await coord._async_update_data()

    mock_get.assert_awaited_once_with(
        "beurs", max_results=5, line_filter=["2", "9"]
    )
    assert data["departures"] == sample
    assert "last_update" in data
    assert "disruptions" not in data


@pytest.mark.asyncio
async def test_coordinator_ns_includes_disruptions_when_enabled(hass, mock_session):
    config = {
        CONF_OPERATOR: STOP_TYPE_NS,
        CONF_STATION_CODE: "Rtd",
        CONF_NS_API_KEY: "secret",
        CONF_MAX_DEPARTURES: 3,
        CONF_MONITOR_DISRUPTIONS: True,
    }
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coord = DeparturesCoordinator(hass, "entry_2", config)

    deps = [{"line": "IC", "destination": "Utrecht"}]
    dis = [{"id": "d1", "title": "Storm"}]

    with (
        patch.object(
            coord.api_client, "async_get_departures", new=AsyncMock(return_value=deps)
        ),
        patch.object(
            coord.disruptions_client,
            "async_get_station_disruptions",
            new=AsyncMock(return_value=dis),
        ),
    ):
        data = await coord._async_update_data()

    assert data["departures"] == deps
    assert data["disruptions"] == dis


@pytest.mark.asyncio
async def test_coordinator_ns_disruption_failure_returns_empty_list(hass, mock_session):
    config = {
        CONF_OPERATOR: STOP_TYPE_NS,
        CONF_STATION_CODE: "Rtd",
        CONF_NS_API_KEY: "secret",
        CONF_MONITOR_DISRUPTIONS: True,
    }
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coord = DeparturesCoordinator(hass, "entry_3", config)

    with (
        patch.object(
            coord.api_client,
            "async_get_departures",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            coord.disruptions_client,
            "async_get_station_disruptions",
            new=AsyncMock(side_effect=RuntimeError("API down")),
        ),
    ):
        data = await coord._async_update_data()

    assert data["departures"] == []
    assert data["disruptions"] == []


@pytest.mark.asyncio
async def test_coordinator_departures_failure_raises_update_failed(hass, mock_session):
    config = {
        CONF_OPERATOR: STOP_TYPE_RET,
        CONF_STOP_ID: "beurs",
    }
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coord = DeparturesCoordinator(hass, "entry_4", config)

    with patch.object(
        coord.api_client,
        "async_get_departures",
        new=AsyncMock(side_effect=ClientError("boom")),
    ):
        with pytest.raises(UpdateFailed, match="Error fetching departures"):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_unknown_operator_raises(hass, mock_session):
    config = {CONF_OPERATOR: "invalid"}
    with (
        patch(
            "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(ValueError, match="Unknown operator"),
    ):
        DeparturesCoordinator(hass, "entry_bad", config)

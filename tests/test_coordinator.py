"""Tests for DeparturesCoordinator update logic."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_LINE_FILTER,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)
from custom_components.ret_ns_departures.coordinator import DeparturesCoordinator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def mock_session():
    return MagicMock()


def _make_coordinator(hass, mock_session, config):
    """Build a coordinator from a config dict via a mock config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        return DeparturesCoordinator(hass, entry)


@pytest.mark.asyncio
async def test_coordinator_ret_passes_line_filter(hass, mock_session):
    """RET updates split comma-separated line filter and fetch departures."""
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_RET,
            CONF_STOP_ID: "beurs",
            CONF_MAX_DEPARTURES: 5,
            CONF_LINE_FILTER: "2, 9",
        },
    )

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
async def test_coordinator_merges_options_over_data(hass, mock_session):
    """Options take precedence over the original config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OPERATOR: STOP_TYPE_RET,
            CONF_STOP_ID: "beurs",
            CONF_MAX_DEPARTURES: 5,
        },
        options={CONF_MAX_DEPARTURES: 2},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ret_ns_departures.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coord = DeparturesCoordinator(hass, entry)

    with (
        patch.object(
            coord.api_client,
            "async_get_departures",
            new=AsyncMock(return_value=[]),
        ) as mock_get,
        patch.object(
            coord.api_client,
            "async_get_service_notice",
            new=AsyncMock(return_value=None),
        ),
    ):
        await coord._async_update_data()

    mock_get.assert_awaited_once_with("beurs", max_results=2, line_filter=None)


@pytest.mark.asyncio
async def test_coordinator_ret_attaches_service_notice_when_empty(hass, mock_session):
    """An empty RET board is explained with the matching omleiding."""
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_RET,
            CONF_STOP_ID: "schiekade",
            CONF_STOP_NAME: "Schiekade",
            CONF_LINE_FILTER: "8",
        },
    )
    notice = {
        "id": "ret-1",
        "title": "Werkzaamheden Hofplein",
        "situation": "Schiekade is vervallen",
        "url": "https://www.ret.nl/home/reizen/dienstregeling/tram-8.html",
    }
    with (
        patch.object(
            coord.api_client,
            "async_get_departures",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            coord.api_client,
            "async_get_service_notice",
            new=AsyncMock(return_value=notice),
        ) as mock_notice,
    ):
        data = await coord._async_update_data()

    mock_notice.assert_awaited_once_with(
        "schiekade", stop_name="Schiekade", line_filter=["8"]
    )
    assert data["departures"] == []
    assert data["disruptions"] == [notice]


@pytest.mark.asyncio
async def test_coordinator_ns_includes_disruptions_when_enabled(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "Rtd",
            CONF_NS_API_KEY: "secret",
            CONF_MAX_DEPARTURES: 3,
            CONF_MONITOR_DISRUPTIONS: True,
        },
    )

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
        patch.object(
            coord.spoorkaart_client,
            "async_get_storing",
            new=AsyncMock(return_value=None),
        ),
    ):
        data = await coord._async_update_data()

    assert data["departures"] == deps
    assert data["disruptions"] == dis
    assert coord.spoorkaart_client is not None


@pytest.mark.asyncio
async def test_coordinator_ns_attaches_virtual_train_image(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "Rtd",
            CONF_NS_API_KEY: "secret",
        },
    )
    deps = [
        {
            "line": "IC",
            "trip_number": "2834",
            "cancelled": False,
            "scheduled_time": None,
        }
    ]
    image = {
        "bytes": b"PNG",
        "content_type": "image/png",
        "url": "https://example.test/train.png",
        "composition": {"type": "VIRM", "lengte": 6},
    }

    with (
        patch.object(
            coord.api_client, "async_get_departures", new=AsyncMock(return_value=deps)
        ),
        patch.object(
            coord.virtual_train_client,
            "async_get_image",
            new=AsyncMock(return_value=image),
        ) as mock_image,
    ):
        data = await coord._async_update_data()

    mock_image.assert_awaited_once_with("2834", station="Rtd", date=None)
    assert data["train_image"] == b"PNG"
    assert data["train_image_url"] == "https://example.test/train.png"
    assert data["train_composition"]["type"] == "VIRM"


@pytest.mark.asyncio
async def test_coordinator_ns_disruption_failure_returns_empty_list(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "Rtd",
            CONF_NS_API_KEY: "secret",
            CONF_MONITOR_DISRUPTIONS: True,
        },
    )

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
async def test_coordinator_ns_attaches_spoorkaart_geo(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "Rtd",
            CONF_NS_API_KEY: "secret",
            CONF_MONITOR_DISRUPTIONS: True,
        },
    )
    deps = [{"line": "IC", "destination": "Utrecht"}]
    dis = [{"id": "6066934", "title": "Schiphol - Leiden"}]
    geo = {
        "id": "6066934",
        "latitude": 52.2,
        "longitude": 4.1,
        "station_codes": ["HFD", "LEDN"],
        "level": "MINDER_TREINEN",
        "map_type": "STORING",
    }

    with (
        patch.object(
            coord.api_client, "async_get_departures", new=AsyncMock(return_value=deps)
        ),
        patch.object(
            coord.disruptions_client,
            "async_get_station_disruptions",
            new=AsyncMock(return_value=dis),
        ),
        patch.object(
            coord.spoorkaart_client,
            "async_get_storing",
            new=AsyncMock(return_value=geo),
        ) as mock_storing,
    ):
        data = await coord._async_update_data()

    mock_storing.assert_awaited_once_with("6066934")
    assert data["disruptions"][0]["geo"]["station_codes"] == ["HFD", "LEDN"]
    assert data["disruptions"][0]["geo"]["latitude"] == 52.2


@pytest.mark.asyncio
async def test_coordinator_ns_spoorkaart_failure_leaves_disruption(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "Rtd",
            CONF_NS_API_KEY: "secret",
            CONF_MONITOR_DISRUPTIONS: True,
        },
    )
    dis = [{"id": "6066934", "title": "Schiphol - Leiden"}]

    with (
        patch.object(
            coord.api_client, "async_get_departures", new=AsyncMock(return_value=[])
        ),
        patch.object(
            coord.disruptions_client,
            "async_get_station_disruptions",
            new=AsyncMock(return_value=dis),
        ),
        patch.object(
            coord.spoorkaart_client,
            "async_get_storing",
            new=AsyncMock(side_effect=RuntimeError("no map")),
        ),
    ):
        data = await coord._async_update_data()

    assert data["disruptions"][0]["id"] == "6066934"
    assert "geo" not in data["disruptions"][0]


@pytest.mark.asyncio
async def test_coordinator_departures_failure_raises_update_failed(hass, mock_session):
    coord = _make_coordinator(
        hass,
        mock_session,
        {
            CONF_OPERATOR: STOP_TYPE_RET,
            CONF_STOP_ID: "beurs",
        },
    )

    with patch.object(
        coord.api_client,
        "async_get_departures",
        new=AsyncMock(side_effect=ClientError("boom")),
    ):
        with pytest.raises(UpdateFailed, match="Error fetching departures"):
            await coord._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_unknown_operator_raises(hass, mock_session):
    with pytest.raises(ValueError, match="Unknown operator"):
        _make_coordinator(hass, mock_session, {CONF_OPERATOR: "invalid"})

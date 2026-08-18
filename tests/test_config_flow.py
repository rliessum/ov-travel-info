"""Tests for the config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_LOCATION,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_STATION_QUERY,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)

ROTTERDAM = {
    "code": "RTD",
    "name": "Rotterdam Centraal",
    "country": "NL",
    "lat": 51.9244,
    "lng": 4.4694,
    "distance_km": 0.2,
}
AMSTERDAM = {
    "code": "ASD",
    "name": "Amsterdam Centraal",
    "country": "NL",
}

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_form_user_step(hass: HomeAssistant):
    """Test the user step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_form_ret_step(hass: HomeAssistant):
    """Test RET configuration step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select RET operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_RET},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ret"


@pytest.mark.asyncio
async def test_form_ret_success(hass: HomeAssistant):
    """Test successful RET configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select RET operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_RET},
    )

    # Configure RET stop with mocked validation; block real entry setup
    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.RETAPIClient.async_validate_stop",
            return_value=True,
        ),
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_ID: "beurs",
                CONF_STOP_NAME: "Beurs Metro",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "RET Beurs Metro"
    assert len(mock_setup.mock_calls) == 1
    assert result["data"][CONF_OPERATOR] == STOP_TYPE_RET
    assert result["data"][CONF_STOP_ID] == "beurs"


@pytest.mark.asyncio
async def test_form_ret_stores_resolved_slug(hass: HomeAssistant):
    """Dead RET slugs are stored as the live replacement halt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_RET},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.RETAPIClient.async_validate_stop",
            return_value=True,
        ),
        patch(
            "custom_components.ret_ns_departures.config_flow.RETAPIClient.resolved_stop_id",
            return_value="rotterdam-centraal",
        ),
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_ID: "centraal-station",
                CONF_STOP_NAME: "Rotterdam Centraal",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STOP_ID] == "rotterdam-centraal"


@pytest.mark.asyncio
async def test_form_ret_invalid_stop(hass: HomeAssistant):
    """Test RET configuration with invalid stop."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select RET operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_RET},
    )

    # Configure RET stop with invalid ID
    with patch(
        "custom_components.ret_ns_departures.config_flow.RETAPIClient.async_validate_stop",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_ID: "invalid",
                CONF_STOP_NAME: "Invalid Stop",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_STOP_ID] == "invalid_stop"


@pytest.mark.asyncio
async def test_form_ns_step(hass: HomeAssistant):
    """Test NS configuration step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select NS operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ns"


@pytest.mark.asyncio
async def test_form_ns_success(hass: HomeAssistant):
    """Test successful NS configuration via nearest-station lookup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_find_stations",
            return_value=[ROTTERDAM, AMSTERDAM],
        ),
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_station",
            return_value=True,
        ),
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
            },
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "ns_select"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION: "RTD"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "NS Rotterdam Centraal"
    assert len(mock_setup.mock_calls) == 1
    assert result["data"][CONF_OPERATOR] == STOP_TYPE_NS
    assert result["data"][CONF_STATION_CODE] == "RTD"
    assert result["data"][CONF_STATION_NAME] == "Rotterdam Centraal"
    assert result["data"][CONF_NS_API_KEY] == "test_api_key"
    assert result["options"][CONF_MONITOR_DISRUPTIONS] is True


@pytest.mark.asyncio
async def test_form_ns_search_by_name(hass: HomeAssistant):
    """Name search is passed through to the stations API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_find_stations",
            return_value=[AMSTERDAM],
        ) as mock_find,
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_station",
            return_value=True,
        ),
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_LOCATION: {"latitude": 52.37, "longitude": 4.89},
                CONF_STATION_QUERY: "Amsterdam",
            },
        )
        assert result["step_id"] == "ns_select"
        mock_find.assert_called_once()
        assert mock_find.call_args.kwargs["query"] == "Amsterdam"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION: "ASD"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STATION_CODE] == "ASD"
    assert result["data"][CONF_STATION_NAME] == "Amsterdam Centraal"


@pytest.mark.asyncio
async def test_form_ns_invalid_station(hass: HomeAssistant):
    """Test NS configuration when the selected station fails departures validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_find_stations",
            return_value=[ROTTERDAM],
        ),
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_station",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION: "RTD"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_STATION] == "invalid_station"


@pytest.mark.asyncio
async def test_form_ns_no_stations_found(hass: HomeAssistant):
    """Empty lookup with a valid key shows no_stations_found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_find_stations",
            return_value=[],
        ),
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_api_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_LOCATION: {"latitude": 0.0, "longitude": 0.0},
                CONF_STATION_QUERY: "zzzzzz",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ns"
    assert result["errors"]["base"] == "no_stations_found"


@pytest.mark.asyncio
async def test_form_ns_invalid_api_key(hass: HomeAssistant):
    """Rejected subscription key surfaces as invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_find_stations",
            return_value=[],
        ),
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_api_key",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "bad_key",
                CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


def _add_existing_ns_entry(hass: HomeAssistant, api_key: str = "saved_api_key") -> None:
    """Register an NS config entry that already has an API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ns_ASD",
        title="NS Amsterdam Centraal",
        data={
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_NS_API_KEY: api_key,
            CONF_STATION_CODE: "ASD",
            CONF_STATION_NAME: "Amsterdam Centraal",
        },
    )
    entry.add_to_hass(hass)


@pytest.mark.asyncio
async def test_form_ns_reuses_existing_api_key(hass: HomeAssistant):
    """A later NS station reuses the API key from an existing entry."""
    _add_existing_ns_entry(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ns"

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient",
        ) as mock_client_cls,
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.async_find_stations = AsyncMock(return_value=[ROTTERDAM])
        mock_client.async_validate_station = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
            },
        )
        assert result["step_id"] == "ns_select"
        assert mock_client_cls.call_args.args[1] == "saved_api_key"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION: "RTD"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NS_API_KEY] == "saved_api_key"
    assert result["data"][CONF_STATION_CODE] == "RTD"


@pytest.mark.asyncio
async def test_form_ns_optional_new_key_overrides_existing(hass: HomeAssistant):
    """A typed key wins over the stored one when adding another station."""
    _add_existing_ns_entry(hass, api_key="old_key")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    with (
        patch(
            "custom_components.ret_ns_departures.config_flow.NSAPIClient",
        ) as mock_client_cls,
        patch(
            "custom_components.ret_ns_departures.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.async_find_stations = AsyncMock(return_value=[ROTTERDAM])
        mock_client.async_validate_station = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "new_key",
                CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
            },
        )
        assert mock_client_cls.call_args.args[1] == "new_key"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_STATION: "RTD"},
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NS_API_KEY] == "new_key"


@pytest.mark.asyncio
async def test_form_ns_requires_key_when_none_stored(hass: HomeAssistant):
    """Without an existing NS entry, an empty key is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NS_API_KEY: "   ",
            CONF_LOCATION: {"latitude": 51.9244, "longitude": 4.4694},
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "ns"
    assert result["errors"][CONF_NS_API_KEY] == "api_key_required"

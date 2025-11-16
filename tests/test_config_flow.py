"""Tests for the config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.ret_ns_departures.const import (
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)


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
    
    # Configure RET stop with mocked validation
    with patch(
        "custom_components.ret_ns_departures.config_flow.RETAPIClient.async_validate_stop",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_ID: "31000539",
                CONF_STOP_NAME: "Beurs Metro",
            },
        )
    
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "RET Beurs Metro"
    assert result["data"][CONF_OPERATOR] == STOP_TYPE_RET
    assert result["data"][CONF_STOP_ID] == "31000539"


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
    """Test successful NS configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    # Select NS operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )
    
    # Configure NS station with mocked validation
    with patch(
        "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_station",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_STATION_CODE: "Rtd",
                CONF_STATION_NAME: "Rotterdam Centraal",
            },
        )
    
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "NS Rotterdam Centraal"
    assert result["data"][CONF_OPERATOR] == STOP_TYPE_NS
    assert result["data"][CONF_STATION_CODE] == "Rtd"


@pytest.mark.asyncio
async def test_form_ns_invalid_station(hass: HomeAssistant):
    """Test NS configuration with invalid station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    
    # Select NS operator
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_OPERATOR: STOP_TYPE_NS},
    )
    
    # Configure NS station with invalid code
    with patch(
        "custom_components.ret_ns_departures.config_flow.NSAPIClient.async_validate_station",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NS_API_KEY: "test_api_key",
                CONF_STATION_CODE: "INVALID",
                CONF_STATION_NAME: "Invalid Station",
            },
        )
    
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"][CONF_STATION_CODE] == "invalid_station"

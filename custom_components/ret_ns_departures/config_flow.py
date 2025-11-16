"""Config flow for RET & NS Departures integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api_ns import NSAPIClient
from .api_ret import RETAPIClient
from .const import (
    CONF_LINE_FILTER,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DEFAULT_MAX_DEPARTURES,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)

_LOGGER = logging.getLogger(__name__)

STEP_OPERATOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPERATOR): vol.In([STOP_TYPE_RET, STOP_TYPE_NS]),
    }
)


class RETNSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RET & NS Departures."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._operator: str | None = None
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose operator."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_OPERATOR_SCHEMA,
            )

        self._operator = user_input[CONF_OPERATOR]
        self._data[CONF_OPERATOR] = self._operator

        if self._operator == STOP_TYPE_RET:
            return await self.async_step_ret()
        elif self._operator == STOP_TYPE_NS:
            return await self.async_step_ns()

        return self.async_abort(reason="unknown_operator")

    async def async_step_ret(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle RET configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the stop ID
            session = async_get_clientsession(self.hass)
            client = RETAPIClient(session)
            
            stop_id = user_input[CONF_STOP_ID]
            
            try:
                is_valid = await client.async_validate_stop(stop_id)
                
                if not is_valid:
                    errors[CONF_STOP_ID] = "invalid_stop"
                else:
                    # Store the configuration
                    self._data.update(user_input)
                    
                    # Create unique ID
                    await self.async_set_unique_id(f"ret_{stop_id}")
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"RET {user_input[CONF_STOP_NAME]}",
                        data=self._data,
                    )
                    
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Error validating RET stop: %s", err)
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_STOP_ID): str,
                vol.Required(CONF_STOP_NAME): str,
                vol.Optional(CONF_LINE_FILTER): str,
            }
        )

        return self.async_show_form(
            step_id="ret",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "stop_id_example": "NL:Q:31000539 or 31000539",
                "line_filter_example": "2, 25, E",
            },
        )

    async def async_step_ns(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle NS configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the API key and station code
            session = async_get_clientsession(self.hass)
            api_key = user_input[CONF_NS_API_KEY]
            client = NSAPIClient(session, api_key)
            
            station_code = user_input[CONF_STATION_CODE]
            
            try:
                is_valid = await client.async_validate_station(station_code)
                
                if not is_valid:
                    errors[CONF_STATION_CODE] = "invalid_station"
                else:
                    # Store the configuration
                    self._data.update(user_input)
                    
                    # Create unique ID
                    await self.async_set_unique_id(f"ns_{station_code}")
                    self._abort_if_unique_id_configured()
                    
                    return self.async_create_entry(
                        title=f"NS {user_input[CONF_STATION_NAME]}",
                        data=self._data,
                    )
                    
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Error validating NS station: %s", err)
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NS_API_KEY): str,
                vol.Required(CONF_STATION_CODE): str,
                vol.Required(CONF_STATION_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="ns",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_code_example": "Rtd (Rotterdam Centraal), Asd (Amsterdam Centraal)",
                "api_key_info": "Get your free API key from https://apiportal.ns.nl",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RETNSOptionsFlow:
        """Get the options flow for this handler."""
        return RETNSOptionsFlow(config_entry)


class RETNSOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for RET & NS Departures."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        operator = self.config_entry.data.get(CONF_OPERATOR)
        
        options_schema = {
            vol.Optional(
                CONF_MAX_DEPARTURES,
                default=self.config_entry.options.get(
                    CONF_MAX_DEPARTURES, DEFAULT_MAX_DEPARTURES
                ),
            ): cv.positive_int,
        }
        
        # Add RET-specific options
        if operator == STOP_TYPE_RET:
            options_schema[
                vol.Optional(
                    CONF_LINE_FILTER,
                    default=self.config_entry.options.get(CONF_LINE_FILTER, ""),
                )
            ] = str
        
        # Add NS-specific options
        if operator == STOP_TYPE_NS:
            options_schema[
                vol.Optional(
                    CONF_MONITOR_DISRUPTIONS,
                    default=self.config_entry.options.get(CONF_MONITOR_DISRUPTIONS, False),
                )
            ] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options_schema),
        )

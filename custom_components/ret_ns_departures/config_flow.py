"""Config flow for RET & NS Departures integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api_ns import NSAPIClient
from .api_ret import RETAPIClient
from .const import (
    CONF_LINE_FILTER,
    CONF_LOCATION,
    CONF_MAX_DEPARTURES,
    CONF_MONITOR_DISRUPTIONS,
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION,
    CONF_STATION_CODE,
    CONF_STATION_NAME,
    CONF_STATION_QUERY,
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
        self._ns_stations: list[dict[str, Any]] = []

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
                    resolved = client.resolved_stop_id(stop_id) or stop_id
                    user_input[CONF_STOP_ID] = resolved
                    # Store the configuration
                    self._data.update(user_input)

                    # Create unique ID
                    await self.async_set_unique_id(f"ret_{resolved}")
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
                "stop_id_example": "beurs or rotterdam-centraal",
                "line_filter_example": "2, 8, E",
            },
        )

    async def async_step_ns(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle NS API key and station lookup."""
        errors: dict[str, str] = {}
        existing_key = self._existing_ns_api_key()

        if user_input is not None:
            api_key = (user_input.get(CONF_NS_API_KEY) or "").strip() or existing_key
            query = (user_input.get(CONF_STATION_QUERY) or "").strip()
            location = user_input.get(CONF_LOCATION) or {}
            lat = location.get("latitude")
            lng = location.get("longitude")

            if not api_key:
                errors[CONF_NS_API_KEY] = "api_key_required"
            else:
                session = async_get_clientsession(self.hass)
                client = NSAPIClient(session, api_key)

                try:
                    stations = await client.async_find_stations(
                        query=query or None,
                        lat=lat,
                        lng=lng,
                    )
                    if stations:
                        self._data[CONF_NS_API_KEY] = api_key
                        self._ns_stations = stations
                        return await self.async_step_ns_select()

                    key_status = await client.async_validate_api_key()
                    if key_status is False:
                        errors["base"] = "invalid_auth"
                    elif key_status is None:
                        errors["base"] = "cannot_connect"
                    else:
                        errors["base"] = "no_stations_found"
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.error("Error looking up NS stations: %s", err)
                    errors["base"] = "cannot_connect"

        if existing_key:
            key_field = vol.Optional(CONF_NS_API_KEY)
        else:
            key_field = vol.Required(CONF_NS_API_KEY)
        data_schema = vol.Schema(
            {
                key_field: str,
                vol.Required(
                    CONF_LOCATION, default=self._default_location()
                ): LocationSelector(LocationSelectorConfig(radius=False)),
                vol.Optional(CONF_STATION_QUERY): str,
            }
        )
        if user_input is not None:
            suggested = {
                key: value
                for key, value in user_input.items()
                if key != CONF_NS_API_KEY
            }
            data_schema = self.add_suggested_values_to_schema(data_schema, suggested)

        return self.async_show_form(
            step_id="ns",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "api_key_info": "https://apiportal.ns.nl (Ns-App product)",
            },
        )

    async def async_step_ns_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user pick a station returned by the NS Stations API."""
        errors: dict[str, str] = {}

        if not self._ns_stations:
            return await self.async_step_ns()

        if user_input is not None:
            selected_code = user_input[CONF_STATION]
            station = next(
                (
                    item
                    for item in self._ns_stations
                    if item.get("code") == selected_code
                ),
                None,
            )
            if station is None:
                errors[CONF_STATION] = "invalid_station"
            else:
                station_code = str(station["code"])
                station_name = str(station.get("name") or station_code)
                session = async_get_clientsession(self.hass)
                client = NSAPIClient(session, self._data[CONF_NS_API_KEY])
                try:
                    is_valid = await client.async_validate_station(station_code)
                    if not is_valid:
                        errors[CONF_STATION] = "invalid_station"
                    else:
                        return await self._async_create_ns_entry(
                            station_code,
                            station_name,
                            user_input.get(CONF_MONITOR_DISRUPTIONS, True),
                        )
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.error("Error validating NS station: %s", err)
                    errors["base"] = "cannot_connect"

        options = [
            SelectOptionDict(
                value=str(station["code"]),
                label=_station_option_label(station),
            )
            for station in self._ns_stations
            if station.get("code")
        ]

        return self.async_show_form(
            step_id="ns_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): SelectSelector(
                        SelectSelectorConfig(options=options, sort=False)
                    ),
                    vol.Optional(CONF_MONITOR_DISRUPTIONS, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def _async_create_ns_entry(
        self,
        station_code: str,
        station_name: str,
        monitor_disruptions: bool = True,
    ) -> FlowResult:
        """Create an NS config entry from a resolved station."""
        if self._async_ns_already_configured(station_code):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(f"ns_{station_code.upper()}")
        self._abort_if_unique_id_configured()

        self._data[CONF_STATION_CODE] = station_code
        self._data[CONF_STATION_NAME] = station_name
        return self.async_create_entry(
            title=f"NS {station_name}",
            data=self._data,
            options={CONF_MONITOR_DISRUPTIONS: monitor_disruptions},
        )

    def _async_ns_already_configured(self, station_code: str) -> bool:
        """Return True if this station is already set up (case-insensitive)."""
        wanted = station_code.upper()
        return any(
            (entry.data.get(CONF_STATION_CODE) or "").upper() == wanted
            for entry in self._async_current_entries()
        )

    def _existing_ns_api_key(self) -> str | None:
        """Return an NS API key already stored on another config entry."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_OPERATOR) != STOP_TYPE_NS:
                continue
            key = (entry.data.get(CONF_NS_API_KEY) or "").strip()
            if key:
                return key
        return None

    def _default_location(self) -> dict[str, float]:
        """Use the Home Assistant home location as the station search origin."""
        return {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> RETNSOptionsFlow:
        """Get the options flow for this handler."""
        return RETNSOptionsFlow()


class RETNSOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for RET & NS Departures."""

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


def _station_option_label(station: dict[str, Any]) -> str:
    """Build a dropdown label with code, country, and distance when known."""
    code = station.get("code", "")
    name = station.get("name") or code
    extras: list[str] = []
    country = str(station.get("country") or "").upper()
    if country and country not in ("NL", "NLD"):
        extras.append(country)
    distance_km = station.get("distance_km")
    if isinstance(distance_km, (int, float)):
        if distance_km < 1:
            extras.append(f"{int(round(distance_km * 1000))} m")
        else:
            extras.append(f"{distance_km:.1f} km")
    label = f"{name} ({code})"
    if extras:
        return f"{label} · {' · '.join(extras)}"
    return label

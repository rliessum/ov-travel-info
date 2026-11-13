"""Tests for the diagnostics download."""
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_NS_API_KEY,
    CONF_OPERATOR,
    CONF_STATION_CODE,
    DOMAIN,
    STOP_TYPE_NS,
)
from custom_components.ret_ns_departures.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_leave_out_the_key_and_the_image(hass):
    """The download shows the entry and data, but no API key or image bytes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_CODE: "RTD",
            CONF_NS_API_KEY: "super-secret",
        },
    )
    coordinator = MagicMock()
    coordinator.data = {"departures": [{"line": "IC"}], "train_image": b"12345"}
    coordinator.last_update_success = True
    coordinator.last_exception = None
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "super-secret" not in str(result)
    assert result["entry"]["data"][CONF_STATION_CODE] == "RTD"
    assert result["coordinator"]["train_image_bytes"] == 5
    assert "train_image" not in result["coordinator"]["data"]
    assert result["coordinator"]["data"]["departures"] == [{"line": "IC"}]

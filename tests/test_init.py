"""Integration lifecycle tests for __init__.py and platform setup."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_MONITOR_DISRUPTIONS,
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

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_setup_and_unload_ret_entry(hass):
    """Setting up a RET entry creates departure sensors and a service-notice binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ret_beurs",
        title="RET Beurs Metro",
        data={
            CONF_OPERATOR: STOP_TYPE_RET,
            CONF_STOP_ID: "beurs",
            CONF_STOP_NAME: "Beurs Metro",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ret_ns_departures.api_ret.RETAPIClient.async_get_departures",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.ret_ns_departures.api_ret.RETAPIClient.async_get_service_notice",
            new=AsyncMock(return_value=None),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.ret_beurs_metro_next_departure") is not None
    assert hass.states.get("sensor.ret_beurs_metro_time_to_next_departure") is not None
    assert hass.states.get("binary_sensor.ret_beurs_metro_disruptions") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_setup_ns_entry_and_remove_stale_disruption_entity_on_reload(hass):
    """Disabling monitor_disruptions removes the stale NS disruption binary sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ns_RTD",
        title="NS Rotterdam Centraal",
        data={
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_NS_API_KEY: "test-key",
            CONF_STATION_CODE: "RTD",
            CONF_STATION_NAME: "Rotterdam Centraal",
        },
        options={CONF_MONITOR_DISRUPTIONS: True},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.ret_ns_departures.api_ns.NSAPIClient.async_get_departures",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "custom_components.ret_ns_departures.api_disruptions."
            "NSDisruptionsAPIClient.async_get_station_disruptions",
            new=AsyncMock(return_value=[]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        assert (
            registry.async_get_entity_id(
                "binary_sensor", DOMAIN, f"{entry.entry_id}_disruptions"
            )
            is not None
        )
        assert (
            registry.async_get_entity_id(
                "image", DOMAIN, f"{entry.entry_id}_next_train_image"
            )
            is not None
        )

        # Updating options triggers async_reload_entry and removes the stale disruption entity.
        hass.config_entries.async_update_entry(
            entry, options={CONF_MONITOR_DISRUPTIONS: False}
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (
        registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_disruptions"
        )
        is None
    )
    assert await hass.config_entries.async_unload(entry.entry_id)

"""Tests for the NS next-train image entity."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_OPERATOR,
    CONF_STATION_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)
from custom_components.ret_ns_departures.image import (
    NextTrainImageEntity,
    async_setup_entry,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _make_coordinator(data, *, last_update_success=True):
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = last_update_success
    return coordinator


def _make_entity(hass, data, *, last_update_success=True):
    coordinator = _make_coordinator(data, last_update_success=last_update_success)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_NAME: "Rotterdam Centraal",
        },
    )
    return NextTrainImageEntity(hass, coordinator, entry, "Rotterdam Centraal")


@pytest.mark.asyncio
async def test_image_setup_entry_creates_entity_for_ns_only(hass):
    """NS entries register a NextTrainImageEntity; RET entries do not."""
    added = []
    ns_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OPERATOR: STOP_TYPE_NS,
            CONF_STATION_NAME: "Rotterdam Centraal",
        },
    )
    ns_entry.runtime_data = _make_coordinator({})
    await async_setup_entry(hass, ns_entry, added.extend)
    assert len(added) == 1
    assert isinstance(added[0], NextTrainImageEntity)

    ret_added = []
    ret_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_OPERATOR: STOP_TYPE_RET},
    )
    ret_entry.runtime_data = _make_coordinator({})
    await async_setup_entry(hass, ret_entry, ret_added.extend)
    assert not ret_added


@pytest.mark.asyncio
async def test_image_entity_returns_bytes_and_metadata(hass):
    """Image entity exposes fetched bytes, content type, timestamp, and composition."""
    updated = datetime(2024, 11, 16, 12, 0, tzinfo=timezone.utc)
    entity = _make_entity(
        hass,
        {
            "train_image": b"\x89PNG",
            "train_image_content_type": "image/png",
            "train_image_url": "https://cdn.ns.nl/virm.png",
            "train_image_updated": updated,
            "train_composition": {
                "type": "VIRM",
                "lengte": 6,
                "ingekort": False,
            },
        },
    )

    assert entity.available is True
    assert await entity.async_image() == b"\x89PNG"
    assert entity.content_type == "image/png"
    assert entity.image_last_updated == updated
    assert entity.extra_state_attributes == {
        "rolling_stock": "VIRM",
        "train_length": 6,
        "shortened": False,
        "image_url": "https://cdn.ns.nl/virm.png",
    }


@pytest.mark.asyncio
async def test_image_entity_unavailable_when_missing_or_coordinator_failed(hass):
    """Availability tracks both fetched image bytes and coordinator health."""
    empty_entity = _make_entity(hass, {})
    assert empty_entity.available is False
    assert await empty_entity.async_image() is None

    failed_entity = _make_entity(
        hass,
        {"train_image": b"\x89PNG"},
        last_update_success=False,
    )
    assert failed_entity.available is False


def test_image_entity_syncs_timestamp_and_content_type_on_coordinator_update(hass):
    """Coordinator updates refresh image_last_updated and content_type."""
    entity = _make_entity(hass, {})
    entity.async_write_ha_state = MagicMock()

    updated = datetime(2024, 11, 16, 12, 5, tzinfo=timezone.utc)
    entity.coordinator.data = {
        "train_image": b"<svg/>",
        "train_image_content_type": "image/svg+xml",
        "train_image_updated": updated,
    }
    entity._handle_coordinator_update()

    assert entity.image_last_updated == updated
    assert entity.content_type == "image/svg+xml"
    entity.async_write_ha_state.assert_called_once()

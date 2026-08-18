"""Image platform for the next NS train (Virtual Train getImage)."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_OPERATOR, CONF_STATION_NAME, DOMAIN, STOP_TYPE_NS
from .coordinator import DeparturesCoordinator, RETNSConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RETNSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the next-train image entity for NS stations."""
    if config_entry.data.get(CONF_OPERATOR) != STOP_TYPE_NS:
        return

    coordinator = config_entry.runtime_data
    location_name = config_entry.data.get(CONF_STATION_NAME, "Unknown Station")
    async_add_entities(
        [NextTrainImageEntity(hass, coordinator, config_entry, location_name)]
    )


class NextTrainImageEntity(
    CoordinatorEntity[DeparturesCoordinator], ImageEntity
):
    """Image of the next departing train from the Virtual Train API."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_train_image"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DeparturesCoordinator,
        config_entry: RETNSConfigEntry,
        location_name: str,
    ) -> None:
        """Initialize the next-train image."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._config_entry = config_entry
        self._location_name = location_name
        self._attr_unique_id = f"{config_entry.entry_id}_next_train_image"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"NS {location_name}",
            manufacturer="NS",
            model="NS Departure Monitor",
        )
        self._sync_image_timestamp()

    @property
    def available(self) -> bool:
        """Return True when a train image was fetched."""
        return bool(self.coordinator.data and self.coordinator.data.get("train_image"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose composition metadata when the Virtual Train API provided it."""
        data = self.coordinator.data or {}
        composition = data.get("train_composition") or {}
        attributes: dict[str, Any] = {}
        if composition.get("type"):
            attributes["rolling_stock"] = composition["type"]
        if composition.get("lengte") is not None:
            attributes["train_length"] = composition["lengte"]
        if composition.get("ingekort") is not None:
            attributes["shortened"] = composition["ingekort"]
        if data.get("train_image_url"):
            attributes["image_url"] = data["train_image_url"]
        return attributes

    async def async_image(self) -> bytes | None:
        """Return image bytes from the last Virtual Train getImage call."""
        if not self.coordinator.data:
            return None
        image = self.coordinator.data.get("train_image")
        return image if isinstance(image, (bytes, bytearray)) else None

    async def async_added_to_hass(self) -> None:
        """Handle added to Home Assistant."""
        await super().async_added_to_hass()
        self._sync_image_timestamp()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update cached image timestamp so the frontend refreshes."""
        self._sync_image_timestamp()
        super()._handle_coordinator_update()

    def _sync_image_timestamp(self) -> None:
        """Copy the coordinator image timestamp onto the entity."""
        updated = None
        if self.coordinator.data:
            updated = self.coordinator.data.get("train_image_updated")
        if isinstance(updated, datetime):
            self._attr_image_last_updated = updated
        content_type = None
        if self.coordinator.data:
            content_type = self.coordinator.data.get("train_image_content_type")
        if content_type:
            self._attr_content_type = content_type

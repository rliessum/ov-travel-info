"""Binary sensor platform for NS Disruptions."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DISRUPTION_CAUSE,
    ATTR_DISRUPTION_END,
    ATTR_DISRUPTION_ID,
    ATTR_DISRUPTION_IMPACT,
    ATTR_DISRUPTION_PHASE,
    ATTR_DISRUPTION_START,
    ATTR_DISRUPTION_STATIONS,
    ATTR_DISRUPTION_TITLE,
    ATTR_DISRUPTION_TYPE,
    ATTR_DISRUPTIONS,
    CONF_MONITOR_DISRUPTIONS,
    CONF_OPERATOR,
    CONF_STATION_NAME,
    DOMAIN,
    STOP_TYPE_NS,
)
from .coordinator import DeparturesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NS Disruption binary sensors."""
    coordinator: DeparturesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    operator = config_entry.data.get(CONF_OPERATOR)
    monitor_disruptions = config_entry.options.get(CONF_MONITOR_DISRUPTIONS, False)
    
    # Only create disruption sensor for NS stations when monitoring is enabled
    if operator == STOP_TYPE_NS and monitor_disruptions:
        location_name = config_entry.data.get(CONF_STATION_NAME, "Unknown Station")
        
        entities = [
            StationDisruptionSensor(coordinator, config_entry, location_name),
        ]
        
        async_add_entities(entities)


class StationDisruptionSensor(CoordinatorEntity[DeparturesCoordinator], BinarySensorEntity):
    """Binary sensor for station disruptions."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: DeparturesCoordinator,
        config_entry: ConfigEntry,
        location_name: str,
    ) -> None:
        """Initialize the disruption sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._location_name = location_name
        self._attr_has_entity_name = True
        
        location_id = coordinator.location_id
        
        # Create unique ID
        self._attr_unique_id = f"{config_entry.entry_id}_disruptions"
        
        # Use same device info as departure sensors for grouping
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"NS {location_name}",
            "manufacturer": "NS",
            "model": "NS Departure Monitor",
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Disruptions"

    @property
    def native_value(self) -> bool:
        """Return the state of the sensor."""
        disruptions = self._get_disruptions()
        # Sensor is ON if there are active disruptions
        return len(disruptions) > 0

    @property
    def is_on(self) -> bool:
        """Return true if there are active disruptions."""
        return self.native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        disruptions = self._get_disruptions()
        
        # Format disruptions for attributes
        formatted_disruptions = []
        for disruption in disruptions:
            formatted_disruption = {
                ATTR_DISRUPTION_ID: disruption.get("id", ""),
                ATTR_DISRUPTION_TITLE: disruption.get("title", ""),
                ATTR_DISRUPTION_TYPE: disruption.get("type", ""),
                ATTR_DISRUPTION_IMPACT: disruption.get("impact", 0),
                ATTR_DISRUPTION_PHASE: disruption.get("phase", ""),
                ATTR_DISRUPTION_CAUSE: disruption.get("cause", ""),
            }
            
            # Add timestamps if available
            start_time = disruption.get("start")
            if start_time:
                formatted_disruption[ATTR_DISRUPTION_START] = start_time.isoformat()
            
            end_time = disruption.get("end")
            if end_time:
                formatted_disruption[ATTR_DISRUPTION_END] = end_time.isoformat()
            
            # Add station list
            stations = disruption.get("stations", [])
            formatted_disruption[ATTR_DISRUPTION_STATIONS] = stations
            
            # Add period and expected duration if available
            if "period" in disruption:
                formatted_disruption["period"] = disruption["period"]
            if "expected_duration" in disruption:
                formatted_disruption["expected_duration"] = disruption["expected_duration"]
            
            formatted_disruptions.append(formatted_disruption)
        
        return {
            ATTR_DISRUPTIONS: formatted_disruptions,
            "count": len(formatted_disruptions),
            "station_name": self._location_name,
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if self.is_on:
            return "mdi:alert-circle"
        return "mdi:check-circle"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _get_disruptions(self) -> list[dict[str, Any]]:
        """Get the list of disruptions from coordinator data."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("disruptions", [])

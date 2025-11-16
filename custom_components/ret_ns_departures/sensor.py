"""Sensor platform for RET & NS Departures."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_ACTUAL_TIME,
    ATTR_DELAY,
    ATTR_DEPARTURES,
    ATTR_DESTINATION,
    ATTR_LINE,
    ATTR_OPERATOR,
    ATTR_PLATFORM,
    ATTR_SCHEDULED_TIME,
    ATTR_STOP_NAME,
    ATTR_TRAIN_TYPE,
    ATTR_TRIP_NUMBER,
    CONF_OPERATOR,
    CONF_STATION_NAME,
    CONF_STOP_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)
from .coordinator import DeparturesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RET & NS Departures sensors."""
    coordinator: DeparturesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    operator = config_entry.data.get(CONF_OPERATOR)
    
    if operator == STOP_TYPE_RET:
        location_name = config_entry.data.get(CONF_STOP_NAME, "Unknown Stop")
    elif operator == STOP_TYPE_NS:
        location_name = config_entry.data.get(CONF_STATION_NAME, "Unknown Station")
    else:
        location_name = "Unknown"
    
    entities = [
        NextDepartureSensor(coordinator, config_entry, location_name),
        TimeToNextDepartureSensor(coordinator, config_entry, location_name),
    ]
    
    async_add_entities(entities)


class DepartureSensorBase(CoordinatorEntity[DeparturesCoordinator], SensorEntity):
    """Base class for departure sensors."""

    def __init__(
        self,
        coordinator: DeparturesCoordinator,
        config_entry: ConfigEntry,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._location_name = location_name
        self._attr_has_entity_name = True
        
        operator = config_entry.data.get(CONF_OPERATOR, "unknown")
        location_id = coordinator.location_id
        
        # Create unique ID
        self._attr_unique_id = f"{config_entry.entry_id}_{self._sensor_type}"
        
        # Create device info for grouping sensors
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"{operator.upper()} {location_name}",
            "manufacturer": operator.upper(),
            "model": f"{operator.upper()} Departure Monitor",
        }

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def _departures(self) -> list[dict[str, Any]]:
        """Get the list of departures from coordinator data."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("departures", [])


class NextDepartureSensor(DepartureSensorBase):
    """Sensor showing the next departure information."""

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "next_departure"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Next Departure"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        departures = self._departures
        
        if not departures:
            return None
        
        next_departure = departures[0]
        actual_time = next_departure.get("actual_time")
        
        if actual_time is None:
            # Train is cancelled
            return "Cancelled"
        
        # Return ISO format time
        return actual_time.isoformat()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        departures = self._departures
        
        if not departures:
            return {
                ATTR_DEPARTURES: [],
                ATTR_STOP_NAME: self._location_name,
            }
        
        next_departure = departures[0]
        
        # Format departures for attributes
        formatted_departures = []
        for dep in departures:
            actual_time = dep.get("actual_time")
            scheduled_time = dep.get("scheduled_time")
            
            formatted_dep = {
                ATTR_LINE: dep.get("line", ""),
                ATTR_OPERATOR: dep.get("operator", ""),
                ATTR_DESTINATION: dep.get("destination", ""),
                ATTR_PLATFORM: dep.get("platform", ""),
                ATTR_DELAY: dep.get("delay", 0),
                ATTR_SCHEDULED_TIME: scheduled_time.isoformat() if scheduled_time else None,
                ATTR_ACTUAL_TIME: actual_time.isoformat() if actual_time else None,
            }
            
            # Add NS-specific attributes
            if "train_type" in dep:
                formatted_dep[ATTR_TRAIN_TYPE] = dep.get("train_type", "")
            if "trip_number" in dep:
                formatted_dep[ATTR_TRIP_NUMBER] = dep.get("trip_number", "")
            if "cancelled" in dep:
                formatted_dep["cancelled"] = dep.get("cancelled", False)
            
            formatted_departures.append(formatted_dep)
        
        return {
            ATTR_LINE: next_departure.get("line", ""),
            ATTR_OPERATOR: next_departure.get("operator", ""),
            ATTR_DESTINATION: next_departure.get("destination", ""),
            ATTR_PLATFORM: next_departure.get("platform", ""),
            ATTR_DELAY: next_departure.get("delay", 0),
            ATTR_SCHEDULED_TIME: next_departure.get("scheduled_time").isoformat()
            if next_departure.get("scheduled_time")
            else None,
            ATTR_ACTUAL_TIME: next_departure.get("actual_time").isoformat()
            if next_departure.get("actual_time")
            else None,
            ATTR_DEPARTURES: formatted_departures,
            ATTR_STOP_NAME: self._location_name,
            "cancelled": next_departure.get("cancelled", False),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        operator = self._config_entry.data.get(CONF_OPERATOR)
        if operator == STOP_TYPE_NS:
            return "mdi:train"
        return "mdi:bus"


class TimeToNextDepartureSensor(DepartureSensorBase):
    """Sensor showing minutes until the next departure."""

    @property
    def _sensor_type(self) -> str:
        """Return the sensor type."""
        return "time_to_next_departure"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Time to Next Departure"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        departures = self._departures
        
        if not departures:
            return None
        
        next_departure = departures[0]
        actual_time = next_departure.get("actual_time")
        
        if actual_time is None:
            # Train is cancelled
            return None
        
        # Calculate minutes until departure
        now = dt_util.now()
        time_diff = actual_time - now
        minutes = int(time_diff.total_seconds() / 60)
        
        return max(0, minutes)  # Don't return negative values

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        departures = self._departures
        
        if not departures:
            return {
                ATTR_STOP_NAME: self._location_name,
            }
        
        next_departure = departures[0]
        
        return {
            ATTR_LINE: next_departure.get("line", ""),
            ATTR_OPERATOR: next_departure.get("operator", ""),
            ATTR_DESTINATION: next_departure.get("destination", ""),
            ATTR_PLATFORM: next_departure.get("platform", ""),
            ATTR_DELAY: next_departure.get("delay", 0),
            ATTR_SCHEDULED_TIME: next_departure.get("scheduled_time").isoformat()
            if next_departure.get("scheduled_time")
            else None,
            ATTR_ACTUAL_TIME: next_departure.get("actual_time").isoformat()
            if next_departure.get("actual_time")
            else None,
            ATTR_STOP_NAME: self._location_name,
            "cancelled": next_departure.get("cancelled", False),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:clock-outline"

    @property
    def state_class(self) -> str:
        """Return the state class."""
        return "measurement"

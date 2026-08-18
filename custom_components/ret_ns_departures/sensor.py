"""Sensor platform for RET & NS Departures."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_ACTUAL_TIME,
    ATTR_DELAY,
    ATTR_DEPARTURES,
    ATTR_DESCRIPTION,
    ATTR_DISRUPTIONS,
    ATTR_DESTINATION,
    ATTR_LINE,
    ATTR_MESSAGE,
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
from .coordinator import DeparturesCoordinator, RETNSConfigEntry
from .disruption_info import (
    disruption_headline,
    disruption_message,
    primary_disruption,
    sort_disruptions,
)


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: RETNSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RET & NS Departures sensors."""
    coordinator = config_entry.runtime_data

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


def _format_departure(dep: dict[str, Any]) -> dict[str, Any]:
    """Format a departure dict for entity attributes."""
    actual_time = dep.get("actual_time")
    scheduled_time = dep.get("scheduled_time")

    formatted = {
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
        formatted[ATTR_TRAIN_TYPE] = dep.get("train_type", "")
    if "trip_number" in dep:
        formatted[ATTR_TRIP_NUMBER] = dep.get("trip_number", "")
    if "cancelled" in dep:
        formatted["cancelled"] = dep.get("cancelled", False)

    return formatted


class DepartureSensorBase(CoordinatorEntity[DeparturesCoordinator], SensorEntity):
    """Base class for departure sensors."""

    _attr_has_entity_name = True
    _sensor_type: str

    def __init__(
        self,
        coordinator: DeparturesCoordinator,
        config_entry: RETNSConfigEntry,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._location_name = location_name

        operator = config_entry.data.get(CONF_OPERATOR, "unknown")

        self._attr_unique_id = f"{config_entry.entry_id}_{self._sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"{operator.upper()} {location_name}",
            manufacturer=operator.upper(),
            model=f"{operator.upper()} Departure Monitor",
        )

    @property
    def _departures(self) -> list[dict[str, Any]]:
        """Get the list of departures from coordinator data."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("departures", [])

    @property
    def _next_departure(self) -> dict[str, Any] | None:
        """Get the next departure that will actually run (skips cancelled)."""
        for dep in self._departures:
            if not dep.get("cancelled") and dep.get("actual_time") is not None:
                return dep
        return None

    @property
    def _is_dutch(self) -> bool:
        """Return True when Home Assistant is set to Dutch."""
        hass = self.hass
        if hass is None:
            return False
        language = getattr(hass.config, "language", None) or "en"
        return str(language).lower().startswith("nl")

    @property
    def _disruptions(self) -> list[dict[str, Any]]:
        """Active disruptions from the coordinator, if monitoring is on."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("disruptions") or []

    @property
    def _next_departure_description(self) -> str | None:
        """Human-readable next service, e.g. 'IC 2834 to Utrecht'."""
        next_departure = self._next_departure
        if next_departure is None:
            return None
        return describe_departure(
            next_departure,
            dutch=self._is_dutch,
            operator=self._config_entry.data.get(CONF_OPERATOR),
        )


class NextDepartureSensor(DepartureSensorBase):
    """Timestamp sensor for the next departure that will actually run."""

    _sensor_type = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "next_departure"

    @property
    def name(self) -> str | None:
        """Show train and destination next to the departure time."""
        description = self._next_departure_description
        if description:
            return description
        if self._next_departure is None:
            headline = disruption_headline(primary_disruption(self._disruptions))
            if headline:
                prefix = "Geen dienst" if self._is_dutch else "No service"
                return f"{prefix} — {headline}"
        return super().name

    @property
    def native_value(self) -> datetime | None:
        """Return the departure time of the next non-cancelled departure."""
        next_departure = self._next_departure

        if next_departure is None:
            return None

        return next_departure.get("actual_time")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        departures = self._departures
        next_departure = self._next_departure

        attributes: dict[str, Any] = {}
        disruptions = self._disruptions
        if disruptions:
            message = disruption_message(primary_disruption(disruptions))
            if message:
                attributes[ATTR_MESSAGE] = message
            attributes[ATTR_DISRUPTIONS] = [
                disruption.get("title") or disruption.get("id")
                for disruption in sort_disruptions(disruptions)
            ]
            attributes["disruption_count"] = len(disruptions)

        attributes[ATTR_DEPARTURES] = [_format_departure(dep) for dep in departures]
        attributes[ATTR_STOP_NAME] = self._location_name

        if next_departure is not None:
            attributes.update(_format_departure(next_departure))
            description = self._next_departure_description
            if description:
                attributes[ATTR_DESCRIPTION] = description
        else:
            notice = primary_disruption(disruptions)
            if notice and notice.get("url"):
                attributes["source_url"] = notice["url"]
            if notice and notice.get("replacement_stops"):
                attributes["replacement_stops"] = notice["replacement_stops"]
            if notice and notice.get("period"):
                attributes["period"] = notice["period"]

        image_url = None
        if self.coordinator.data:
            image_url = self.coordinator.data.get("train_image_url")
            composition = self.coordinator.data.get("train_composition") or {}
            if composition.get("type"):
                attributes["rolling_stock"] = composition["type"]
            if composition.get("lengte") is not None:
                attributes["train_length"] = composition["lengte"]
        if image_url:
            attributes["train_image"] = image_url

        return attributes

    @property
    def entity_picture(self) -> str | None:
        """Show the Virtual Train image on the next-departure entity when public."""
        if not self.coordinator.data:
            return None
        url = self.coordinator.data.get("train_image_url")
        return url if isinstance(url, str) else None

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        operator = self._config_entry.data.get(CONF_OPERATOR)
        if operator == STOP_TYPE_NS:
            return "mdi:train"
        return "mdi:bus"


class TimeToNextDepartureSensor(DepartureSensorBase):
    """Sensor showing minutes until the next departure."""

    _sensor_type = "time_to_next_departure"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "time_to_next_departure"

    @property
    def native_value(self) -> int | None:
        """Return minutes until the next non-cancelled departure."""
        next_departure = self._next_departure

        if next_departure is None:
            return None

        actual_time = next_departure["actual_time"]
        minutes = int((actual_time - dt_util.now()).total_seconds() / 60)

        return max(0, minutes)  # Don't return negative values

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        next_departure = self._next_departure

        attributes: dict[str, Any] = {ATTR_STOP_NAME: self._location_name}

        if next_departure is not None:
            attributes.update(_format_departure(next_departure))
            description = self._next_departure_description
            if description:
                attributes[ATTR_DESCRIPTION] = description
        else:
            notice = primary_disruption(self._disruptions)
            message = disruption_message(notice)
            if message:
                attributes[ATTR_MESSAGE] = message
            if notice and notice.get("replacement_stops"):
                attributes["replacement_stops"] = notice["replacement_stops"]
            if notice and notice.get("url"):
                attributes["source_url"] = notice["url"]

        return attributes


def describe_departure(
    departure: dict[str, Any],
    *,
    dutch: bool = False,
    operator: str | None = None,
) -> str:
    """Build a short 'train to destination' label for the next service."""
    destination = str(departure.get("destination") or "").strip()
    line = str(departure.get("line") or "").strip()
    train_type = str(departure.get("train_type") or "").strip()
    trip_number = str(departure.get("trip_number") or "").strip()
    category = line or train_type

    if operator == STOP_TYPE_RET:
        prefix = "Lijn" if dutch else "Line"
        service = f"{prefix} {category}".strip() if category else ""
    else:
        parts = [category]
        if trip_number and trip_number not in parts:
            parts.append(trip_number)
        service = " ".join(part for part in parts if part)

    if service and destination:
        preposition = "naar" if dutch else "to"
        return f"{service} {preposition} {destination}"
    return service or destination

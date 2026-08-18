"""Binary sensor platform for NS and RET service notices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DISRUPTION_BBOX,
    ATTR_DISRUPTION_CAUSE,
    ATTR_DISRUPTION_END,
    ATTR_DISRUPTION_GEOMETRY_TYPE,
    ATTR_DISRUPTION_ID,
    ATTR_DISRUPTION_IMPACT,
    ATTR_DISRUPTION_LEVEL,
    ATTR_DISRUPTION_MAP_TYPE,
    ATTR_DISRUPTION_PHASE,
    ATTR_DISRUPTION_START,
    ATTR_DISRUPTION_STATION_CODES,
    ATTR_DISRUPTION_STATIONS,
    ATTR_DISRUPTION_TITLE,
    ATTR_DISRUPTION_TYPE,
    ATTR_DISRUPTIONS,
    ATTR_GEOJSON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_MONITOR_DISRUPTIONS,
    CONF_OPERATOR,
    CONF_STATION_NAME,
    CONF_STOP_NAME,
    DOMAIN,
    STOP_TYPE_NS,
    STOP_TYPE_RET,
)
from .coordinator import DeparturesCoordinator, RETNSConfigEntry
from .disruption_info import disruption_name, primary_display_attributes


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: RETNSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NS Disruption binary sensors."""
    coordinator = config_entry.runtime_data

    operator = config_entry.data.get(CONF_OPERATOR)
    monitor_disruptions = config_entry.options.get(
        CONF_MONITOR_DISRUPTIONS,
        config_entry.data.get(CONF_MONITOR_DISRUPTIONS, False),
    )

    # NS: optional station disruptions. RET: omleidingen when a halt is empty.
    if operator == STOP_TYPE_NS and monitor_disruptions:
        location_name = config_entry.data.get(CONF_STATION_NAME, "Unknown Station")
        async_add_entities(
            [StationDisruptionSensor(coordinator, config_entry, location_name)]
        )
    elif operator == STOP_TYPE_RET:
        location_name = config_entry.data.get(CONF_STOP_NAME, "Unknown Stop")
        async_add_entities(
            [StationDisruptionSensor(coordinator, config_entry, location_name)]
        )


class StationDisruptionSensor(
    CoordinatorEntity[DeparturesCoordinator], BinarySensorEntity
):
    """Binary sensor for station disruptions."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = True
    _attr_translation_key = "disruptions"

    def __init__(
        self,
        coordinator: DeparturesCoordinator,
        config_entry: RETNSConfigEntry,
        location_name: str,
    ) -> None:
        """Initialize the disruption sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._location_name = location_name

        self._attr_unique_id = f"{config_entry.entry_id}_disruptions"

        operator = config_entry.data.get(CONF_OPERATOR, STOP_TYPE_NS)
        # Use same device info as departure sensors for grouping
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"{operator.upper()} {location_name}",
            manufacturer=operator.upper(),
            model=f"{operator.upper()} Departure Monitor",
        )

    @property
    def is_on(self) -> bool:
        """Return true if there are active disruptions."""
        return len(self._get_disruptions()) > 0

    @property
    def name(self) -> str | None:
        """Show the primary disruption in the entity name when one is active."""
        headline = disruption_name(self._get_disruptions())
        if headline:
            return headline
        return super().name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return more-info attributes, with what's wrong first."""
        disruptions = self._get_disruptions()

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

            start_time = disruption.get("start")
            if start_time:
                formatted_disruption[ATTR_DISRUPTION_START] = start_time.isoformat()

            end_time = disruption.get("end")
            if end_time:
                formatted_disruption[ATTR_DISRUPTION_END] = end_time.isoformat()

            formatted_disruption[ATTR_DISRUPTION_STATIONS] = disruption.get(
                "stations", []
            )

            if "period" in disruption:
                formatted_disruption["period"] = disruption["period"]
            if "expected_duration" in disruption:
                formatted_disruption["expected_duration"] = disruption[
                    "expected_duration"
                ]
            if disruption.get("situation"):
                formatted_disruption["situation"] = disruption["situation"]
            if disruption.get("additional_travel_time"):
                formatted_disruption["additional_travel_time"] = disruption[
                    "additional_travel_time"
                ]
            if disruption.get("description"):
                formatted_disruption["description"] = disruption["description"]

            formatted_disruptions.append(
                _with_storing_geo(formatted_disruption, disruption.get("geo"))
            )

        attributes: dict[str, Any] = {}
        attributes.update(primary_display_attributes(disruptions))
        attributes["count"] = len(formatted_disruptions)
        attributes["station_name"] = self._location_name
        attributes.update(_primary_storing_location(formatted_disruptions))
        if formatted_disruptions:
            attributes[ATTR_DISRUPTIONS] = formatted_disruptions
        geojson = _storing_geojson(formatted_disruptions)
        if geojson is not None:
            attributes[ATTR_GEOJSON] = geojson
        return attributes

    def _get_disruptions(self) -> list[dict[str, Any]]:
        """Get the list of disruptions from coordinator data."""
        if not self.coordinator.data:
            return []
        return self.coordinator.data.get("disruptions", [])


def _with_storing_geo(
    formatted: dict[str, Any], geo: dict[str, Any] | None
) -> dict[str, Any]:
    """Copy compact getStoring fields onto a disruption attribute dict."""
    if not geo:
        return formatted
    if geo.get(ATTR_LATITUDE) is not None:
        formatted[ATTR_LATITUDE] = geo[ATTR_LATITUDE]
    if geo.get(ATTR_LONGITUDE) is not None:
        formatted[ATTR_LONGITUDE] = geo[ATTR_LONGITUDE]
    if geo.get("bbox"):
        formatted[ATTR_DISRUPTION_BBOX] = geo["bbox"]
    if geo.get("geometry_type"):
        formatted[ATTR_DISRUPTION_GEOMETRY_TYPE] = geo["geometry_type"]
    if geo.get("station_codes"):
        formatted[ATTR_DISRUPTION_STATION_CODES] = geo["station_codes"]
    if geo.get("level"):
        formatted[ATTR_DISRUPTION_LEVEL] = geo["level"]
    if geo.get("map_type"):
        formatted[ATTR_DISRUPTION_MAP_TYPE] = geo["map_type"]
    return formatted


def _primary_storing_location(disruptions: list[dict[str, Any]]) -> dict[str, Any]:
    """Use the first mapped disruption so the binary sensor can appear on the map."""
    for disruption in disruptions:
        latitude = disruption.get(ATTR_LATITUDE)
        longitude = disruption.get(ATTR_LONGITUDE)
        if latitude is not None and longitude is not None:
            return {ATTR_LATITUDE: latitude, ATTR_LONGITUDE: longitude}
    return {}


def _storing_geojson(disruptions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build a Point FeatureCollection from disruption centroids."""
    features: list[dict[str, Any]] = []
    for disruption in disruptions:
        latitude = disruption.get(ATTR_LATITUDE)
        longitude = disruption.get(ATTR_LONGITUDE)
        if latitude is None or longitude is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": disruption.get(ATTR_DISRUPTION_ID),
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "properties": {
                    "title": disruption.get(ATTR_DISRUPTION_TITLE),
                    "type": disruption.get(ATTR_DISRUPTION_TYPE),
                    "level": disruption.get(ATTR_DISRUPTION_LEVEL),
                    "stations": disruption.get(ATTR_DISRUPTION_STATION_CODES) or [],
                },
            }
        )
    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}

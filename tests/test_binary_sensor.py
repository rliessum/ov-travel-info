"""Tests for the NS disruption binary sensor."""
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.binary_sensor import StationDisruptionSensor
from custom_components.ret_ns_departures.const import (
    CONF_OPERATOR,
    DOMAIN,
    STOP_TYPE_NS,
)


def _sensor(disruptions):
    coordinator = MagicMock()
    coordinator.data = {"disruptions": disruptions}
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_OPERATOR: STOP_TYPE_NS})
    return StationDisruptionSensor(coordinator, entry, "Rotterdam Centraal")


def test_disruption_sensor_exposes_spoorkaart_geo():
    sensor = _sensor(
        [
            {
                "id": "6066934",
                "title": "Schiphol - Leiden",
                "type": "DISRUPTION",
                "impact": 3,
                "phase": "In behandeling",
                "cause": "Seinstoring",
                "stations": ["Schiphol Airport", "Leiden Centraal"],
                "geo": {
                    "latitude": 52.2,
                    "longitude": 4.1,
                    "bbox": [4.0, 52.0, 4.2, 52.4],
                    "geometry_type": "MultiLineString",
                    "station_codes": ["HFD", "LEDN"],
                    "level": "MINDER_TREINEN",
                    "map_type": "STORING",
                },
            }
        ]
    )

    assert sensor.is_on is True
    assert sensor.name == "Schiphol - Leiden"
    attrs = sensor.extra_state_attributes
    assert attrs["message"] == "Schiphol - Leiden. Seinstoring. Minder treinen."
    assert attrs["title"] == "Schiphol - Leiden"
    assert attrs["cause"] == "Seinstoring"
    assert attrs["stations"] == "Schiphol Airport, Leiden Centraal"
    assert attrs["count"] == 1
    assert attrs["latitude"] == 52.2
    assert attrs["longitude"] == 4.1
    disruption = attrs["disruptions"][0]
    assert disruption["station_codes"] == ["HFD", "LEDN"]
    assert disruption["level"] == "MINDER_TREINEN"
    assert disruption["map_type"] == "STORING"
    assert disruption["geometry_type"] == "MultiLineString"
    assert attrs["geojson"]["type"] == "FeatureCollection"
    assert attrs["geojson"]["features"][0]["geometry"]["coordinates"] == [4.1, 52.2]


def test_disruption_sensor_off_without_items():
    sensor = _sensor([])
    assert sensor.is_on is False
    attrs = sensor.extra_state_attributes
    assert attrs["count"] == 0
    assert "message" not in attrs
    assert "geojson" not in attrs
    assert "latitude" not in attrs
    assert "disruptions" not in attrs


def test_disruption_sensor_name_lists_extra_count():
    sensor = _sensor(
        [
            {"id": "1", "title": "Leiden - Den Haag", "type": "DISRUPTION", "impact": 3},
            {"id": "2", "title": "Groningen - Leer", "type": "MAINTENANCE", "impact": 1},
        ]
    )
    assert sensor.name == "Leiden - Den Haag (+1)"
    assert sensor.extra_state_attributes["other_disruptions"] == ["Groningen - Leer"]

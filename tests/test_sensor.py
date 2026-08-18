"""Tests for the departure sensor entities."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from freezegun import freeze_time
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ret_ns_departures.const import (
    CONF_OPERATOR,
    DOMAIN,
    STOP_TYPE_NS,
)
from custom_components.ret_ns_departures.sensor import (
    NextDepartureSensor,
    TimeToNextDepartureSensor,
    describe_departure,
)

NOW = datetime(2024, 11, 16, 12, 0, tzinfo=timezone.utc)


def _departure(minutes_from_now: int | None, *, cancelled: bool = False, **fields):
    actual = (
        None
        if minutes_from_now is None
        else datetime(2024, 11, 16, 12, minutes_from_now, tzinfo=timezone.utc)
    )
    return {
        "line": fields.get("line", "IC"),
        "operator": "NS",
        "destination": fields.get("destination", "Utrecht"),
        "platform": "5",
        "delay": 0,
        "scheduled_time": actual,
        "actual_time": actual,
        "cancelled": cancelled,
        "train_type": fields.get("train_type", "IC"),
        "trip_number": fields.get("trip_number", "2834"),
    }


def _make_sensors(departures, disruptions=None):
    coordinator = MagicMock()
    coordinator.data = {"departures": departures}
    if disruptions is not None:
        coordinator.data["disruptions"] = disruptions
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_OPERATOR: STOP_TYPE_NS})
    return (
        NextDepartureSensor(coordinator, entry, "Rotterdam Centraal"),
        TimeToNextDepartureSensor(coordinator, entry, "Rotterdam Centraal"),
    )


def test_next_departure_returns_datetime():
    next_sensor, _ = _make_sensors([_departure(10), _departure(20)])

    value = next_sensor.native_value
    assert isinstance(value, datetime)
    assert value.minute == 10


def test_next_departure_skips_cancelled():
    next_sensor, _ = _make_sensors(
        [_departure(None, cancelled=True), _departure(20)]
    )

    assert next_sensor.native_value.minute == 20
    # Attributes describe the departure shown in the state
    attrs = next_sensor.extra_state_attributes
    assert attrs["cancelled"] is False
    # The full list still includes the cancelled departure
    assert len(attrs["departures"]) == 2
    assert attrs["departures"][0]["cancelled"] is True


def test_next_departure_none_when_no_departures():
    next_sensor, time_sensor = _make_sensors([])

    assert next_sensor.native_value is None
    assert time_sensor.native_value is None


def test_empty_ret_board_shows_dienstregeling_reason():
    next_sensor, time_sensor = _make_sensors(
        [],
        disruptions=[
            {
                "id": "ret-1",
                "title": "Werkzaamheden Hofplein",
                "type": "MAINTENANCE",
                "cause": "Werkzaamheden Hofplein",
                "situation": "Schiekade is vervallen. Vervangende halte: Provenierssingel tot 23 november 2026 01:00",
                "period": "18 juli 2026 05:00 – 23 november 2026 01:00",
                "replacement_stops": ["Provenierssingel"],
                "url": "https://www.ret.nl/home/reizen/dienstregeling/tram-8.html",
            }
        ],
    )
    next_sensor.hass = MagicMock()
    next_sensor.hass.config.language = "en"

    assert next_sensor.name == "No service — Werkzaamheden Hofplein"
    attrs = next_sensor.extra_state_attributes
    assert attrs["message"].startswith("Werkzaamheden Hofplein.")
    assert attrs["replacement_stops"] == ["Provenierssingel"]
    assert attrs["source_url"].endswith("tram-8.html")
    assert time_sensor.extra_state_attributes["message"].startswith(
        "Werkzaamheden Hofplein."
    )


def test_next_departure_none_when_all_cancelled():
    next_sensor, _ = _make_sensors([_departure(None, cancelled=True)])

    assert next_sensor.native_value is None


@freeze_time(NOW)
def test_time_to_next_departure_minutes():
    _, time_sensor = _make_sensors([_departure(10)])

    assert time_sensor.native_value == 10


@freeze_time(NOW)
def test_time_to_next_departure_skips_cancelled():
    _, time_sensor = _make_sensors(
        [_departure(None, cancelled=True), _departure(30)]
    )

    assert time_sensor.native_value == 30


def test_next_departure_name_includes_train_and_destination():
    next_sensor, time_sensor = _make_sensors(
        [_departure(10, line="IC", trip_number="2834", destination="Amsterdam Centraal")]
    )

    assert next_sensor.name == "IC 2834 to Amsterdam Centraal"
    assert next_sensor.extra_state_attributes["description"] == (
        "IC 2834 to Amsterdam Centraal"
    )
    assert time_sensor.extra_state_attributes["description"] == (
        "IC 2834 to Amsterdam Centraal"
    )


def test_describe_departure_ret_and_dutch():
    ret = {"line": "2", "destination": "Nesselande"}
    assert describe_departure(ret, operator="ret") == "Line 2 to Nesselande"
    assert describe_departure(ret, operator="ret", dutch=True) == "Lijn 2 naar Nesselande"
    assert (
        describe_departure(
            {"line": "SPR", "trip_number": "6164", "destination": "Meppel"},
            dutch=True,
        )
        == "SPR 6164 naar Meppel"
    )


def test_next_departure_includes_disruption_titles():
    next_sensor, _ = _make_sensors(
        [_departure(10)],
        disruptions=[{"id": "d1", "title": "Seinstoring Utrecht"}],
    )

    attrs = next_sensor.extra_state_attributes
    assert attrs["disruption_count"] == 1
    assert attrs["disruptions"] == ["Seinstoring Utrecht"]
    assert attrs["message"] == "Seinstoring Utrecht."


def test_next_departure_entity_picture_from_virtual_train():
    next_sensor, _ = _make_sensors([_departure(10)])
    next_sensor.coordinator.data["train_image_url"] = "https://example.test/train.png"
    next_sensor.coordinator.data["train_composition"] = {"type": "VIRM", "lengte": 6}

    assert next_sensor.entity_picture == "https://example.test/train.png"
    attrs = next_sensor.extra_state_attributes
    assert attrs["train_image"] == "https://example.test/train.png"
    assert attrs["rolling_stock"] == "VIRM"
    assert attrs["train_length"] == 6

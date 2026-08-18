"""Tests for disruption presentation helpers."""

from custom_components.ret_ns_departures.disruption_info import (
    disruption_message,
    disruption_name,
    primary_disruption,
    primary_display_attributes,
)


def test_primary_prefers_calamity_then_high_impact():
    items = [
        {"id": "m", "type": "MAINTENANCE", "impact": 5, "title": "Work"},
        {"id": "d", "type": "DISRUPTION", "impact": 2, "title": "Signal"},
        {"id": "c", "type": "CALAMITY", "impact": 1, "title": "Grand Prix"},
    ]
    assert primary_disruption(items)["id"] == "c"


def test_disruption_message_joins_what_is_wrong():
    message = disruption_message(
        {
            "title": "Amsterdam Zuid - Schiphol - Leiden Centraal.",
            "cause": "Seinstoring",
            "situation": "Minder treinen",
            "additional_travel_time": "+15 min",
            "expected_duration": "Tot ongeveer 12:00 uur",
        }
    )
    assert message == (
        "Amsterdam Zuid - Schiphol - Leiden Centraal. "
        "Seinstoring. Minder treinen. +15 min. Tot ongeveer 12:00 uur."
    )


def test_disruption_message_uses_map_level_when_situation_missing():
    message = disruption_message(
        {
            "title": "Leiden - Den Haag",
            "cause": "Werkzaamheden",
            "geo": {"level": "MINDER_TREINEN"},
        }
    )
    assert message == "Leiden - Den Haag. Werkzaamheden. Minder treinen."


def test_disruption_name_includes_extra_count():
    name = disruption_name(
        [
            {"title": "Leiden - Den Haag", "type": "DISRUPTION", "impact": 3},
            {"title": "Groningen - Leer", "type": "MAINTENANCE", "impact": 1},
        ]
    )
    assert name == "Leiden - Den Haag (+1)"


def test_primary_display_attributes_are_flat_and_readable():
    attrs = primary_display_attributes(
        [
            {
                "title": "Leiden - Den Haag",
                "type": "DISRUPTION",
                "impact": 4,
                "cause": "Seinstoring",
                "situation": "Geen treinen",
                "phase": "In behandeling",
                "stations": ["Leiden Centraal", "Den Haag HS"],
            },
            {
                "title": "Groningen - Leer",
                "type": "MAINTENANCE",
                "impact": 1,
            },
        ]
    )
    assert attrs["message"].startswith("Leiden - Den Haag.")
    assert attrs["title"] == "Leiden - Den Haag"
    assert attrs["cause"] == "Seinstoring"
    assert attrs["situation"] == "Geen treinen"
    assert attrs["stations"] == "Leiden Centraal, Den Haag HS"
    assert attrs["other_disruptions"] == ["Groningen - Leer"]

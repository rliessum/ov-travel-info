"""Human-readable presentation for NS disruptions."""
from __future__ import annotations

from typing import Any

from .const import (
    ATTR_ADDITIONAL_TRAVEL_TIME,
    ATTR_DISRUPTION_CAUSE,
    ATTR_DISRUPTION_LEVEL,
    ATTR_DISRUPTION_PHASE,
    ATTR_DISRUPTION_STATIONS,
    ATTR_DISRUPTION_TITLE,
    ATTR_DISRUPTION_TYPE,
    ATTR_EXPECTED_DURATION,
    ATTR_MESSAGE,
    ATTR_OTHER_DISRUPTIONS,
    ATTR_PERIOD,
    ATTR_SITUATION,
)

_TYPE_RANK = {
    "CALAMITY": 0,
    "DISRUPTION": 1,
    "STORING": 1,
    "MAINTENANCE": 2,
    "WERKZAAMHEID": 2,
}

_LEVEL_LABELS = {
    "MINDER_TREINEN": "Minder treinen",
    "GEEN_TREINEN": "Geen treinen",
    "STATION_GESLOTEN": "Station gesloten",
    "OMREIZEN": "Reis via een andere route",
    "VERTRAGING": "Vertraging",
}


def sort_disruptions(disruptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Put calamities and high-impact disruptions first."""
    return sorted(disruptions, key=_disruption_sort_key)


def primary_disruption(disruptions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the disruption that should be shown first."""
    if not disruptions:
        return None
    return sort_disruptions(disruptions)[0]


def disruption_headline(disruption: dict[str, Any] | None) -> str:
    """Short title for entity names and lists."""
    if not disruption:
        return ""
    return str(disruption.get("title") or disruption.get("id") or "").strip()


def disruption_message(disruption: dict[str, Any] | None) -> str:
    """One paragraph that answers what is wrong."""
    if not disruption:
        return ""
    parts: list[str] = []
    title = disruption_headline(disruption)
    if title:
        parts.append(_strip_trailing_punct(title))

    cause = _clean_text(disruption.get("cause"))
    situation = _clean_text(disruption.get("situation"))
    level = _level_label(disruption)
    extra = _clean_text(disruption.get("additional_travel_time"))
    duration = _clean_text(
        disruption.get("expected_duration") or disruption.get("period")
    )

    for piece in (cause, situation or level, extra, duration):
        if piece and not _already_in(piece, parts):
            parts.append(piece)

    if not parts:
        return ""
    return f"{'. '.join(parts)}."


def disruption_name(disruptions: list[dict[str, Any]]) -> str | None:
    """Entity name: primary title, with a count when more are active."""
    primary = primary_disruption(disruptions)
    title = disruption_headline(primary)
    if not title:
        return None
    extra = len(disruptions) - 1
    if extra > 0:
        return f"{title} (+{extra})"
    return title


def primary_display_attributes(disruptions: list[dict[str, Any]]) -> dict[str, Any]:
    """Top-level more-info fields for the most important disruption."""
    primary = primary_disruption(disruptions)
    if primary is None:
        return {}

    attributes: dict[str, Any] = {}
    message = disruption_message(primary)
    if message:
        attributes[ATTR_MESSAGE] = message

    title = disruption_headline(primary)
    if title:
        attributes[ATTR_DISRUPTION_TITLE] = title

    for key, attr in (
        ("cause", ATTR_DISRUPTION_CAUSE),
        ("situation", ATTR_SITUATION),
        ("additional_travel_time", ATTR_ADDITIONAL_TRAVEL_TIME),
        ("expected_duration", ATTR_EXPECTED_DURATION),
        ("period", ATTR_PERIOD),
        ("phase", ATTR_DISRUPTION_PHASE),
    ):
        value = _clean_text(primary.get(key))
        if value:
            attributes[attr] = value

    dtype = _clean_text(primary.get("type"))
    if dtype:
        attributes[ATTR_DISRUPTION_TYPE] = dtype

    geo = primary.get("geo") if isinstance(primary.get("geo"), dict) else {}
    level = _clean_text(geo.get("level") or primary.get("level"))
    if level:
        attributes[ATTR_DISRUPTION_LEVEL] = level

    stations = primary.get("stations") or []
    if stations:
        attributes[ATTR_DISRUPTION_STATIONS] = ", ".join(
            str(station) for station in stations if station
        )

    others = [
        disruption_headline(item)
        for item in sort_disruptions(disruptions)
        if item is not primary
    ]
    others = [title for title in others if title]
    if others:
        attributes[ATTR_OTHER_DISRUPTIONS] = others

    replacements = primary.get("replacement_stops") or []
    if replacements:
        attributes["replacement_stops"] = replacements
    source_url = _clean_text(primary.get("url"))
    if source_url:
        attributes["source_url"] = source_url

    return attributes


def _disruption_sort_key(disruption: dict[str, Any]) -> tuple[int, int]:
    dtype = str(disruption.get("type") or "").upper()
    impact = disruption.get("impact")
    try:
        impact_value = int(impact)
    except (TypeError, ValueError):
        impact_value = 0
    return (_TYPE_RANK.get(dtype, 3), -impact_value)


def _level_label(disruption: dict[str, Any]) -> str:
    geo = disruption.get("geo") if isinstance(disruption.get("geo"), dict) else {}
    raw = _clean_text(geo.get("level") or disruption.get("level"))
    if not raw:
        return ""
    return _LEVEL_LABELS.get(raw.upper(), raw.replace("_", " ").capitalize())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _strip_trailing_punct(value: str) -> str:
    return value.rstrip(" .")


def _already_in(piece: str, parts: list[str]) -> bool:
    needle = piece.casefold()
    return any(needle in part.casefold() for part in parts)

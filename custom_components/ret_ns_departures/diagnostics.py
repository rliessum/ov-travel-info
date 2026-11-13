"""Diagnostics support for RET & NS Departures."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_NS_API_KEY
from .coordinator import RETNSConfigEntry

TO_REDACT = {CONF_NS_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RETNSConfigEntry  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """Return diagnostics for a config entry, without the API key or image."""
    coordinator = entry.runtime_data
    data = dict(coordinator.data or {})
    image = data.pop("train_image", None)

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "update_interval": str(coordinator.update_interval),
            "train_image_bytes": len(image) if image else 0,
            "data": data,
        },
    }

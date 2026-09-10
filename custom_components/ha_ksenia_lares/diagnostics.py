"""Diagnostics with secrets redacted."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .outputs import pair_shutters

_REDACT = {"password", "PINToUse", "pin"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = {key: ("***" if key.lower() in _REDACT else value) for key, value in entry.data.items()}
    runtime = getattr(entry, "runtime_data", None)
    if runtime is None:
        return {"entry": data, "loaded": False}

    pairs = pair_shutters(runtime.descriptions)
    return {
        "entry": data,
        "loaded": True,
        "panel": {
            "name": runtime.device_info.get("name"),
            "model": runtime.device_info.get("model"),
            "sw_version": runtime.device_info.get("sw_version"),
            "lares_version": runtime.device_info.get("lares_version"),
        },
        "outputs_named": len(runtime.descriptions),
        "outputs_polled": len(runtime.coordinator.data or []),
        "shutter_covers": [
            {
                "name": pair.name,
                "unique_id": pair.unique_id,
                "up": pair.up_id,
                "down": pair.down_id,
                "su": pair.su_id,
                "giu": pair.giu_id,
            }
            for pair in pairs
        ],
    }

"""Diagnostics download."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import Lywsd02ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Lywsd02ConfigEntry
) -> dict[str, Any]:
    state = asdict(entry.runtime_data.data)
    for key in ("last_check", "last_sync", "last_attempt"):
        if state[key] is not None:
            state[key] = state[key].isoformat()
    return {"options": dict(entry.options), "state": state}

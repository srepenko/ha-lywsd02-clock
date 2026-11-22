"""Binary sensor: the last attempt to reach the clock failed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Lywsd02ConfigEntry
from .entity import Lywsd02Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Lywsd02ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SyncProblem(entry.runtime_data, "sync_problem")])


class SyncProblem(Lywsd02Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        if state.last_attempt is None:
            return None
        return state.error is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.data
        return {
            "last_error": s.error,
            "consecutive_failures": s.consecutive_failures,
            "last_attempt": s.last_attempt.isoformat() if s.last_attempt else None,
            "drift_after_sync": s.drift_after,
            "recent": s.history[:5],
        }

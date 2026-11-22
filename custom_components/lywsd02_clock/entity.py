"""Base entity: attaches to the same device as the Xiaomi BLE sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Lywsd02Coordinator


class Lywsd02Entity(CoordinatorEntity[Lywsd02Coordinator]):
    """Common device info / unique id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Lywsd02Coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_translation_key = key
        # Same identifiers/connections as the Xiaomi BLE integration uses, so the
        # clock shows up as one device with both sets of entities.
        self._attr_device_info = DeviceInfo(
            identifiers={(CONNECTION_BLUETOOTH, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            manufacturer="Xiaomi",
            model="LYWSD02",
        )

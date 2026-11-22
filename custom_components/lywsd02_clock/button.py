"""Button: sync the clock now."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Lywsd02ConfigEntry
from .entity import Lywsd02Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Lywsd02ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [
            SyncTimeButton(entry.runtime_data, "sync_time"),
            IdentifyButton(entry.runtime_data, "identify"),
        ]
    )


class SyncTimeButton(Lywsd02Entity, ButtonEntity):
    """Write the current time to the clock regardless of drift."""

    async def async_press(self) -> None:
        if await self.coordinator.async_check_and_sync(force=True) is False:
            raise HomeAssistantError(f"Clock not reachable: {self.coordinator.data.error}")


class IdentifyButton(Lywsd02Entity, ButtonEntity):
    """Show this clock's number (01:11, 02:22, ...) and °F for a minute to find it."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_identify()
        except Exception as err:  # BLE errors of any kind -> visible to the user
            raise HomeAssistantError(f"Clock not reachable: {err}") from err

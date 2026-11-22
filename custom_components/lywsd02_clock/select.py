"""Select: temperature unit shown on the clock."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Lywsd02ConfigEntry
from .const import UNIT_CELSIUS, UNIT_FAHRENHEIT
from .entity import Lywsd02Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Lywsd02ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([TemperatureUnit(entry.runtime_data, "temperature_unit")])


class TemperatureUnit(Lywsd02Entity, SelectEntity):
    _attr_options = [UNIT_CELSIUS, UNIT_FAHRENHEIT]
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.unit

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.async_set_unit(option)
        except Exception as err:  # BLE errors of any kind -> visible to the user
            raise HomeAssistantError(f"Clock not reachable: {err}") from err

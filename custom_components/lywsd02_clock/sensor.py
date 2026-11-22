"""Sensors: temperature / humidity / battery (from advertisements) and clock diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Lywsd02ConfigEntry
from .coordinator import ClockState
from .entity import Lywsd02Entity


@dataclass(frozen=True, kw_only=True)
class ClockSensorDescription(SensorEntityDescription):
    value: Callable[[ClockState], Any]
    attr: str | None = None  # ClockState field restored after a restart
    from_advertisements: bool = False


SENSORS: tuple[ClockSensorDescription, ...] = (
    ClockSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value=lambda s: s.temperature,
        attr="temperature",
        from_advertisements=True,
    ),
    ClockSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value=lambda s: s.humidity,
        attr="humidity",
        from_advertisements=True,
    ),
    ClockSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.battery,
        attr="battery",
        from_advertisements=True,
    ),
    ClockSensorDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda s: s.rssi,
        from_advertisements=True,
    ),
    ClockSensorDescription(
        key="drift",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.drift,
    ),
    ClockSensorDescription(
        key="last_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.last_check,
    ),
    ClockSensorDescription(
        key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.last_sync,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Lywsd02ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(ClockSensor(entry.runtime_data, d) for d in SENSORS)


class ClockSensor(Lywsd02Entity, RestoreSensor):
    entity_description: ClockSensorDescription

    def __init__(self, coordinator, description: ClockSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        attr = self.entity_description.attr
        if attr and getattr(self.coordinator.data, attr) is None:
            if (last := await self.async_get_last_sensor_data()) is not None:
                try:
                    setattr(self.coordinator.data, attr, float(last.native_value))
                except (TypeError, ValueError):
                    pass

    @property
    def available(self) -> bool:
        if self.entity_description.from_advertisements:
            return self.coordinator.data.present
        return True

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)

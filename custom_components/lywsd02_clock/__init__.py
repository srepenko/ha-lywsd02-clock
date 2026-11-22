"""Xiaomi LYWSD02 Clock: reliable time sync for the Mijia BLE e-ink clock."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.components import persistent_notification
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FORCE,
    DOMAIN,
    IDENTIFY_SECONDS,
    SERVICE_IDENTIFY_ALL,
    SERVICE_READ_SENSORS,
    SERVICE_SYNC_ALL,
    STARTUP_DELAY,
    STARTUP_STAGGER,
)
from .coordinator import Lywsd02Coordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

Lywsd02ConfigEntry = ConfigEntry[Lywsd02Coordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain service once."""

    async def sync_all(call: ServiceCall) -> None:
        force = call.data[ATTR_FORCE]
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            await entry.runtime_data.async_check_and_sync(force=force)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_ALL,
        sync_all,
        schema=vol.Schema({vol.Optional(ATTR_FORCE, default=True): cv.boolean}),
    )

    async def read_sensors(call: ServiceCall) -> ServiceResponse:
        result = {}
        for entry in sorted(hass.config_entries.async_loaded_entries(DOMAIN), key=lambda e: e.title):
            c = entry.runtime_data
            ok = await c.async_read_sensors()
            result[entry.title] = {
                "ok": ok,
                "temperature": c.data.temperature,
                "humidity": c.data.humidity,
                "battery": c.data.battery,
            }
        return {"clocks": result}

    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_SENSORS,
        read_sensors,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def identify_all(call: ServiceCall) -> ServiceResponse:
        devices = dr.async_get(hass)
        areas = ar.async_get(hass)
        result: dict[str, dict[str, str | None]] = {}
        lines = []
        entries = sorted(
            hass.config_entries.async_loaded_entries(DOMAIN), key=lambda e: (e.title, e.entry_id)
        )
        for entry in entries:
            coordinator = entry.runtime_data
            area = None
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
                if device.area_id and (a := areas.async_get_area(device.area_id)):
                    area = a.name
            try:
                label = await coordinator.async_identify()
                status = None
            except Exception as err:  # noqa: BLE001 - report per clock
                label, status = coordinator.identify_label(), f"not reachable: {err}"
            result[entry.title] = {"shows": label, "area": area, "error": status}
            lines.append(
                f"**{label}** — {entry.title}"
                + (f" ({area})" if area else "")
                + (f" — {status}" if status else "")
            )
        persistent_notification.async_create(
            hass,
            "\n".join(lines) + f"\n\n(°F + number for {IDENTIFY_SECONDS} s, then the time is restored)",
            title="LYWSD02: which clock is which",
            notification_id=f"{DOMAIN}_identify",
        )
        return {"clocks": result}

    hass.services.async_register(
        DOMAIN,
        SERVICE_IDENTIFY_ALL,
        identify_all,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Lywsd02ConfigEntry) -> bool:
    """Set up one clock."""
    coordinator = Lywsd02Coordinator(hass, entry, entry.data[CONF_ADDRESS].upper())
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_passive()

    index = sorted(e.entry_id for e in hass.config_entries.async_entries(DOMAIN)).index(
        entry.entry_id
    )

    @callback
    def _started(_hass: HomeAssistant) -> None:
        coordinator.async_schedule(STARTUP_DELAY + index * STARTUP_STAGGER)

    entry.async_on_unload(async_at_started(hass, _started))
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: Lywsd02ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Lywsd02ConfigEntry) -> bool:
    """Unload a clock."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

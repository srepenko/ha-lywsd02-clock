"""Config flow: Bluetooth discovery, manual pick, options."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)

from .const import (
    CONF_FALLBACK,
    CONF_MAX_DRIFT,
    CONF_SYNC_TIME,
    DEFAULT_FALLBACK,
    DEFAULT_MAX_DRIFT,
    DEFAULT_SYNC_TIME,
    DOMAIN,
)
from .device import is_lywsd02


def _title(address: str) -> str:
    return f"LYWSD02 {address.replace(':', '')[-4:].upper()}"


class Lywsd02ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._candidates: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        if not is_lywsd02(discovery_info.name, discovery_info.service_data):
            return self.async_abort(reason="not_supported")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": _title(discovery_info.address)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        address = self._discovery.address.upper()
        if user_input is not None:
            return self.async_create_entry(title=_title(address), data={CONF_ADDRESS: address})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": _title(address), "address": address},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=_title(address), data={CONF_ADDRESS: address})

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            address = info.address.upper()
            if address in configured or address in self._candidates:
                continue
            if is_lywsd02(info.name, info.service_data):
                self._candidates[address] = f"{_title(address)} ({address}, {info.rssi} dBm)"
        if not self._candidates:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._candidates)}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return Lywsd02OptionsFlow()


class Lywsd02OptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SYNC_TIME, default=opts.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME)
                    ): TimeSelector(),
                    vol.Required(
                        CONF_MAX_DRIFT, default=opts.get(CONF_MAX_DRIFT, DEFAULT_MAX_DRIFT)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=300, step=1, unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_FALLBACK, default=opts.get(CONF_FALLBACK, DEFAULT_FALLBACK)
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=60, max=3600, step=60, unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

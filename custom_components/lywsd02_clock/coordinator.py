"""Coordinator: schedules and performs clock checks / time syncs over BLE."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta
import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FALLBACK,
    CONF_MAX_DRIFT,
    CONF_SYNC_TIME,
    CONNECT_ATTEMPTS,
    DEFAULT_FALLBACK,
    DEFAULT_MAX_DRIFT,
    DEFAULT_SYNC_TIME,
    DOMAIN,
    IDENTIFY_SECONDS,
    NOTIFY_TIMEOUT,
    OPERATION_TIMEOUT,
    RETRY_DELAYS,
    UUID_BATTERY,
    UUID_DATA,
    UUID_TIME,
    UNIT_FAHRENHEIT,
    UUID_UNITS,
    XIAOMI_SERVICE_UUID,
)
from .device import (
    decode_sensor_data,
    decode_time,
    decode_unit,
    drift_seconds,
    encode_display,
    encode_time,
    encode_unit,
    identify_code,
    parse_mibeacon,
)

_LOGGER = logging.getLogger(__name__)


class ClockUnavailable(Exception):
    """The clock is not reachable by any connectable Bluetooth adapter/proxy."""


@dataclass(slots=True)
class ClockState:
    """What we know about one clock."""

    drift: int | None = None  # seconds, measured before the last sync decision
    drift_after: int | None = None  # seconds, read back after the last write
    last_check: datetime | None = None
    last_sync: datetime | None = None
    last_attempt: datetime | None = None
    unit: str | None = None
    battery: float | None = None  # % (advertisements, refreshed over GATT on each check)
    temperature: float | None = None  # °C from advertisements
    humidity: float | None = None  # % from advertisements
    rssi: int | None = None
    last_seen: datetime | None = None
    present: bool = True  # False once Bluetooth reports the clock unavailable
    values_at: datetime | None = None  # last temperature/humidity reading (any source)
    last_gatt_read: datetime | None = None  # last fallback read over GATT
    error: str | None = None
    consecutive_failures: int = 0
    history: list[str] = field(default_factory=list)  # short log for diagnostics


def _connection_lock(hass: HomeAssistant) -> asyncio.Lock:
    """One BLE connection at a time across all clocks (gentle on adapters/proxies)."""
    data = hass.data.setdefault(DOMAIN, {})
    if "lock" not in data:
        data["lock"] = asyncio.Lock()
    return data["lock"]


class Lywsd02Coordinator(DataUpdateCoordinator[ClockState]):
    """Owns the schedule and the BLE operations of one clock."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {address}",
            update_interval=None,  # driven by our own schedule, not polling
        )
        self.address = address
        self.data = ClockState()
        self._retry_unsub: CALLBACK_TYPE | None = None
        self._busy = False
        self._gatt_read_busy = False
        self._pending_unit: str | None = None  # unit to restore after identify
        self._identify_until: datetime | None = None
        self._started_at = dt_util.utcnow()

    async def _async_update_data(self) -> ClockState:
        """No polling: entities just read the current state."""
        return self.data

    # ----------------------------------------------------------------- schedule
    @property
    def max_drift(self) -> int:
        return int(self.config_entry.options.get(CONF_MAX_DRIFT, DEFAULT_MAX_DRIFT))

    @property
    def sync_time(self) -> dt_time:
        raw = self.config_entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME)
        return dt_time.fromisoformat(raw)

    @callback
    def async_schedule(self, startup_delay: float) -> None:
        """Daily check at the configured time + one check shortly after start."""
        t = self.sync_time
        # spread clocks over the minute so they don't all connect at once
        second = (int(self.address.replace(":", "")[-2:], 16) % 50) + 5
        self.config_entry.async_on_unload(
            async_track_time_change(
                self.hass, self._scheduled, hour=t.hour, minute=t.minute, second=second
            )
        )
        self.config_entry.async_on_unload(
            async_call_later(self.hass, startup_delay, self._scheduled)
        )
        self.config_entry.async_on_unload(self._cancel_retry)

    # ------------------------------------------------------- advertisements
    @callback
    def async_start_passive(self) -> None:
        """Listen to the clock's MiBeacon advertisements (temperature/humidity/battery)."""
        self.config_entry.async_on_unload(
            bluetooth.async_register_callback(
                self.hass,
                self._on_advertisement,
                bluetooth.BluetoothCallbackMatcher(address=self.address, connectable=False),
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        self.config_entry.async_on_unload(
            bluetooth.async_track_unavailable(
                self.hass, self._on_unavailable, self.address, connectable=False
            )
        )
        self.config_entry.async_on_unload(
            async_track_time_interval(self.hass, self._watchdog, timedelta(seconds=60))
        )
        # values already in the Bluetooth cache (e.g. right after a reload)
        if info := bluetooth.async_last_service_info(self.hass, self.address, connectable=False):
            self._on_advertisement(info, bluetooth.BluetoothChange.ADVERTISEMENT)

    @callback
    def _on_advertisement(
        self, info: bluetooth.BluetoothServiceInfoBleak, change: bluetooth.BluetoothChange
    ) -> None:
        state = self.data
        state.rssi = info.rssi
        state.last_seen = dt_util.utcnow()
        changed = not state.present
        state.present = True
        raw = info.service_data.get(XIAOMI_SERVICE_UUID)
        if raw:
            parsed = parse_mibeacon(raw)
            if "temperature" in parsed or "humidity" in parsed:
                state.values_at = state.last_seen
            for key, value in parsed.items():
                if getattr(state, key) != value:
                    setattr(state, key, value)
                    changed = True
        if changed:
            self.async_set_updated_data(state)

    @callback
    def _on_unavailable(self, _info: bluetooth.BluetoothServiceInfoBleak) -> None:
        self.data.present = False
        self.async_set_updated_data(self.data)

    @property
    def fallback_after(self) -> int:
        return int(self.config_entry.options.get(CONF_FALLBACK, DEFAULT_FALLBACK))

    @callback
    def _watchdog(self, _now: datetime) -> None:
        """No temperature/humidity advertised for a while -> ask the clock directly."""
        now = dt_util.utcnow()
        limit = timedelta(seconds=self.fallback_after)
        since = self.data.values_at or self._started_at
        last = self.data.last_gatt_read
        if now - since < limit or (last and now - last < limit):
            return
        if self._busy or self._gatt_read_busy:
            return
        self.config_entry.async_create_background_task(
            self.hass, self.async_read_sensors(), f"{DOMAIN}_{self.address}_read"
        )

    async def async_read_sensors(self) -> bool:
        """Read temperature/humidity (and battery) over a GATT connection."""
        self._gatt_read_busy = True
        state = self.data
        state.last_gatt_read = dt_util.utcnow()

        async def op(client: BleakClientWithServiceCache) -> tuple[float, float]:
            try:
                data = await client.read_gatt_char(UUID_DATA)
                if len(data) >= 3:
                    return decode_sensor_data(data)
            except BleakError:
                pass
            loop = asyncio.get_running_loop()
            got: asyncio.Future[bytes] = loop.create_future()

            def on_notify(_char, payload: bytearray) -> None:
                if not got.done():
                    got.set_result(bytes(payload))

            await client.start_notify(UUID_DATA, on_notify)
            try:
                async with asyncio.timeout(NOTIFY_TIMEOUT):
                    data = await got
            finally:
                try:
                    await client.stop_notify(UUID_DATA)
                except BleakError:
                    pass
            result = decode_sensor_data(data)
            await self._read_extras(client)
            return result

        try:
            temperature, humidity = await self._run(op)
        except (ClockUnavailable, BleakNotFoundError, BleakError, TimeoutError, OSError, ValueError) as err:
            self._log(f"GATT read failed: {type(err).__name__}: {err}"[:120])
            _LOGGER.debug("%s: GATT sensor read failed: %s", self.address, err)
            ok = False
        else:
            state.temperature, state.humidity = temperature, humidity
            state.values_at = dt_util.utcnow()
            self._log(f"GATT read {temperature:.1f}°C {humidity:.0f}%")
            ok = True
        finally:
            self._gatt_read_busy = False
            self.async_set_updated_data(state)
        return ok

    # ----------------------------------------------------------------- identify
    def identify_index(self) -> int:
        entries = sorted(
            self.hass.config_entries.async_entries(DOMAIN), key=lambda e: (e.title, e.entry_id)
        )
        return [e.entry_id for e in entries].index(self.config_entry.entry_id)

    def identify_label(self) -> str:
        return "%02d:%02d" % identify_code(self.identify_index())

    async def async_identify(self) -> str:
        """Show this clock's number (01:11, 02:22, ...) and °F for a minute, then restore."""
        hour, minute = identify_code(self.identify_index())

        async def op(client: BleakClientWithServiceCache) -> None:
            unit = decode_unit(await client.read_gatt_char(UUID_UNITS))
            if self._pending_unit is None:
                self._pending_unit = unit
            await client.write_gatt_char(UUID_TIME, encode_display(hour, minute, dt_util.utcnow()))
            await client.write_gatt_char(UUID_UNITS, encode_unit(UNIT_FAHRENHEIT))

        await self._run(op)
        self._identify_until = dt_util.utcnow() + timedelta(seconds=IDENTIFY_SECONDS)
        label = "%02d:%02d" % (hour, minute)
        self._log(f"identify: showing {label}")
        self.config_entry.async_on_unload(
            async_call_later(self.hass, IDENTIFY_SECONDS, self._identify_done)
        )
        return label

    @callback
    def _identify_done(self, _now: datetime) -> None:
        self._identify_until = None
        self.config_entry.async_create_background_task(
            self.hass, self.async_check_and_sync(force=True), f"{DOMAIN}_{self.address}_restore"
        )

    @callback
    def _cancel_retry(self) -> None:
        if self._retry_unsub:
            self._retry_unsub()
            self._retry_unsub = None

    @callback
    def _scheduled(self, _now: datetime | None = None) -> None:
        self.config_entry.async_create_background_task(
            self.hass, self.async_check_and_sync(force=False), f"{DOMAIN}_{self.address}"
        )

    @callback
    def _schedule_retry(self) -> None:
        self._cancel_retry()
        n = self.data.consecutive_failures
        if n == 0 or n > len(RETRY_DELAYS):
            return  # give up until the next daily run
        delay = RETRY_DELAYS[n - 1]
        _LOGGER.debug("%s: retry in %s s", self.address, delay)
        self._retry_unsub = async_call_later(self.hass, delay, self._scheduled)

    # --------------------------------------------------------------- BLE work
    async def _connect(self) -> BleakClientWithServiceCache:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise ClockUnavailable("not seen by any connectable Bluetooth adapter")
        return await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.address,
            max_attempts=CONNECT_ATTEMPTS,
            ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            or ble_device,
        )

    async def _run(self, op) -> Any:
        """Connect, run op(client), disconnect; serialised and time-limited."""
        async with _connection_lock(self.hass):
            async with asyncio.timeout(OPERATION_TIMEOUT):
                client = await self._connect()
                try:
                    return await op(client)
                except BleakError:
                    # stale GATT cache is a classic cause of "characteristic not found"
                    await client.clear_cache()
                    raise
                finally:
                    await client.disconnect()

    async def _read_extras(self, client: BleakClientWithServiceCache) -> None:
        """Unit and battery are nice to have; failures here are not fatal."""
        try:
            self.data.unit = decode_unit(await client.read_gatt_char(UUID_UNITS))
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("%s: unit read failed: %s", self.address, err)
        try:
            raw = await client.read_gatt_char(UUID_BATTERY)
            if raw:
                self.data.battery = float(raw[0])
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("%s: battery read failed: %s", self.address, err)

    async def async_check_and_sync(self, force: bool) -> bool | None:
        """Read the clock; write the time if it drifted (or always when forced).

        Returns True on success, False on failure, None if a run was already going.
        """
        if self._busy:
            return None
        if not force and self._identify_until and dt_util.utcnow() < self._identify_until:
            return None  # the clock is showing its number; the restore will sync it
        self._busy = True
        self._cancel_retry()
        state = self.data
        state.last_attempt = dt_util.utcnow()

        async def op(client: BleakClientWithServiceCache) -> str:
            now = dt_util.utcnow()
            offset = dt_util.now().utcoffset() or timedelta(0)
            before = drift_seconds(decode_time(await client.read_gatt_char(UUID_TIME)), now, offset)
            if self._pending_unit is None:  # after "identify" the drift is meaningless
                state.drift = before
            state.last_check = now
            action = f"drift {before:+d}s"
            if force or abs(before) > self.max_drift:
                now = dt_util.utcnow()
                offset = dt_util.now().utcoffset() or timedelta(0)
                await client.write_gatt_char(UUID_TIME, encode_time(now, offset))
                after = drift_seconds(
                    decode_time(await client.read_gatt_char(UUID_TIME)), dt_util.utcnow(), offset
                )
                state.drift_after = after
                state.last_sync = dt_util.utcnow()
                action += f", synced (now {after:+d}s)"
                if abs(after) > max(self.max_drift, 5):  # BLE latency on weak links
                    raise BleakError(f"time did not stick (still {after:+d}s)")
            if self._pending_unit is not None:
                await client.write_gatt_char(UUID_UNITS, encode_unit(self._pending_unit))
                self._pending_unit = None
                action += ", unit restored"
            await self._read_extras(client)
            return action

        try:
            result = await self._run(op)
        except (ClockUnavailable, BleakNotFoundError, BleakError, TimeoutError, OSError, ValueError) as err:
            state.consecutive_failures += 1
            state.error = f"{type(err).__name__}: {err}"[:200]
            self._log(f"failed ({state.consecutive_failures}): {state.error}")
            log = _LOGGER.warning if state.consecutive_failures > len(RETRY_DELAYS) else _LOGGER.debug
            log("%s: clock check failed (%s attempts): %s", self.address, state.consecutive_failures, state.error)
            self._schedule_retry()
            ok = False
        else:
            state.consecutive_failures = 0
            state.error = None
            self._log(result)
            _LOGGER.debug("%s: %s", self.address, result)
            ok = True
        finally:
            self._busy = False
            self.async_set_updated_data(state)
        return ok

    async def async_set_unit(self, unit: str) -> None:
        """Switch the clock between °C and °F."""

        async def op(client: BleakClientWithServiceCache) -> None:
            await client.write_gatt_char(UUID_UNITS, encode_unit(unit))
            self.data.unit = decode_unit(await client.read_gatt_char(UUID_UNITS))

        await self._run(op)
        self._log(f"unit -> {unit}")
        self.async_set_updated_data(self.data)

    def _log(self, msg: str) -> None:
        stamp = dt_util.now().strftime("%m-%d %H:%M:%S")
        self.data.history = ([f"{stamp} {msg}"] + self.data.history)[:20]

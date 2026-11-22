"""BLE protocol of the LYWSD02 clock (no Home Assistant state here)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import struct

from .const import (
    LYWSD02_LOCAL_NAME,
    LYWSD02_PRODUCT_IDS,
    UNIT_CELSIUS,
    UNIT_FAHRENHEIT,
    XIAOMI_SERVICE_UUID,
)


@dataclass(slots=True)
class ClockTime:
    """Time as stored in the clock."""

    timestamp: int  # unix seconds
    tz_hours: int  # offset the clock adds before display

    @property
    def displayed_epoch(self) -> int:
        """Seconds the clock shows, expressed as 'local epoch'."""
        return self.timestamp + self.tz_hours * 3600


def encode_time(now_utc: datetime, utc_offset: timedelta) -> bytes:
    """Pack the current time for the clock.

    The clock only supports whole-hour offsets, so a remainder (e.g. +05:30)
    is folded into the timestamp; the displayed time is still correct.
    """
    offset = int(utc_offset.total_seconds())
    hours = offset // 3600
    remainder = offset - hours * 3600
    return struct.pack("<Ib", int(now_utc.timestamp() + 0.5) + remainder, hours)


def decode_time(data: bytes | bytearray) -> ClockTime:
    """Unpack the time characteristic."""
    if len(data) >= 5:
        ts, tz = struct.unpack_from("<Ib", data)
    elif len(data) >= 4:
        (ts,) = struct.unpack_from("<I", data)
        tz = 0
    else:
        raise ValueError(f"unexpected time payload: {bytes(data).hex()}")
    return ClockTime(ts, tz)


def drift_seconds(clock: ClockTime, now_utc: datetime, utc_offset: timedelta) -> int:
    """How far the displayed time is ahead (+) or behind (-) the real local time."""
    real_local = int(now_utc.timestamp()) + int(utc_offset.total_seconds())
    return clock.displayed_epoch - real_local


def decode_unit(data: bytes | bytearray) -> str:
    """0x01 means Fahrenheit, anything else Celsius (the clock uses 0xFF)."""
    return UNIT_FAHRENHEIT if data and data[0] == 0x01 else UNIT_CELSIUS


def encode_unit(unit: str) -> bytes:
    """Pack the temperature unit."""
    return b"\x01" if unit == UNIT_FAHRENHEIT else b"\xff"


def decode_sensor_data(data: bytes | bytearray) -> tuple[float, float]:
    """GATT sensor characteristic: int16 LE temperature x100, uint8 humidity."""
    if len(data) < 3:
        raise ValueError(f"unexpected sensor payload: {bytes(data).hex()}")
    temp, hum = struct.unpack_from("<hB", data)
    return temp / 100, float(hum)


def identify_code(index: int) -> tuple[int, int]:
    """Number shown by clock #index (0-based) while identifying: 01:11, 02:22, ... 05:55, 06:06 ..."""
    n = index % 23 + 1
    return n, (n * 11) % 60


def encode_display(hour: int, minute: int, now_utc: datetime) -> bytes:
    """Time payload that makes the clock display HH:MM (date: today, tz offset 0)."""
    midnight = int(now_utc.timestamp()) // 86400 * 86400
    return struct.pack("<Ib", midnight + hour * 3600 + minute * 60, 0)


def parse_mibeacon(data: bytes | bytearray) -> dict[str, float]:
    """Decode an unencrypted Xiaomi MiBeacon frame as sent by the LYWSD02.

    Layout: frame control (2) | product id (2) | counter (1) | [mac (6)]
    | [capability (1) (+2 if cap & 0x20)] | [object id (2) | length (1) | value].
    Returns any of: temperature (°C), humidity (%), battery (%).
    """
    out: dict[str, float] = {}
    if len(data) < 5:
        return out
    (frctrl,) = struct.unpack_from("<H", data, 0)
    if frctrl & 0x0008:  # encrypted frame: not used by the LYWSD02
        return out
    i = 5
    if frctrl & 0x0010:
        i += 6
    if frctrl & 0x0020:
        if i >= len(data):
            return out
        capability = data[i]
        i += 1
        if capability & 0x20:
            i += 2
    if not frctrl & 0x0040:
        return out
    while i + 3 <= len(data):
        obj_id, length = struct.unpack_from("<HB", data, i)
        i += 3
        value = data[i : i + length]
        i += length
        if len(value) < length:
            break
        if obj_id == 0x1004 and length == 2:
            out["temperature"] = struct.unpack("<h", value)[0] / 10
        elif obj_id == 0x1006 and length == 2:
            out["humidity"] = struct.unpack("<H", value)[0] / 10
        elif obj_id == 0x100A and length >= 1:
            out["battery"] = float(value[0])
        elif obj_id == 0x100D and length == 4:
            t, h = struct.unpack("<hH", value)
            out["temperature"] = t / 10
            out["humidity"] = h / 10
    return out


def is_lywsd02(name: str | None, service_data: dict[str, bytes]) -> bool:
    """Recognise a LYWSD02 from its advertisement."""
    if name and name.upper().startswith(LYWSD02_LOCAL_NAME):
        return True
    data = service_data.get(XIAOMI_SERVICE_UUID)
    if data and len(data) >= 4:
        (product_id,) = struct.unpack_from("<H", data, 2)
        return product_id in LYWSD02_PRODUCT_IDS
    return False

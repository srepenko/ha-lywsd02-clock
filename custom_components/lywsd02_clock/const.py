"""Constants for the Xiaomi LYWSD02 Clock integration."""

from __future__ import annotations

DOMAIN = "lywsd02_clock"

# GATT characteristics of the LYWSD02 (Xiaomi Mijia BLE e-ink clock with thermometer).
UUID_TIME = "ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6"  # r/w: uint32 LE unix time + int8 tz offset (h)
UUID_UNITS = "ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6"  # r/w: 0x01 = Fahrenheit, 0xFF = Celsius
UUID_BATTERY = "ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6"  # r: uint8 battery %
UUID_DATA = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"  # r/notify: int16 LE temp/100 + uint8 humidity

UNIT_CELSIUS = "celsius"
UNIT_FAHRENHEIT = "fahrenheit"

# Xiaomi MiBeacon service data: frame control (2 bytes) + product id (2 bytes, LE).
XIAOMI_SERVICE_UUID = "0000fe95-0000-1000-8000-00805f9b34fb"
LYWSD02_PRODUCT_IDS = {0x045B}
LYWSD02_LOCAL_NAME = "LYWSD02"

CONF_SYNC_TIME = "sync_time"
CONF_MAX_DRIFT = "max_drift"
CONF_FALLBACK = "fallback_after"
DEFAULT_SYNC_TIME = "04:05:00"  # after the EU DST switch (03:00/04:00 local)
DEFAULT_MAX_DRIFT = 2  # seconds
DEFAULT_FALLBACK = 300  # s without advertised readings before reading over GATT
NOTIFY_TIMEOUT = 15  # s to wait for a sensor notification
IDENTIFY_SECONDS = 60  # how long the clock shows its number

STARTUP_DELAY = 90  # seconds after HA start before the first check
STARTUP_STAGGER = 45  # extra seconds per configured clock
RETRY_DELAYS = (300, 900, 1800)  # seconds between attempts after a failure
OPERATION_TIMEOUT = 90  # seconds for one connect/read/write cycle
CONNECT_ATTEMPTS = 4

SERVICE_SYNC_ALL = "sync_all"
SERVICE_IDENTIFY_ALL = "identify_all"
SERVICE_READ_SENSORS = "read_sensors"
ATTR_FORCE = "force"

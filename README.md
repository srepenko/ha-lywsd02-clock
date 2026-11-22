# Xiaomi LYWSD02 Clock for Home Assistant

Keeps the time on **Xiaomi Mijia LYWSD02** e-ink BLE clocks (the square thermometer/hygrometer clock) correct — reliably, without hourly
automations and without log spam.

It is a complete integration for the clock: **temperature, humidity and battery** are decoded from the clock's own MiBeacon
advertisements (passive, no connection), and the **time and settings** are managed over a GATT connection. You don't need the
built-in Xiaomi BLE integration for these clocks (if you used it, remove the LYWSD02 entries there and, if you want to keep
history, rename the new entities to the old entity IDs).

## Features

- **Bluetooth discovery** and a config flow (no YAML, no MAC addresses to type).
- **Smart sync**: once a day (default 04:05, right after the EU DST switch) and shortly after Home Assistant starts, the clock is
  **read first**; the time is written only if it drifted more than the threshold (default 2 s), then read back to verify.
- **Correct time zone handling**: real UTC timestamp + the local UTC offset, as the clock expects (whole-hour offsets; a
  half-hour remainder is folded into the timestamp so the display is still right). DST changes are picked up by the daily check.
- **Reliable BLE**: `bleak-retry-connector` (works with local adapters and ESPHome Bluetooth proxies), GATT cache reset on errors,
  one connection at a time across all clocks, an overall timeout, and retries after 5 / 15 / 30 min when a clock is out of reach.
  Failures are logged at WARNING only after all retries are exhausted.
- Entities per clock:
  - **Temperature**, **Humidity**, **Battery** (from advertisements; last values are restored after a restart;
    unavailable when Bluetooth stops seeing the clock), **Signal strength** (disabled by default)
  - **Sync time** button (force write now)
  - **Show number** button (identify): the clock shows its number (01:11, 02:22, …) and °F for a minute, then
    the time and unit are restored — handy to find out which clock is in which room
  - **Clock drift** (s) — measured before the last sync decision
  - **Last check**, **Last time sync** (timestamps)
  - **Sync problem** binary sensor with `last_error`, `consecutive_failures` and a short history in its attributes
  - **Temperature unit** select (°C / °F, written to the clock)
- **Fallback reads**: if a clock advertises no temperature/humidity for 5 minutes (configurable), the values are read
  over a GATT connection (at most once per that interval).
- Services:
  - `lywsd02_clock.sync_all` (`force: true|false`)
  - `lywsd02_clock.read_sensors` — read temperature/humidity/battery from every clock now (returns the values)
  - `lywsd02_clock.identify_all` — every clock shows its own number for a minute; the mapping
    (number → clock → area) is shown as a notification and returned as the service response
- Options: daily check time, allowed drift, fallback read interval.
- Diagnostics download.

## Installation

### HACS (custom repository)
1. HACS → ⋮ → *Custom repositories* → add `https://github.com/srepenko/ha-lywsd02-clock`, type *Integration*.
2. Install **Xiaomi LYWSD02 Clock**, restart Home Assistant.

### Manual
Copy `custom_components/lywsd02_clock` into your `config/custom_components/` and restart Home Assistant.

Then: *Settings → Devices & services* — discovered clocks appear automatically, or *Add integration → Xiaomi LYWSD02 Clock*.

## Notes

- Requires a **connectable** Bluetooth adapter or an ESPHome Bluetooth proxy within range (RSSI better than about −85 dBm).
- Only the original **LYWSD02** (MiBeacon product id `0x045B`, advertised name `LYWSD02`) is supported.
- If you previously used an hourly automation calling `lywsd02.set_time`, remove it — this integration replaces it.

## Protocol (for reference)

| Characteristic | Access | Format |
|---|---|---|
| `ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6` time | read / write | `uint32` LE unix time + `int8` UTC offset in hours |
| `ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6` unit | read / write | `0xFF` = °C, `0x01` = °F |
| `ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6` battery | read | `uint8` % |

---

## Українською

Інтеграція тримає правильний час на годинниках-термометрах **Xiaomi LYWSD02**: раз на добу (типово о 04:05, одразу після переходу
на літній/зимовий час) і після запуску Home Assistant спершу **зчитує** час із годинника і записує новий, лише якщо він відійшов
більше ніж на поріг (типово 2 с), потім перевіряє. Надійне BLE-з'єднання з повторами (через 5 / 15 / 30 хв, якщо годинник
недосяжний), одне з'єднання за раз, автовиявлення по Bluetooth, кнопка «Синхронізувати час», сенсори відхилення та останньої
синхронізації, «Проблема синхронізації» з описом помилки, вибір °C/°F. Кнопка «Показати номер» і сервіс
«Показати номери на всіх» — годинники на хвилину показують 01:11, 02:22, … щоб знайти, де який. Якщо 5 хв немає даних
із реклами — температура й вологість зчитуються через з'єднання; сервіс «Запросити дані зараз». Температура, вологість і батарея — з рекламних пакетів
годинника (без з'єднання), тож вбудована Xiaomi BLE для цих годинників не потрібна.

## License

MIT

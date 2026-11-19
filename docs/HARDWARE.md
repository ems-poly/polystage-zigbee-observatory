# Hardware and flashing

[Back to the project](../README.md)

## Supported board

The initial implementation targets **SONOFF ZBBridge-P**, containing an ESP32 and a Texas Instruments CC2652P radio. Check the board markings; ZBBridge, ZBBridge-P, and newer products are not interchangeable targets.

The ESP32 handles BLE provisioning, Wi-Fi scanning, storage, and uploads. It communicates with the CC2652P over an internal UART. The radio's existing firmware provides the TI MAC energy-detect commands used here; changing its firmware is unnecessary for the demonstrated scanner.

The manufacturer's [product page and photograph](https://sonoff.tech/en-us/products/sonoff-zigbee-bridge-pro) help identify the enclosure. The [board configuration reference](https://templates.blakadder.com/sonoff_ZBBridge-P.html) documents the GPIO assignments used below. Photograph rights remain with SONOFF; no manufacturer image is redistributed as MIT-licensed project content.

## ESP32 connections

| GPIO | Connection | Use in this project |
|---|---|---|
| 27 | Case button | Input with pull-up; pressed = low |
| 2 | Blue indicator (firmware assignment) | Active-low output |
| 21 | Green indicator (firmware assignment) | Active-low output |
| 19 | CC2652P UART TX | ESP32 transmits to radio |
| 23 | CC2652P UART RX | ESP32 receives from radio |
| 15 | CC2652P reset | Pulsed low to restart the radio |
| 22 | CC2652P boot select | Held high for normal radio firmware |
| 0 | ESP32 boot strap | Hold low at power-on to enter ROM download mode |
| 4 | Buzzer | Unused |

The indicator outputs alternate in setup mode. The blue/green assignment follows the GPIO reference and observed board LED labels; independently confirm it on another board revision. See the [button and indicator reference](LED-STATUS.md) for status behavior. The case button is **GPIO27, not GPIO0**.

## Power and UART

Use the bridge's normal USB input with **5 V power**. A power bank is suitable for portable use once wireless operation has been verified.

For flashing, connect:

- Adapter **TX → ESP32 RX**.
- Adapter **RX ← ESP32 TX**.
- Adapter **GND ↔ board GND**.
- Adapter **DTR → GPIO0**, if using the supplied flashing workflow.

UART signalling must use **3.3 V logic**. When the board is powered through normal USB, leave the adapter's **3V3 power lead disconnected**. A 5 V adapter supply setting is not evidence that its signal pins are safe for the ESP32; check the adapter's logic level separately.

An adapter connection to ESP32 **EN/reset** is optional but changes whether entry to flashing mode can be automated. GPIO0/DTR alone cannot guarantee a reset into the ROM loader. The tested arrangement requires a physical power cycle while GPIO0 is held low.

## Flashing the ESP32

Flashing replaces the ESP32 application and its stored configuration. This repository does not distribute a backup of a factory image. Keep a vendor-supported recovery method if you need to restore stock behavior later.

1. Stop any serial monitor or UART collector using the adapter. The portable network receiver does not need UART access.
2. Install PlatformIO Core 6.2.0 with `pip install platformio==6.2.0`. Generate the private configuration with `configure_native.py`, then build `firmware-native/` with `pio run -d firmware-native`.
3. Select your serial port with `ZIGBEE_SERIAL_PORT` (for example, `export ZIGBEE_SERIAL_PORT=/dev/ttyUSB0`). Device paths vary by operating system; do not copy another machine's adapter identifier.
4. Run `python flash_native.py`. It waits for the ROM downloader while holding GPIO0 low.
5. If EN is not connected, unplug and reconnect the bridge's external USB power. Leave UART signals and ground connected.
6. Wait for the complete firmware hash verification and startup log. Do not interrupt power during erase or write.

The tested serial path uses the ESP32 ROM loader at 115200 baud, explicit SPI flash initialization, and 1 KiB transfer blocks. Larger helper transfers were unreliable on the test link. The flasher groups writes into sector-aligned **128 KiB chunks**, checks each chunk's hash, retries recoverable UART failures, and verifies each complete written image afterward.

A fresh install with `python flash_native.py` erases the ESP32 and writes its bootloader, partition table, boot selection data, and application. It does **not** program the CC2652P.

### Updating an existing native installation

When the current board already has this firmware's matching partition table, use:

```sh
python flash_native.py --application-only
```

This mode first verifies that the installed partition table matches the build. It refuses the update if the table differs. It then writes only the application, preserving ESP32 NVS Wi-Fi credentials and the LittleFS buffer. It still requires entry into the ROM loader, including a physical power cycle when EN/reset is not wired.

Use a fresh install when deliberately changing the partition layout, and expect its full ESP32 erase to remove saved credentials and buffered records. The application-only flag is not a migration mechanism between incompatible layouts.

The application partition is 3 MiB, with separate NVS, LittleFS, and coredump areas. The current layout does not provide a second application slot for normal OTA firmware updates.

## First startup

Before first BLE provisioning, native startup checks:

1. CC2652P command response.
2. Energy results for all sixteen channels.
3. ESP32 Wi-Fi access-point scanning.
4. BLE provisioning startup.

A successful startup includes `CC2652P ping OK`, `SELFTEST Zigbee=OK channels=16`, a Wi-Fi scan result, and `BLE_SETUP_READY`. These checks have been observed on hardware. Phone provisioning has also saved credentials in NVS, followed by a boot into normal survey mode. A real native survey has also reached the receiver over Wi-Fi with a valid capture timestamp and all sixteen Zigbee channels. An application-only update retained the provisioned Wi-Fi configuration.

The native phone-to-receiver flow is verified. The design does not require UART for surveys; removal of UART and sustained power-bank use still need a separate field test. Keep the bridge's USB power connected for portable surveys.

## CC2652P recovery boundary

This project uses the existing radio firmware. Do not install an unrelated CC2652P image simply to obtain energy readings. A different image can change UART commands, board-specific RF configuration, and serial bootloader access.

Any future radio-flashing work needs a separately verified board-specific image and recovery path. The scanner's supported installation procedure changes only the ESP32.

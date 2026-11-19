# Button and indicator reference

[Back to the project](../README.md) · [Hardware connections](HARDWARE.md) · [Troubleshooting](TROUBLESHOOTING.md)

## Button

The case button is GPIO27 with an internal pull-up: pressing it pulls the input low. It is separate from the ESP32 GPIO0 boot strap used during serial flashing.

| Action | Behavior |
|---|---|
| Short press while surveying | Increment the numbered survey point and clear its active test association |
| Hold for at least three seconds, then release | Restart into BLE Wi-Fi setup |

The firmware debounces the input. Network/storage operations may delay recognition; release the button after a setup hold. A button action is a request to change state, not confirmation that Wi-Fi setup or an upload succeeded.

## Indicator wiring

| Firmware indicator | ESP32 output | Electrical behavior |
|---|---|---|
| Blue | GPIO2 | Active low: driving low lights the LED |
| Green | GPIO21 | Active low: driving low lights the LED |

The firmware color assignment combines the documented GPIO roles with the observed board's LED labels. It should be independently checked on another board revision before relying on a color alone. There is no red status LED in this board's confirmed blue/green pair.

## Status patterns

These patterns describe the current firmware source and are deployed to the test unit. Their physical timing/color behavior has not yet been independently observed. An older installed build may only alternate the LEDs in setup and briefly pulse after a scan. Check the installed source revision before using this table to diagnose a unit.

| State | Indicator pattern | Timing |
|---|---|---|
| Boot/startup | Blue slow pulse | 1 second on, 250 ms off |
| BLE Wi-Fi setup | Blue and green alternate | 200 ms per color |
| Zigbee energy sweep | Blue double pulse | Two 80 ms flashes, separated by 80 ms; repeats every second |
| Wi-Fi access-point scan | Blue even blink | 600 ms on, 600 ms off |
| Wi-Fi connection attempt | Blue triple pulse | Three 100 ms flashes, separated by 100 ms; repeats every 2 seconds |
| Upload in progress | Green fast blink | 80 ms on, 170 ms off |
| At least one queued sample acknowledged; waiting for next survey | Green heartbeat | 100 ms flash every 3 seconds |
| No sample acknowledged in the upload pass | Green short flash, then blue long flash | Green 100 ms at the start; blue 1 second beginning 300 ms after the start; repeats every 3 seconds |
| Fatal/storage/radio error | Both LEDs flash together three times | Three 150 ms flashes with 150 ms spacing; repeats every 2 seconds |

A dedicated indicator task keeps the patterns running during blocking network operations. The displayed state can still change before you see a whole cycle, especially during a quick successful connection or upload.

## Interpret the pattern with the dashboard

A ready heartbeat means at least one queued sample was acknowledged in that pass; a backlog may still remain. The offline pattern can mean Wi-Fi failed, the receiver was unreachable, authentication failed, or no queued record was successfully sent.

An upload blink means an upload is being attempted. A successful receiver acknowledgement and fresh dashboard record are stronger evidence than Wi-Fi association or a successful radio scan. Use the last upload/capture times, queue information, and serial errors alongside the indicators.

Alternating setup lights mean the unit is in the setup path; they do not prove that the phone has accepted the QR or supplied working Wi-Fi credentials. Both-color error pulses require the startup/error log to distinguish radio, storage, and other fatal failures.

# Troubleshooting

[Back to the project](../README.md)

## No serial response

Confirm the board has normal USB power, UART logic is 3.3 V, and ground is shared. Adapter TX connects to board RX and adapter RX to board TX. When using normal USB power, leave the adapter's 3V3 supply wire disconnected.

Check the selected serial port and close any other monitor or collector using it. The portable receiver does not need UART; the earlier UART collector does.

## ROM flashing never starts

The ESP32 samples GPIO0 during the appropriate reset. Connecting DTR to GPIO0 does not itself provide an EN/reset connection. With the tested arrangement, start the flasher, then power-cycle the external USB supply while GPIO0 is held low. The case button is GPIO27 and cannot substitute for GPIO0.

A normal software restart may boot the existing application again. Do not mistake permission to flash for evidence that the hardware has entered the ROM loader.

## A UART write fails partway through

Keep power stable and avoid disturbing the signal wiring. The reliable test setup used the ROM loader, explicit SPI attachment, and small blocks; larger helper transfers were unreliable.

The installer verifies sector-aligned 128 KiB chunks, retries recoverable UART errors, and checks the **entire image hash** afterward. If it reports a terminal failure, leave the board powered and inspect the error before restarting the installation. Use `--application-only` only when updating an existing native installation with a matching partition table; a fresh installation performs a full ESP32 erase. Do not boot a partially written image or treat a progress percentage as successful verification.

## CC2652P ping or energy self-test fails

Confirm the exact bridge model and board-specific UART/reset mapping. GPIO19 is ESP32 TX, GPIO23 RX, GPIO15 radio reset, and GPIO22 must remain high for normal radio execution. The native startup allows delayed responses and attempts to skip the radio bootloader before retrying.

Check for a complete 16-channel successful callback rather than interpreting zeros, a partial response, or a timeout as a quiet environment. A radio error remains an error, not a generated measurement. Do not replace radio firmware as a first troubleshooting step.

## BLE device does not appear

Wait for the radio/Wi-Fi startup self-tests and alternating setup LEDs. Use **ESP BLE Prov**, with Bluetooth access enabled for that app. The phone camera alone does not provision the device.

An already configured bridge starts normal surveys without BLE. Hold the case button for three seconds and release it to request setup. Keep the phone close while provisioning and check that you are using the QR generated for this unit. BLE service startup and saved phone-provisioned credentials have been observed on hardware. The native survey-to-receiver wireless upload has also been verified. If your unit fails here, compare its configuration and error messages with those separate startup stages.

## Wi-Fi setup fails

Select a **2.4 GHz** network supported by the original ESP32. Verify the entered credentials, signal strength, and router restrictions. A phone connected on 5 GHz can still configure a compatible 2.4 GHz network, but the bridge cannot join a 5 GHz-only SSID.

The QR includes the BLE service name and proof of possession; it does not contain the Wi-Fi password. After a failed attempt, re-enter setup and retry with the correct details. Avoid posting the QR or credentials in an issue.

## BLE succeeds but the dashboard receives nothing

Check that the receiver computer is awake, running in portable mode, and listening on port 8767. Its compiled receiver address must still be valid. DHCP address changes, local firewall rules, guest/client isolation, or a VPN can prevent access.

Distinguish a successful Wi-Fi association from a successful authenticated receiver upload. Serial startup and scan messages help locate the failing stage. Do not publish upload tokens or device configuration while reporting the problem.

## Startup stops at filesystem initialization

The partition table and the LittleFS mount must use the same partition label. This project names its filesystem partition `littlefs`; an Arduino default mount that searches for `spiffs` will fail even though a valid LittleFS partition exists. Use the current firmware and its matching partition table together.

On a new or freshly erased filesystem, an initial mount failure followed by successful formatting and continued startup can be expected. A persistent initialization failure, reboot loop, or absence of subsequent surveys is different and needs investigation.

A successful application flash does not prove that the storage partition mounted. Check startup messages and actual uploads after updating. If only the application is reflashed, preserve a compatible partition table and inspect any queue-format changes before erasing data.

## The dashboard is stale or history has gaps

Review capture times, upload times, coverage, radio errors, and the dropped-record counter. Buffered samples retain their original capture times; their upload time is not evidence of a current measurement. Records captured before clock synchronization remain unplotted because their wall-clock time is unknown.

The on-device buffer is bounded, and prolonged outages can discard older records. Keep the receiver running for longer surveys. Power loss and moving the unit can also explain gaps.

## Button presses seem delayed

The firmware debounces the input and requires a sustained three-second hold for setup. Release the button after the hold. Some network and storage operations block briefly, so the current implementation does not guarantee immediate response to every very short tap.

Physical button/LED behavior is still part of field validation. Record the operation being performed and whether a waypoint or setup message appeared in serial output.

## Energy is high but the network works

High sampled energy alone is not a fault. Ordinary traffic, nearby Wi-Fi, and other emitters share the band. The scanner cannot identify a transmitter from an energy value. Compare repeated symptoms and controlled conditions at the same physical location.

## Energy is low but a device is offline

Sequential sweeps can miss short interference bursts. The scanner's position may differ from the affected link, or that link may use a band the scanner cannot observe. Commissioning, battery condition, firmware, routing, antenna placement, and device faults can also produce missing readings.

For a HAN, confirm the affected link's band and actual association state through the relevant equipment or supplier. This project cannot commission a meter, read consumption, or diagnose an 868 MHz link.

## Sharing a useful issue

Include the board model, source revision, software versions, reproduction steps, and sanitized error messages. Describe exact observations and timing. Prefer synthetic samples to household exports. Remove network names/BSSIDs, addresses, local paths, meter/customer details, tokens, access codes, and QR codes before sharing.

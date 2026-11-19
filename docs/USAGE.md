# Setup and RF surveys

[Back to the project](../README.md)

## Receiver setup

Install the Python dependencies in a virtual environment. Install PlatformIO Core 6.2.0 separately when building firmware, then generate the device configuration:

```sh
pip install -r requirements.txt
pip install platformio==6.2.0
python configure_native.py --receiver 'http://RECEIVER-LAN-IP:8767'
```

Replace `RECEIVER-LAN-IP` with the computer's reachable address or hostname on the same local network that the bridge will join. Keep the URL quoted in the shell command. This address is compiled into the device header. A router DHCP reservation helps keep it stable; changing it requires regenerating configuration and rebuilding/flashing the ESP32.

The generator creates an upload token, dashboard code, BLE proof of possession, provisioning QR, and ignored firmware header. Treat these files as private. The QR is an onboarding credential, even though it contains no home Wi-Fi password.

The generator also selects portable mode in the ignored `data/transport.json` file. Start the service:

```sh
python start.py
```

The local dashboard is **http://127.0.0.1:8765**. The LAN receiver listens on port **8767**. Keep the computer awake and allow that port through its local firewall. The bridge and phone must be able to reach the receiver; a guest network with client isolation can prevent this even when all devices have internet access.

## BLE Wi-Fi provisioning

1. Power the bridge through its normal USB input. On an unconfigured unit, setup follows the startup self-tests.
2. To change an existing Wi-Fi configuration, hold the case button for **three seconds**, then release it. The ESP32 restarts into setup.
3. Wait for alternating indicator LEDs.
4. Open Espressif's **ESP BLE Prov** app on the phone. Its source and app information are available from the official [iOS](https://github.com/espressif/esp-idf-provisioning-ios) and [Android](https://github.com/espressif/esp-idf-provisioning-android) projects.
5. Scan the provisioning QR shown on the computer's local dashboard. If scanning is unavailable, use the displayed service name and proof of possession.
6. Enter the **2.4 GHz Wi-Fi** network and password in the app. These credentials are stored in the ESP32's Wi-Fi configuration, not sent as a chat message or saved in the project's receiver configuration.
7. After successful provisioning, the unit restarts into survey mode. BLE is inactive during normal collection.

The standard QR tells the provisioning app which BLE device to contact and how to authenticate it. Scanning with the phone camera alone does not transfer credentials, and the app cannot automatically read every saved Wi-Fi password from the phone.

## Check the indicators

The [LED reference](LED-STATUS.md) describes distinct patterns for setup, Zigbee sweeps, Wi-Fi scans, connecting, uploads, idle, offline, and errors. Expanded status patterns are deployed to the test unit; physical timing/color observation is still pending. Older installed firmware may show fewer patterns.

## Confirm portable operation

Before relying on a power-bank survey, verify all of the following:

- The dashboard receives fresh uploads, with an actual device address and capture timestamps.
- All sixteen Zigbee channels have readings, and the radio-error field is clear.
- Wi-Fi results appear after each quiet Zigbee measurement phase.
- A short button press creates a new survey point.
- Disconnecting UART while keeping USB power connected does not stop uploads.
- After a receiver outage, reconnecting uploads buffered records with their original capture times.

Phone provisioning has saved Wi-Fi credentials in NVS, and a subsequent boot has entered normal survey mode. After an application-only update retained those credentials, a real native survey reached the receiver over Wi-Fi with a valid capture timestamp and all sixteen Zigbee channels. Native radio/Wi-Fi self-tests and BLE service startup have also passed on hardware. Physical button/LED behavior, UART-disconnected power-bank operation, and an extended offline-buffer recovery survey remain field-verification steps for this development version.

## Label the networks accurately

Enter Hue, iHost, and HAN channel numbers from their own settings or exports. Unknown is a valid value. The scanner detects energy; it cannot infer those network identities from a busy channel.

For a HAN, confirm the **radio band** first. An IHD or communications hub may expose information for one link without proving the band used by every meter. An 868 MHz link is outside this scanner's range. A channel marker labels a known 2.4 GHz link; it does not establish that a particular meter is connected to it.

Wi-Fi channel and width fields in the settings panel are manual labels for an approximate overlay. The access-point scan supplies primary channel and RSSI; it does not measure width or utilization. Saving settings never changes a router, bridge, or meter.

## A repeatable survey

### Start beside the affected device

Place the scanner near the device whose link is unreliable, rather than only beside its coordinator. Keep it clear of metal surfaces and avoid touching or shielding its antennas. Record the scanner's physical location and orientation so a later measurement is comparable.

A short button press starts a new numbered point; use the dashboard to give the current location a descriptive label. Button waypoints reset after an ESP32 reboot, so name important locations in the dashboard and keep notes.

### Record a baseline

Start a controlled test with a clear name and the baseline condition. Leave the network in ordinary use long enough to observe its normal variation. For failures lasting hours or days, a short scan is insufficient: leave the receiver running and collect across a representative period.

Log failures, delays, and recoveries when they occur. A missing value on a display is not a measured packet failure; describe exactly what you observed and record a response time only when you measured it.

### Change one condition

Finish the baseline test, then repeat at the same scanner location while changing one condition with your normal controls. Examples include a repeatable light-command sequence or a known Wi-Fi load. Keep other traffic and placement as similar as practical.

If you change a router or Zigbee channel, record the actual resulting channel/width after the change, allow the network to settle, and repeat the same test. A nominal channel change may not reduce overlap if a Wi-Fi access point still uses a wide channel.

### Compare repeated results

Use the same location and history window when comparing means, p95 values, peaks, and events. Look for a repeatable change that accompanies the symptom. A single high-energy sample is a reason to investigate, not proof of interference.

The event table compares energy within **±15 seconds** of the event against the preceding **five minutes**, excluding the final **30 seconds**. It uses matching location and test context and reports insufficient data when coverage is too small.

## Offline records and timestamps

The device stores samples in a bounded LittleFS queue before attempting upload. It sends up to eight queued records per upload pass. When the queue grows beyond its threshold, older records are discarded to make space, and a dropped-record counter is reported.

Captures keep their original location, boot identifier, sequence number, and timestamp. The receiver deduplicates repeated uploads. A reboot before time synchronization can produce records with no trustworthy wall-clock time; these are retained but excluded from timed charts. Reconnecting cannot reconstruct a missing capture time reliably.

The queue is a practical short-outage buffer, not an unlimited logger or a guarantee against sudden power-loss data loss.

## Export and share

The dashboard exports the selected analysis and raw measurement log. Local data can contain Wi-Fi names/BSSIDs, device addresses, location notes, and event descriptions. Inspect and sanitize exports before sharing. Never include the generated provisioning QR, upload token, access code, Wi-Fi credentials, or a hub export containing Zigbee network keys.

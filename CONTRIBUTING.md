# Contributing

Contributions that improve measurement quality, hardware recovery, reproducible setup, accessibility, and documentation are welcome.

## Development checks

Use Python 3.12 or newer, a C++17 compiler, and Node.js:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest test_observatory test_portable -q
c++ -std=c++17 -Ifirmware-native/include firmware-native/test/protocol.cpp -o /tmp/survey-protocol-test
/tmp/survey-protocol-test
node --check dashboard/app.js
```

For firmware changes, follow the build instructions in the README and confirm that the ESP32 application still fits the partition table. Do not commit a generated device configuration or provisioning QR code. CI uses conspicuous build-only placeholders and does not contact real hardware.

## Pull requests

Explain the concrete problem, resulting behavior, checks performed, and any hardware observations. Separate an actual device observation from a fixture, simulation, or assumption. Record the board variant and relevant firmware version when reporting hardware behavior; redact identifiers and credentials.

Energy measurements are relative values. Avoid changes that label the raw scale as calibrated dBm, airtime occupancy, packet loss, or proof of a particular interference source without independent supporting measurements.

## Privacy and licensing

Do not attach household network exports, real SSIDs/BSSIDs, device addresses, access tokens, Wi-Fi passwords, provisioning QR codes, or unredacted screenshots. Use synthetic examples with clearly identified demonstration data.

Preserve third-party notices. Submit only work you have the right to distribute under the project's MIT license, or identify a compatible separate license for third-party material. Contributions to original project code are accepted under the [MIT license](LICENSE).

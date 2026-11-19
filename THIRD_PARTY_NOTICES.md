# Third-party notices

The project's original source and documentation are distributed under the [MIT license](LICENSE). Upstream components, product photographs, firmware blobs, and trademarks retain their own terms. This file does not relicense them.

## Included source

### MicroPython pyboard utility

[`pyboard.py`](pyboard.py) is derived from the [MicroPython pyboard utility](https://github.com/micropython/micropython/blob/master/tools/pyboard.py), licensed under MIT:

- Copyright (c) 2014–2021 Damien P. George
- Copyright (c) 2017 Paul Sokolovsky

The complete upstream copyright, permission grant, and warranty disclaimer are preserved in that file. Local serial-opening changes deassert DTR and RTS before opening the port. Preserve the upstream header when copying or modifying this utility.

## Dependencies installed separately

These are fetched by the Python or firmware build tooling rather than vendored in this source repository:

| Component | Upstream | License information |
|---|---|---|
| ArduinoJson | [bblanchon/ArduinoJson](https://github.com/bblanchon/ArduinoJson) | MIT |
| Arduino core for ESP32 | [espressif/arduino-esp32](https://github.com/espressif/arduino-esp32) | LGPL-2.1-or-later for the core; individual components may differ |
| ESP-IDF and provisioning components | [espressif/esp-idf](https://github.com/espressif/esp-idf) | Apache-2.0 for ESP-IDF; inspect component notices |
| pioarduino ESP32 platform | [pioarduino/platform-espressif32](https://github.com/pioarduino/platform-espressif32) | Apache-2.0 |
| Python packages | [requirements.txt](requirements.txt) | Each package retains its own distribution license |

A compiled firmware image combines components under different licenses. The project's MIT license alone is not a complete license notice for such an image. Before distributing binaries, preserve the applicable upstream licenses and meet their source and relinking obligations. This initial source release does not bundle vendor firmware or compiled device images.

## Hardware and media

SONOFF, ESP32, Zigbee, Hue, and other product names identify compatible hardware or protocols. They are the property of their respective owners. This project is independent and is not an official SONOFF or Espressif product.

Hardware documentation links do not grant permission to redistribute the linked site's photographs. Any included external image must have its own source and license recorded beside it. Manufacturer product imagery, when displayed through an external reference, remains subject to its owner's terms and is not covered by this repository's MIT license.

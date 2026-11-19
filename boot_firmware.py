"""Start the flashed ESP32 bootloader from RAM without requiring an EN wire."""
from types import SimpleNamespace
from esptool.cmds import load_ram
from hardware import connect

e=connect(reset=False)
e.ESP_RAM_BLOCK=256
e._port.dtr=False; e._port.rts=False
load_ram(e,SimpleNamespace(filename='firmware/ESP32_GENERIC-v1.29.0.bin'))
e._port.close()

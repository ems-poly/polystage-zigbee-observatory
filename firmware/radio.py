# MicroPython, SONOFF ZBBridge-P. Preserve the CC2652P firmware.
from machine import UART, Pin
import time, binascii
radio = UART(2, baudrate=115200, tx=19, rx=23, rxbuf=4096, timeout=0)
bsl = Pin(22, Pin.OUT, value=1)
rst = Pin(15, Pin.OUT, value=1)

def radio_reset():
    bsl.value(1)
    rst.value(0)
    time.sleep_ms(20)
    rst.value(1)
    time.sleep_ms(500)
    return True

def transfer(hexdata=''):
    if hexdata:
        radio.write(binascii.unhexlify(hexdata))
    time.sleep_ms(15)
    data = radio.read() or b''
    return binascii.hexlify(data).decode()

radio_reset()

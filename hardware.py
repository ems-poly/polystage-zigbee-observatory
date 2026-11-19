"""Controlled serial access: GPIO0=DTR, optional EN=RTS; no surprise resets on open."""
import os,serial,time
from serial.tools import list_ports
from esptool.targets.esp32 import ESP32ROM, ESP32StubLoader
def serial_port():
    selected=os.environ.get('ZIGBEE_SERIAL_PORT')
    if selected:return selected
    ports=list(list_ports.comports())
    candidates=[p.device for p in ports if p.vid==0x0403 and p.pid==0x6001]
    if not candidates:candidates=[p.device for p in ports if p.vid is not None]
    if len(candidates)!=1:
        raise RuntimeError('Set ZIGBEE_SERIAL_PORT to the connected 3.3 V UART adapter port')
    return candidates[0]
def connect(baud=115200, reset=False, wait=False):
    s=serial.Serial(port=None,baudrate=baud,timeout=.3)
    s.port=serial_port(); s.dtr=True; s.rts=False; s.open()
    if reset:
        s.rts=True; time.sleep(.15); s.rts=False; time.sleep(.15)
    e=ESP32ROM(s,baud=baud)
    while True:
        try:
            e.connect(mode='no_reset',attempts=1)
            break
        except Exception as exc:
            if isinstance(exc,(serial.SerialException,OSError)):
                s.close()
                raise
            if not wait:
                s.close()
                raise
            print('Holding DTR low; waiting for board power-on reset',flush=True)
            time.sleep(1)
    if e.sync_stub_detected:
        e=ESP32StubLoader(e)
    return e
if __name__=='__main__':
    e=connect()
    print('Bootloader responding; RAM helper:', e.IS_STUB)
    e._port.dtr=False; e._port.rts=False; e._port.close()

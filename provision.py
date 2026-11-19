"""Erase and provision only the ESP32; never writes the TI radio."""
import json, time, traceback
from pathlib import Path
from types import SimpleNamespace
from esptool.cmds import write_flash
from hardware import connect,serial_port
ROOT=Path(__file__).resolve().parent
STATUS=ROOT/'data/provision.json'
def status(stage,detail):
    temporary=STATUS.with_suffix('.tmp')
    temporary.write_text(json.dumps({'stage':stage,'detail':detail,'time':time.time()}))
    temporary.replace(STATUS)
    print(stage,detail,flush=True)
def main():
    while True:
        try:
            status('connecting','Waiting for ESP32 ROM/stub response; power-cycle if necessary')
            e=connect(reset=True, wait=True)
            break
        except Exception as exc:
            status('waiting_for_reset',str(exc)); time.sleep(5)
    if e.IS_STUB:
        e.soft_reset(stay_in_bootloader=True)
        e._port.close()
        e=connect(wait=True)
    e.flash_spi_attach(0)
    e.flash_set_parameters(0x400000)
    status('connected','ROM flash attached at 115200 baud')
    e.ESP_RAM_BLOCK=256
    e.FLASH_WRITE_SIZE=1024
    image=ROOT/'firmware/ESP32_GENERIC-v1.29.0.bin'
    status('flashing','Installing MicroPython on ESP32, preserving CC2652P')
    e.flash_set_parameters(0x400000)
    e.flash_begin(0x400000,0)
    with image.open('rb') as f:
        args=SimpleNamespace(compress=False,no_compress=True,no_stub=True,force=False,
            addr_filename=[(0x1000,f)],encrypt=False,encrypt_files=None,
            ignore_flash_encryption_efuse_setting=False,flash_size='4MB',flash_mode='keep',
            flash_freq='keep',chip='esp32',erase_all=False,verify=False)
        e.flash_set_parameters(0x400000)
        write_flash(e,args)
    status('booting','Image verified by flashing tool; starting firmware')
    e._port.dtr=False; e._port.rts=False
    from esptool.cmds import load_ram
    e.ESP_RAM_BLOCK=256
    try: load_ram(e,SimpleNamespace(filename=str(image)))
    except Exception as exc: print('RAM boot handoff:',exc,flush=True)
    e._port.close()
    time.sleep(3)
    import pyboard
    for attempt in range(5):
        board=None
        try:
            board=pyboard.Pyboard(serial_port(),timeout=3)
            board.enter_raw_repl(soft_reset=False)
            print(board.exec_('import sys; print(sys.implementation)'),flush=True)
            break
        except Exception:
            if board: board.close()
            if attempt==4: raise
            time.sleep(3)
    board.exec_((ROOT/'firmware/radio.py').read_text())
    print(board.exec_("print(transfer('fe00210120'))"),flush=True)
    board.exit_raw_repl(); board.close()
    status('ready','ESP32 MicroPython responding; radio UART ready for validation')
if __name__=='__main__':
    try: main()
    except Exception as exc:
        status('error',str(exc)); traceback.print_exc(); raise

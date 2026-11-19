"""Flash only the ESP32 via ROM, retrying verified sectors after UART errors."""
import argparse,hashlib,json,os,time
from pathlib import Path
from types import SimpleNamespace
from esptool.cmds import load_ram
from hardware import connect
ROOT=Path(__file__).resolve().parent

def report(stage):
 print(stage,flush=True)
 (ROOT/'data').mkdir(exist_ok=True)
 (ROOT/'data/native-flash-status.json').write_text(json.dumps({'stage':stage,'time':time.time()}))

def attach(wait=False):
 e=connect(reset=False,wait=wait)
 if e.IS_STUB:raise RuntimeError('Expected ESP32 ROM loader')
 e.flash_spi_attach(0);e.flash_set_parameters(0x400000)
 e.ESP_RAM_BLOCK=256;e.FLASH_WRITE_SIZE=1024
 return e

def write_verified(e,address,payload):
 # Chunk boundaries are flash-sector aligned so a retry cannot erase earlier data.
 for offset in range(0,len(payload),128*1024):
  blockdata=payload[offset:offset+128*1024];target=address+offset
  expected=hashlib.md5(blockdata).hexdigest()
  for attempt in range(4):
   try:
    if e.flash_md5sum(target,len(blockdata))!=expected:
     e.flash_begin(len(blockdata),target)
     for seq in range((len(blockdata)+1023)//1024):
      e.flash_block(blockdata[seq*1024:(seq+1)*1024].ljust(1024,b'\xff'),seq)
     if e.flash_md5sum(target,len(blockdata))!=expected:raise RuntimeError('Flash chunk hash mismatch')
    print('Verified',hex(target),len(blockdata),'bytes',flush=True);break
   except Exception as exc:
    print('UART retry',attempt+1,'at',hex(target),type(exc).__name__,flush=True)
    e._port.close()
    if attempt==3:raise
    e=attach()
 if e.flash_md5sum(address,len(payload))!=hashlib.md5(payload).hexdigest():raise RuntimeError('Complete image hash mismatch')
 return e

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--application-only',action='store_true',help='Require matching partition table and preserve Wi-Fi credentials and buffered data')
 args=parser.parse_args();build=ROOT/'firmware-native/.pio/build/zbbridgepro'
 report('Waiting for external USB power cycle; GPIO0 held low')
 e=attach(wait=True)
 if args.application_only:
  table=(build/'partitions.bin').read_bytes()
  if e.flash_md5sum(0x8000,len(table))!=hashlib.md5(table).hexdigest():raise RuntimeError('Partition table differs; application-only update refused')
  report('Updating application; preserving saved Wi-Fi credentials')
  segments=[(0x10000,build/'firmware.bin')]
 else:
  report('Erasing ESP32 flash; TI radio untouched');e.flash_begin(0x400000,0)
  core=Path(os.environ.get('PLATFORMIO_CORE_DIR',str(Path.home()/'.platformio')))
  segments=[(0x1000,build/'bootloader.bin'),(0x8000,build/'partitions.bin'),
   (0xe000,core/'packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin'),(0x10000,build/'firmware.bin')]
 for address,path in segments:e=write_verified(e,address,path.read_bytes())
 report('All written image hashes verified; starting native bootloader')
 e._port.dtr=False;e._port.rts=False
 try:load_ram(e,SimpleNamespace(filename=str(build/'bootloader.bin')))
 except Exception as exc:print('Boot handoff:',exc,flush=True)
 report('Collecting native startup output');e._port.timeout=.3
 with (ROOT/'data/native-startup.log').open('ab') as log:
  start=time.time()
  while time.time()-start<45:
   data=e._port.read(e._port.in_waiting or 1)
   if data:log.write(data);log.flush();print(data.decode(errors='replace'),end='',flush=True)
 e._port.close();report('Native startup collection finished')

if __name__=='__main__':
 try:main()
 except Exception as exc:report('Installation failed: '+str(exc));raise

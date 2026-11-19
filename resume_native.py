"""Resume an interrupted application write at a flash-sector boundary."""
import hashlib,time,sys
from pathlib import Path
from types import SimpleNamespace
from esptool.cmds import load_ram
from hardware import connect
from flash_native import report,ROOT
if len(sys.argv)!=2:raise SystemExit('Usage: python resume_native.py SECTOR_ALIGNED_FLASH_ADDRESS')
address=int(sys.argv[1],0)
assert address>=0x10000 and address%4096==0
build=ROOT/'firmware-native/.pio/build/zbbridgepro'
image=(build/'firmware.bin').read_bytes();remaining=image[address-0x10000:]
e=connect();e.flash_spi_attach(0);e.flash_set_parameters(0x400000);e.FLASH_WRITE_SIZE=1024;e.ESP_RAM_BLOCK=256
report('Resuming application write at '+hex(address))
e.flash_begin(len(remaining),address)
for index in range((len(remaining)+1023)//1024):
 block=remaining[index*1024:(index+1)*1024].ljust(1024,b'\xff');e.flash_block(block,index)
 if index%64==0:print('Resume progress',index*1024,'/',len(remaining),flush=True)
actual=e.flash_md5sum(0x10000,len(image));expected=hashlib.md5(image).hexdigest()
if actual!=expected:raise RuntimeError('Complete firmware hash mismatch: '+str(actual))
report('Complete native application hash verified')
e._port.dtr=False;e._port.rts=False
try:load_ram(e,SimpleNamespace(filename=str(build/'bootloader.bin')))
except Exception as exc:print('Boot handoff:',exc,flush=True)
e._port.timeout=.3
report('Collecting native startup and hardware self-tests')
with (ROOT/'data/native-startup.log').open('ab') as log:
 start=time.time()
 while time.time()-start<45:
  data=e._port.read(e._port.in_waiting or 1)
  if data:log.write(data);log.flush();print(data.decode(errors='replace'),end='',flush=True)
e._port.close();report('Native startup collection finished')

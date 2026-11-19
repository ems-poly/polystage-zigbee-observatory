"""Generate private firmware configuration and the standard Espressif BLE QR."""
import argparse,json,secrets,socket
from pathlib import Path
import qrcode
from configuration import ensure_auth
ROOT=Path(__file__).resolve().parent

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--receiver',help='LAN receiver URL, e.g. http://192.0.2.1:8767');args=parser.parse_args()
 data=ROOT/'data';data.mkdir(exist_ok=True)
 auth=ensure_auth(ROOT)
 configfile=data/'portable-device.json';config=json.loads(configfile.read_text()) if configfile.exists() else {}
 receiver=args.receiver or config.get('receiver')
 if not receiver:
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
   sock.connect(('8.8.8.8',9));receiver='http://'+sock.getsockname()[0]+':8767'
 config={'device_id':auth['device_id'],'token':auth['token'],'receiver':receiver,
   'prov_name':config.get('prov_name','PROV_'+auth['device_id'][-6:].upper()),'pop':config.get('pop',secrets.token_hex(6)),'provisioning':'ble'}
 configfile.write_text(json.dumps(config));configfile.chmod(0o600)
 (data/'transport.json').write_text(json.dumps({'mode':'portable'}))
 header=ROOT/'firmware-native/include/device_secrets.h'
 mapping={'DEVICE_ID':'device_id','RECEIVER_URL':'receiver','INGEST_TOKEN':'token','PROV_NAME':'prov_name','PROV_POP':'pop'}
 header.write_text('#pragma once\n'+''.join('static const char *'+k+' = '+json.dumps(config[v])+';\n' for k,v in mapping.items()));header.chmod(0o600)
 qr={'ver':'v1','name':config['prov_name'],'pop':config['pop'],'transport':'ble'}
 qrcode.make(json.dumps(qr,separators=(',',':'))).save(data/'provisioning-qr.png')
 print('Private configuration and BLE QR ready; receiver:',receiver)
if __name__=='__main__':main()

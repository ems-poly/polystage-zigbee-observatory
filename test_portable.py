import asyncio,copy,json,tempfile,threading,time,unittest
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from observatory import Observatory
from portable import Receiver,validate_sample
from firmware.survey_protocol import Frames,encode,scan_payload,energy

def sample(now=None):
 return {'device_id':'fixture-device','boot_id':'testboot','seq':1,'captured_at':time.time() if now is None else now,
    'clock_valid':True,'location':'Survey point 2','session':None,'wifi_off_during_zigbee':True,
    'channels':[{'channel':ch,'raw':ch*3} for ch in range(11,27)],'radio_error':None,
    'wifi':[{'ssid':'Fixture','bssid':'demo-access-point','channel':6,'rssi':-55,'width_mhz':None}],
    'wifi_scanned_at':time.time(),'waypoint':2,'queue_dropped':0}

class CodecTests(unittest.TestCase):
 def test_matches_installed_znp_schema(self):
  import zigpy_znp.commands as c,zigpy_znp.types as t
  packet=c.MAC.ScanReq.Req(ScanChannels=t.Channels.ALL_CHANNELS,ScanType=0,ScanDuration=2,ChannelPage=0,MaxResults=32,KeySource=[0]*8,SecurityLevel=0,KeyIdMode=0,KeyIndex=0).to_frame()
  self.assertEqual(scan_payload(),bytes(packet.data))
 def test_fragmented_combined_and_bad_checksum_frames(self):
  first=encode(0x62,0x0c,b'\0');last=encode(0x42,0x8c,b'example');f=Frames()
  self.assertEqual(f.feed(b'noise'+first[:3]),[])
  self.assertEqual(f.feed(first[3:]+last),[(0x62,0x0c,b'\0'),(0x42,0x8c,b'example')])
  bad=bytearray(last);bad[-1]^=1
  self.assertEqual(f.feed(bad+first),[(0x62,0x0c,b'\0')])
 def test_actual_legacy_energy_mapping(self):
  p=bytes.fromhex('00000000000000001b20'+'ff'*11+'334845487b727878694b663c2d3f4254'+'00'*5)
  values=energy(p);self.assertEqual(values[0]['raw'],51);self.assertEqual(values[-1]['raw'],84)
 def test_validation_rejects_self_interference_and_bad_times(self):
  good=sample();validate_sample(good,time.time(),good['device_id'])
  for key,value in [('wifi_off_during_zigbee',False),('seq',True),('captured_at',float('nan')),('clock_valid',False)]:
   bad=copy.deepcopy(good);bad[key]=value
   with self.assertRaises(ValueError):validate_sample(bad,time.time(),good['device_id'])

class ReceiverTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);(root/'data').mkdir()
  self.obs=Observatory(root/'data');self.state={'updated':None,'scans':0,'history':[]}
  from configuration import ensure_auth
  auth=ensure_auth(root);auth['device_id']='fixture-device'
  (root/'data/portable-auth.json').write_text(json.dumps(auth))
  self.receiver=Receiver(self.obs,self.state,threading.Lock(),root)
  app=web.Application(middlewares=[self.receiver.protect],client_max_size=32768)
  app.router.add_post('/api/portable/scan',self.receiver.ingest)
  app.router.add_get('/api/portable/bootstrap',self.receiver.bootstrap)
  app.router.add_post('/login',self.receiver.login)
  app.router.add_get('/private',lambda r:web.json_response({'ok':True}))
  self.client=TestClient(TestServer(app));await self.client.start_server()
  self.headers={'X-Survey-Token':self.receiver.auth['token']}
 async def asyncTearDown(self):await self.client.close();self.obs.db.close();self.temp.cleanup()
 async def test_authentication_and_idempotent_actual_capture_time(self):
  value=sample(time.time()-120)
  r=await self.client.post('/api/portable/scan',json=value);self.assertEqual(r.status,401)
  r=await self.client.post('/api/portable/scan',json=value,headers=self.headers);self.assertEqual(r.status,201)
  r=await self.client.post('/api/portable/scan',json=value,headers=self.headers);self.assertTrue((await r.json())['duplicate'])
  self.assertEqual(self.obs.summary()['coverage']['count'],1)
  self.assertEqual(self.state['updated'],value['captured_at']);self.assertEqual(self.state['location'],'Survey point 2')
 async def test_unclocked_data_is_preserved_but_not_plotted(self):
  value=sample();value.update(captured_at=None,clock_valid=False)
  r=await self.client.post('/api/portable/scan',json=value,headers=self.headers);self.assertEqual(r.status,201)
  self.assertEqual(self.obs.summary()['coverage']['count'],0)
  self.assertEqual(self.obs.db.execute('SELECT COUNT(*) FROM portable_samples').fetchone()[0],1)
 async def test_old_buffered_samples_do_not_replace_latest_measurement(self):
  current=sample();older=sample(time.time()-100);older['seq']=2
  await self.client.post('/api/portable/scan',json=current,headers=self.headers)
  await self.client.post('/api/portable/scan',json=older,headers=self.headers)
  self.assertEqual(self.state['updated'],current['captured_at'])
 async def test_dashboard_needs_code(self):
  r=await self.client.get('/private',allow_redirects=False);self.assertEqual(r.status,302)
  r=await self.client.post('/login',data={'code':self.receiver.auth['dashboard_code']},allow_redirects=False)
  self.assertEqual(r.status,302);self.assertTrue(r.cookies['survey_view']['httponly'])

if __name__=='__main__':unittest.main()

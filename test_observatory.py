import json,tempfile,time,unittest
from pathlib import Path
from observatory import Observatory
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
import scanner

def record(t,raw):
    return {'time':t,'channels':[{'channel':ch,'raw':raw,'percent':round(raw*100/255,1)} for ch in range(11,27)]}

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name);self.o=Observatory(self.path)
    def tearDown(self): self.o.db.close();self.temp.cleanup()
    def test_event_comparison_filters_location_and_keeps_channel_snapshot(self):
        self.o.configure({'networks':{'Hue':15},'location':'Desk'})
        for t in (900,930,960,990,1020,1050,1100,1130,1160): self.o.add_scan(record(t,20))
        for t in (1190,1200,1210): self.o.add_scan(record(t,80))
        event=self.o.add_event({'network':'Hue','kind':'failure','note':'Measured test fixture'},now=1200)
        self.o.configure({'location':'Other','networks':{'Hue':20}})
        self.o.add_scan(record(1191,250))
        result=self.o.summary(15,now=1220)
        saved=next(e for e in result['events'] if e['id']==event['id'])
        self.assertEqual(saved['channel'],15)
        self.assertEqual(saved['comparison']['delta'],60)
        self.assertEqual(saved['comparison']['event_samples'],3)
        self.assertEqual(len(self.o.summary(15,'Desk',now=1220)['history']),12)
    def test_missing_baseline_and_future_window_are_not_claimed_as_correlation(self):
        self.o.configure({'networks':{'iHost':20}})
        self.o.add_scan(record(1200,100));self.o.add_event({'network':'iHost','kind':'delay'},now=1200)
        self.assertEqual(self.o.summary(15,now=1205)['events'][0]['comparison']['status'],'collecting')
        self.assertEqual(self.o.summary(15,now=1220)['events'][0]['comparison']['status'],'insufficient')
    def test_sessions_prevent_mixing_locations_and_survive_restart(self):
        self.o.configure({'location':'Desk'});self.o.session({'action':'start','label':'Baseline','condition':'baseline'})
        key=self.o.settings['active_session'];self.o.add_scan(record(time.time(),50))
        with self.assertRaises(ValueError):self.o.configure({'location':'Other'})
        self.o.db.close();self.o=Observatory(self.path)
        self.assertEqual(self.o.settings['active_session'],key)
        self.assertEqual(self.o.summary(15,session=key)['coverage']['count'],1)
        self.o.session({'action':'stop'});self.o.configure({'location':'Other'})
    def test_import_is_idempotent_and_preserves_real_history(self):
        self.o.db.close();self.path.joinpath('scans.jsonl').write_text(json.dumps(record(1200,45))+'\n')
        self.path.joinpath('imported-network.json').write_text('{"channel":20}')
        # A fresh database is used to exercise the one-time legacy import.
        fresh=self.path/'fresh';fresh.mkdir()
        fresh.joinpath('scans.jsonl').write_text(self.path.joinpath('scans.jsonl').read_text())
        fresh.joinpath('imported-network.json').write_text('{"channel":20}')
        self.o=Observatory(fresh)
        self.assertEqual(self.o.settings['networks']['iHost'],20)
        self.assertEqual(self.o.summary(15,now=1220)['coverage']['count'],1)
        self.o.db.close();self.o=Observatory(fresh)
        self.assertEqual(self.o.summary(15,now=1220)['coverage']['count'],1)
    def test_validation(self):
        for value in (True,10,27,'20'):
            with self.assertRaises(ValueError):self.o.configure({'networks':{'Hue':value}})
        with self.assertRaises(ValueError):self.o.configure({'networks':{'HAN':20},'han_band':'868MHz'})
        with self.assertRaises(ValueError):self.o.add_event({'latency':float('nan')})

class APITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.o=Observatory(self.temp.name);scanner.observatory=self.o
        app=web.Application();app.router.add_post('/api/settings',scanner.settings);app.router.add_post('/api/events',scanner.events)
        app.router.add_get('/api/analysis',scanner.analysis);app.router.add_post('/api/sessions',scanner.sessions)
        self.client=TestClient(TestServer(app));await self.client.start_server()
    async def asyncTearDown(self):await self.client.close();self.o.db.close();self.temp.cleanup()
    async def test_real_routes_validation_and_recording(self):
        r=await self.client.post('/api/settings',json={'networks':{'Hue':15,'iHost':20},'location':'Hall'})
        self.assertEqual(r.status,200)
        r=await self.client.post('/api/events',json={'network':'iHost','kind':'failure','note':'Fixture'})
        self.assertEqual(r.status,201);event=await r.json();self.assertEqual(event['channel'],20)
        r=await self.client.get('/api/analysis?minutes=15&location=Hall&download=1')
        self.assertEqual(r.status,200);self.assertIn('attachment',r.headers['Content-Disposition'])
        a=await r.json();self.assertEqual(a['coverage']['count'],0);self.assertEqual(len(a['events']),1)
        r=await self.client.post('/api/settings',json={'networks':{'Hue':10}});self.assertEqual(r.status,400)
        r=await self.client.post('/api/events',json=[]);self.assertEqual(r.status,400)
        r=await self.client.get('/api/analysis?minutes=9999');self.assertEqual(r.status,400)

if __name__=='__main__':unittest.main()

"""Authenticated LAN receiver for the power-bank survey unit."""
import asyncio, hashlib, hmac, ipaddress, json, math, secrets, time
from pathlib import Path
from aiohttp import web
from configuration import ensure_auth


def validate_sample(value, now, device_id):
    if not isinstance(value,dict): raise ValueError('Expected a survey object')
    if value.get('device_id')!=device_id: raise ValueError('Unrecognized survey unit')
    boot=value.get('boot_id');seq=value.get('seq')
    if not isinstance(boot,str) or not 1<=len(boot)<=32 or type(seq) is not int or not 0<=seq<2**31: raise ValueError('Invalid sample identity')
    location=value.get('location')
    if not isinstance(location,str) or not location.strip() or len(location)>100: raise ValueError('Invalid survey location')
    if value.get('wifi_off_during_zigbee') is not True: raise ValueError('Wi-Fi must be disabled during Zigbee measurements')
    stamp=value.get('captured_at')
    if stamp is not None and (type(stamp) not in (int,float) or not math.isfinite(stamp) or not now-7*86400<=stamp<=now+30): raise ValueError('Invalid or expired capture time')
    if stamp is not None and value.get('clock_valid') is not True: raise ValueError('Capture time has not been synchronized')
    channels=value.get('channels');error=value.get('radio_error')
    if not isinstance(channels,list): raise ValueError('Missing energy readings')
    if channels:
        if len(channels)!=16: raise ValueError('Expected all 16 Zigbee channels')
        for expected,item in zip(range(11,27),channels):
            if not isinstance(item,dict) or item.get('channel')!=expected or type(item.get('raw')) is not int or not 0<=item['raw']<=255: raise ValueError('Invalid energy reading')
    elif not isinstance(error,str) or not error or len(error)>300: raise ValueError('Empty readings need a radio-error explanation')
    aps=value.get('wifi')
    if not isinstance(aps,list) or len(aps)>32: raise ValueError('Invalid Wi-Fi scan')
    for ap in aps:
        if not isinstance(ap,dict) or not isinstance(ap.get('ssid'),str) or len(ap['ssid'].encode())>128: raise ValueError('Invalid Wi-Fi name')
        if type(ap.get('channel')) is not int or not 1<=ap['channel']<=14: raise ValueError('Invalid 2.4 GHz Wi-Fi channel')
        if type(ap.get('rssi')) is not int or not -127<=ap['rssi']<=0: raise ValueError('Invalid Wi-Fi RSSI')
        if ap.get('width_mhz') is not None: raise ValueError('This firmware does not measure Wi-Fi channel width')
    # Build a bounded record: arbitrary request fields never enter measurements.
    return {'device_id':device_id,'boot_id':boot,'seq':seq,'captured_at':stamp,'location':location.strip(),
        'session':value.get('session') if isinstance(value.get('session'),str) else None,
        'channels':[{'channel':i['channel'],'raw':i['raw'],'percent':round(i['raw']*100/255,1)} for i in channels],
        'wifi':[{k:a.get(k) for k in ('ssid','bssid','channel','rssi','security','hidden','width_mhz')} for a in aps],
        'wifi_off_during_zigbee':True,'wifi_scanned_at':value.get('wifi_scanned_at'),
        'radio_error':error[:300] if isinstance(error,str) else None,
        'device_ip':value.get('device_ip') if isinstance(value.get('device_ip'),str) else None,
        'waypoint':value.get('waypoint'),'queue_dropped':value.get('queue_dropped',0),
        'zigbee_duration_ms':value.get('zigbee_duration_ms'),'received_at':now}

class Receiver:
    def __init__(self,obs,state,lock,root):
        self.obs=obs;self.state=state;self.lock=lock;self.root=Path(root);self.attempts={};self.runner=None
        self.auth=ensure_auth(self.root)
        self.obs.db.executescript('''CREATE TABLE IF NOT EXISTS portable_samples(
            device TEXT,boot TEXT,seq INTEGER,received REAL NOT NULL,captured REAL,
            location TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(device,boot,seq));
            CREATE INDEX IF NOT EXISTS portable_captured ON portable_samples(captured);''')
        self.obs.db.commit();self.latest=None
        row=self.obs.db.execute('SELECT payload FROM portable_samples ORDER BY received DESC LIMIT 1').fetchone()
        if row:self.latest=json.loads(row[0])

    def response(self,**extra):
        return {'unix_time':time.time(),'control':{'location':self.obs.settings['location'],
            'active_session':self.obs.settings['active_session']},**extra}

    def cookie(self):
        expiry=str(int(time.time()+24*3600))
        return expiry+'.'+hmac.new(self.auth['token'].encode(),expiry.encode(),hashlib.sha256).hexdigest()

    def logged_in(self,request):
        try:
            expiry,signature=request.cookies.get('survey_view','').split('.',1)
            expected=hmac.new(self.auth['token'].encode(),expiry.encode(),hashlib.sha256).hexdigest()
            return int(expiry)>time.time() and hmac.compare_digest(signature,expected)
        except (ValueError,TypeError):return False

    @web.middleware
    async def protect(self,request,handler):
        try:
            if not ipaddress.ip_address(request.remote).is_private: raise web.HTTPForbidden()
        except ValueError:raise web.HTTPForbidden()
        if request.path in ('/api/portable/bootstrap','/api/portable/scan'):
            if not hmac.compare_digest(request.headers.get('X-Survey-Token',''),self.auth['token']):raise web.HTTPUnauthorized(text='Survey token required')
        elif request.path!='/login' and not self.logged_in(request):
            if request.path.startswith('/api/'):raise web.HTTPUnauthorized(text='Sign in to the survey dashboard')
            raise web.HTTPFound('/login')
        if request.method=='POST' and request.headers.get('Origin') and request.headers['Origin']!=request.scheme+'://'+request.host:
            raise web.HTTPForbidden(text='Unexpected request origin')
        result=await handler(request);result.headers['Cache-Control']='no-store';result.headers['Referrer-Policy']='no-referrer'
        return result

    async def login(self,request):
        error=''
        if request.method=='POST':
            key=request.remote;now=time.time();tries=[t for t in self.attempts.get(key,[]) if now-t<60]
            if len(tries)>=5:raise web.HTTPTooManyRequests(text='Please wait a minute before trying again')
            data=await request.post()
            if hmac.compare_digest(str(data.get('code','')),self.auth['dashboard_code']):
                response=web.HTTPFound('/');response.set_cookie('survey_view',self.cookie(),httponly=True,samesite='Strict',max_age=86400);return response
            self.attempts[key]=tries+[now];error='Incorrect survey access code.'
        return web.Response(content_type='text/html',text='''<!doctype html><meta name="viewport" content="width=device-width"><title>Survey dashboard</title><style>body{font:17px system-ui;background:#12201b;color:#edf7f0;max-width:480px;margin:60px auto;padding:20px}input,button{display:block;width:100%;padding:14px;margin:15px 0;box-sizing:border-box}</style><h1>Portable RF survey</h1><p>Enter the dashboard access code shown on the Mac’s local dashboard. This is not your home Wi-Fi password.</p><form method="post"><label>Access code<input name="code" type="password" required maxlength="32"></label><button>Open dashboard</button></form><p>'''+error+'</p>')

    async def bootstrap(self,request):return web.json_response(self.response())

    async def ingest(self,request):
        try:value=validate_sample(await request.json(),time.time(),self.auth['device_id'])
        except ValueError as exc:raise web.HTTPBadRequest(text=str(exc))
        db=self.obs.db;identity=(value['device_id'],value['boot_id'],value['seq'])
        if db.execute('SELECT 1 FROM portable_samples WHERE device=? AND boot=? AND seq=?',identity).fetchone():
            return web.json_response(self.response(duplicate=True))
        # Preserve capture context; don't attach a location change to an unrelated active test.
        if value['session']:
            session=db.execute('SELECT location FROM sessions WHERE id=?',(value['session'],)).fetchone()
            if not session or session['location']!=value['location']:value['session']=None
        record=None
        with db:
            db.execute('INSERT INTO portable_samples VALUES(?,?,?,?,?,?,?)',identity+(value['received_at'],value['captured_at'],value['location'],json.dumps(value)))
            if value['captured_at'] is not None and value['channels']:
                record={'time':value['captured_at'],'channels':value['channels'],'location':value['location'],
                    'session':value['session'],'source':'portable','device_id':value['device_id'],
                    'wifi_off_during_zigbee':True,'wifi_scanned_at':value['wifi_scanned_at'],
                    'wifi':value['wifi'],'transmissions':None,'failures':None}
                self.obs.add_scan(record,legacy=True,commit=False)
        if record:
            with (self.root/'data/scans.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
            with self.lock:
                if not self.state['updated'] or record['time']>=self.state['updated']:
                    self.state.update(status='scanning',error=None,updated=record['time'],channels=record['channels'],location=record['location'],transport='portable')
                    self.state['scans']+=1;self.state['history']=(self.state['history']+[record])[-120:]
        elif value['radio_error']:
            with self.lock:self.state.update(status='error',error=value['radio_error'])
        if self.latest is None or (value['captured_at'] or 0)>=(self.latest.get('captured_at') or 0):self.latest=value
        return web.json_response(self.response(saved=True,clock_required=value['captured_at'] is None),status=201)

    async def status(self,request):
        row=self.obs.db.execute('SELECT COUNT(*) FROM portable_samples').fetchone()
        return web.json_response({'enabled':True,'samples_received':row[0],'latest':self.latest,
            'limits':'2.4 GHz Wi-Fi only. AP channel widths are not measured. Zigbee samples are captured with both ESP32 Wi-Fi interfaces disabled.'})

    async def access(self,request):
        import socket
        address='127.0.0.1'
        try:
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',9));address=s.getsockname()[0];s.close()
        except OSError:pass
        local=request.remote in ('127.0.0.1','::1')
        result={'url':'http://'+address+':8767','code':self.auth['dashboard_code'] if local else None}
        setup=self.root/'data/portable-device.json'
        if local and setup.exists():
            config=json.loads(setup.read_text())
            result['setup']={'name':config['prov_name'],'pop':config['pop'],'transport':'ble','qr':'/api/portable/qr'}
        return web.json_response(result)

    async def qr(self,request):
        path=self.root/'data/provisioning-qr.png'
        if not path.exists():raise web.HTTPNotFound()
        return web.FileResponse(path,headers={'Cache-Control':'no-store'})

    async def start(self,routes):
        app=web.Application(middlewares=[self.protect],client_max_size=32768)
        app.router.add_get('/api/portable/qr',self.qr)
        app.router.add_get('/login',self.login);app.router.add_post('/login',self.login)
        app.router.add_get('/api/portable/bootstrap',self.bootstrap);app.router.add_post('/api/portable/scan',self.ingest)
        for method,path,handler in routes:app.router.add_route(method,path,handler)
        app.router.add_static('/dashboard/',self.root/'dashboard',show_index=False)
        self.runner=web.AppRunner(app);await self.runner.setup();await web.TCPSite(self.runner,'0.0.0.0',8767).start()

    async def close(self):
        if self.runner:await self.runner.cleanup()

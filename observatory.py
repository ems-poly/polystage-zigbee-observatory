"""Persistent RF measurements, experiment context and event comparisons."""
import json, math, sqlite3, time, uuid
from pathlib import Path

NETWORKS=('Hue','iHost','HAN')
DEFAULTS={'networks':{n:None for n in NETWORKS},'location':'Unlabelled','wifi_channel':None,
          'wifi_width':None,'han_band':'unknown','han_model':'','active_session':None}
KINDS=('failure','delay','recovery','test','note')

class Observatory:
    def __init__(self, directory):
        self.directory=Path(directory); self.directory.mkdir(exist_ok=True)
        self.db=sqlite3.connect(self.directory/'observatory.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY,time REAL UNIQUE NOT NULL,location TEXT NOT NULL,session TEXT);
        CREATE INDEX IF NOT EXISTS scans_time ON scans(time);
        CREATE INDEX IF NOT EXISTS scans_location_time ON scans(location,time);
        CREATE TABLE IF NOT EXISTS readings(scan INTEGER NOT NULL REFERENCES scans(id),channel INTEGER NOT NULL,raw INTEGER NOT NULL,PRIMARY KEY(scan,channel));
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,time REAL NOT NULL,network TEXT,kind TEXT NOT NULL,note TEXT NOT NULL,location TEXT NOT NULL,session TEXT,channel INTEGER,latency REAL);
        CREATE INDEX IF NOT EXISTS events_time ON events(time);
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,start REAL NOT NULL,end REAL,label TEXT NOT NULL,condition TEXT NOT NULL,location TEXT NOT NULL);
        ''')
        row=self.db.execute("SELECT value FROM meta WHERE key='settings'").fetchone()
        self.settings=json.loads(json.dumps(DEFAULTS))
        if row: self.settings.update(json.loads(row['value']))
        else:
            old=self.directory/'networks.json'
            if old.exists(): self.settings['networks'].update(json.loads(old.read_text()))
        self.settings['networks']={n:self.settings['networks'].get(n) for n in NETWORKS}
        if not self.db.execute("SELECT 1 FROM meta WHERE key='legacy_import'").fetchone():
            old=self.directory/'scans.jsonl'
            if old.exists():
                with old.open() as f:
                    for line in f:
                        try: self.add_scan(json.loads(line),legacy=True,commit=False)
                        except (ValueError,KeyError,TypeError): continue
            self.db.execute("INSERT INTO meta VALUES('legacy_import','done')")
        imported=self.directory/'imported-network.json'
        if imported.exists() and not self.db.execute("SELECT 1 FROM meta WHERE key='ihost_import_applied'").fetchone():
            channel=json.loads(imported.read_text()).get('channel')
            if self.settings['networks']['iHost'] is None and type(channel) is int and 11<=channel<=26:
                self.settings['networks']['iHost']=channel
            self.db.execute("INSERT INTO meta VALUES('ihost_import_applied','done')")
        self.save_settings()

    def save_settings(self):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('settings',?)",(json.dumps(self.settings),)); self.db.commit()

    def configure(self, values):
        if not isinstance(values,dict): raise ValueError('Expected settings object')
        new=json.loads(json.dumps(self.settings))
        if 'networks' in values:
            if not isinstance(values['networks'],dict): raise ValueError('Expected network channels')
            for n,ch in values['networks'].items():
                if n not in NETWORKS: raise ValueError('Unknown network')
                if ch is not None and (type(ch) is not int or not 11<=ch<=26): raise ValueError('Zigbee channels must be 11–26 or unknown')
                new['networks'][n]=ch
        for key in ('location','han_model'):
            if key in values:
                if not isinstance(values[key],str) or len(values[key])>100: raise ValueError(key+' must be at most 100 characters')
                new[key]=values[key].strip() or ('Unlabelled' if key=='location' else '')
        for key,allowed in (('wifi_channel',range(1,15)),('wifi_width',(20,40))):
            if key in values:
                v=values[key]
                if v is not None and (type(v) is not int or v not in allowed): raise ValueError('Invalid '+key)
                new[key]=v
        if 'han_band' in values:
            if values['han_band'] not in ('unknown','2.4GHz','868MHz'): raise ValueError('Invalid HAN band')
            new['han_band']=values['han_band']
        if new['han_band']=='868MHz' and new['networks']['HAN'] is not None:
            raise ValueError('868 MHz HAN cannot have a 2.4 GHz channel marker')
        if new['location']!=self.settings['location'] and self.settings['active_session']:
            raise ValueError('Finish the current test before changing scanner location')
        self.settings=new; self.save_settings(); return new

    def add_scan(self, record, legacy=False, commit=True):
        location=record.get('location','Unlabelled') if legacy else self.settings['location']
        session=record.get('session') if legacy else self.settings['active_session']
        cursor=self.db.execute('INSERT OR IGNORE INTO scans(time,location,session) VALUES(?,?,?)',(record['time'],location,session))
        if cursor.rowcount:
            self.db.executemany('INSERT INTO readings VALUES(?,?,?)',[(cursor.lastrowid,v['channel'],v['raw']) for v in record['channels']])
        if commit: self.db.commit()
        record.update(location=location,session=session)

    def add_event(self, value, now=None):
        if not isinstance(value,dict): raise ValueError('Expected event object')
        network=value.get('network') or None; kind=value.get('kind','note'); note=value.get('note','')
        latency=value.get('latency')
        if network is not None and network not in NETWORKS: raise ValueError('Unknown event network')
        if kind not in KINDS: raise ValueError('Unknown event type')
        if not isinstance(note,str) or len(note)>500: raise ValueError('Note must be at most 500 characters')
        if latency is not None and (type(latency) not in (int,float) or not math.isfinite(latency) or not 0<=latency<=3600000): raise ValueError('Latency must be milliseconds between 0 and 3600000')
        event={'id':uuid.uuid4().hex,'time':now if now is not None else time.time(),'network':network,'kind':kind,'note':note.strip(),
               'location':self.settings['location'],'session':self.settings['active_session'],
               'channel':self.settings['networks'].get(network),'latency':latency}
        self.db.execute('INSERT INTO events VALUES(:id,:time,:network,:kind,:note,:location,:session,:channel,:latency)',event); self.db.commit()
        return event

    def session(self, value):
        if not isinstance(value,dict): raise ValueError('Expected test object')
        if value.get('action')=='stop':
            if not self.settings['active_session']: raise ValueError('No test is running')
            self.add_event({'kind':'note','note':'Test finished'})
            self.db.execute('UPDATE sessions SET end=? WHERE id=?',(time.time(),self.settings['active_session']))
            self.settings['active_session']=None; self.save_settings(); return
        if value.get('action')!='start': raise ValueError('Unknown test action')
        if self.settings['active_session']: raise ValueError('Finish the current test first')
        label=value.get('label',''); condition=value.get('condition','baseline')
        if not isinstance(label,str) or not label.strip() or len(label)>100: raise ValueError('Give the test a name, up to 100 characters')
        if condition not in ('baseline','Hue commands','iHost commands','Wi-Fi busy','Wi-Fi quiet','placement','other'): raise ValueError('Unknown test condition')
        key=uuid.uuid4().hex
        self.db.execute('INSERT INTO sessions VALUES(?,?,NULL,?,?,?)',(key,time.time(),label.strip(),condition,self.settings['location']))
        self.settings['active_session']=key; self.save_settings()
        self.add_event({'kind':'test','note':label.strip()+' — '+condition})

    def summary(self, minutes=15, location=None, session=None, now=None):
        now=time.time() if now is None else now; start=now-minutes*60
        where='s.time>=? AND s.time<=?'; params=[start,now]
        if location: where+=' AND s.location=?'; params.append(location)
        if session: where+=' AND s.session=?'; params.append(session)
        query=' FROM readings r JOIN scans s ON s.id=r.scan WHERE '+where
        rows=self.db.execute('''WITH ranked AS (SELECT r.channel,r.raw,
            ROW_NUMBER() OVER(PARTITION BY r.channel ORDER BY r.raw) AS n,
            COUNT(*) OVER(PARTITION BY r.channel) AS c'''+query+''')
            SELECT channel,COUNT(*) samples,ROUND(AVG(raw),1) mean,MAX(raw) peak,
            MIN(CASE WHEN n >= ((c*95+99)/100) THEN raw END) p95 FROM ranked GROUP BY channel''',params)
        stats=[dict(row) for row in rows]
        bucket=max(1,math.ceil(minutes*60/360))
        history={}
        for row in self.db.execute('SELECT CAST(s.time/? AS INTEGER)*? time,r.channel,AVG(r.raw) raw,MAX(r.raw) peak,COUNT(*) samples'+query+' GROUP BY 1,r.channel ORDER BY 1,r.channel',[bucket,bucket]+params):
            history.setdefault(row['time'],{'time':row['time'],'channels':[]})['channels'].append(dict(row))
        ewhere='time>=? AND time<=?'; ep=[start,now]
        if location: ewhere+=' AND location=?'; ep.append(location)
        if session: ewhere+=' AND session=?'; ep.append(session)
        events=[dict(row) for row in self.db.execute('SELECT * FROM events WHERE '+ewhere+' ORDER BY time DESC LIMIT 200',ep)]
        for event in events:
            event['comparison']=None
            if event['channel'] is None: continue
            # Use a complete ±15 s event window; never silently compare different places/tests.
            if now<event['time']+15: event['comparison']={'status':'collecting'}; continue
            base='SELECT COUNT(*) n,AVG(r.raw) mean FROM readings r JOIN scans s ON r.scan=s.id WHERE r.channel=? AND s.location=? AND s.time>=? AND s.time<?'
            extra=' AND s.session IS ?'; context=[event['channel'],event['location']]
            before=self.db.execute(base+extra,context+[event['time']-300,event['time']-30,event['session']]).fetchone()
            around=self.db.execute(base+extra,context+[event['time']-15,event['time']+15,event['session']]).fetchone()
            if before['n']<5 or around['n']<2:
                event['comparison']={'status':'insufficient','before_samples':before['n'],'event_samples':around['n']}
            else:
                event['comparison']={'status':'ready','before_samples':before['n'],'event_samples':around['n'],
                    'before':round(before['mean'],1),'around':round(around['mean'],1),
                    'delta':round(around['mean']-before['mean'],1)}
        count=self.db.execute('SELECT COUNT(*) count,MIN(s.time) first,MAX(s.time) last FROM scans s WHERE '+where,params).fetchone()
        return {'start':start,'end':now,'minutes':minutes,'bucket_seconds':bucket,'location':location,'session':session,
                'stats':stats,'history':list(history.values()),'events':events,'coverage':dict(count),
                'settings':self.settings,'locations':[r[0] for r in self.db.execute('SELECT DISTINCT location FROM scans ORDER BY location')],
                'sessions':[dict(r) for r in self.db.execute('SELECT * FROM sessions ORDER BY start DESC LIMIT 50')],
                'limits':'Energy is relative 0–255, not dBm or airtime occupancy. Event comparisons show association, not proof of interference. Each sweep samples channels sequentially and can miss short bursts.'}

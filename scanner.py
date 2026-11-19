"""Local UART-to-ZNP scanner and HTTP dashboard. No simulated measurements."""
import argparse, asyncio, contextlib, json, logging, queue, socket, threading, time, re
from collections import deque
from pathlib import Path
from aiohttp import web
import pyboard
from observatory import Observatory, NETWORKS
from portable import Receiver
observatory=None

ROOT=Path(__file__).resolve().parent
state={'status':'starting','error':None,'updated':None,'channels':[], 'history':[], 'radio':None,'scans':0,
       'networks':{n:None for n in NETWORKS},'measurement':'ZNP energy detect, raw 0–255; not calibrated dBm'}
lock=threading.Lock()

class UARTTunnel:
    def __init__(self, port, tcp_port=8766):
        self.port=port; self.tcp_port=tcp_port; self.stop=threading.Event(); self.error=None
    def run(self):
        board=None
        try:
            board=pyboard.Pyboard(self.port, timeout=3)
            board.serial.dtr=False; board.serial.rts=False
            board.enter_raw_repl(soft_reset=False)
            board.exec_((ROOT/'firmware/radio.py').read_text())
            listener=socket.socket(); listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            listener.bind(('127.0.0.1',self.tcp_port)); listener.listen(1); listener.settimeout(1)
            with listener:
                while not self.stop.is_set():
                    try: conn,_=listener.accept()
                    except socket.timeout: continue
                    with conn:
                        conn.settimeout(.025)
                        while not self.stop.is_set():
                            data=b''
                            try:
                                data=conn.recv(4096)
                                if not data: break
                            except socket.timeout: pass
                            result=board.exec_(f'print(transfer({data.hex()!r}))',timeout=3).strip()
                            if result: conn.sendall(bytes.fromhex(result.decode()))
        except Exception as exc:
            self.error=str(exc); logging.exception('UART tunnel failed')
        finally:
            if board:
                with contextlib.suppress(Exception): board.exit_raw_repl(); board.close()

def parse_mac_energy(data, channels):
    # TI SWRA198 MAC_SCAN_CNF: status, ED, type, page, unscanned mask,
    # result count, result byte length, then energy array.
    if len(data)<10: raise RuntimeError('Truncated MAC scan confirmation')
    if data[0]!=0 or data[2]!=0 or data[3]!=0:
        raise RuntimeError(f'Unexpected MAC scan status/type/page: {data[:4].hex()}')
    mask=int.from_bytes(data[4:8],'little')
    if any(mask & (1<<ch) for ch in channels): raise RuntimeError('Radio did not scan all requested channels')
    count,maximum=data[8:10]; values=data[10:]
    if len(values)<maximum or count>maximum: raise RuntimeError('Truncated MAC energy array')
    if count==len(channels): energies=values[:count]
    elif count>max(channels) and all(values[ch]==255 for ch in range(count) if ch not in channels):
        energies=[values[ch] for ch in channels]
    else: raise RuntimeError(f'Unrecognized channel mapping: count={count}, bytes={len(values)}')
    return [{'channel':ch,'raw':int(v),'percent':round(v*100/255,1)} for ch,v in zip(channels,energies,strict=True)]

async def collector(port):
    from zigpy_znp.zigbee.application import ControllerApplication
    import zigpy_znp.commands as c
    import zigpy_znp.types as t
    tunnel=UARTTunnel(port)
    worker=threading.Thread(target=tunnel.run,daemon=True)
    worker.start()
    await asyncio.sleep(2)
    if tunnel.error: raise RuntimeError(tunnel.error)
    app=ControllerApplication({'device':{'path':'socket://127.0.0.1:8766'},'database_path':None})
    try:
        await app.connect()
        znp=app._znp
        version=await znp.request(c.SYS.Version.Req())
        with lock: state.update(status='starting_radio',error=None,radio=str(version))
        queue=asyncio.Queue()
        original=znp.frame_received
        def frame_received(frame):
            if frame.header.id==0x8c and frame.header.subsystem==t.Subsystem.MAC:
                queue.put_nowait(bytes(frame.data)); return True
            return original(frame)
        znp.frame_received=frame_received
        with lock: state.update(status='scanning',error=None)
        async def energy_scan(channels):
            while not queue.empty(): queue.get_nowait()
            await znp.request(c.MAC.ScanReq.Req(ScanChannels=t.Channels.from_channel_list(channels),
                ScanType=0,ScanDuration=2,ChannelPage=0,MaxResults=32,KeySource=[0]*8,
                SecurityLevel=0,KeyIdMode=0,KeyIndex=0),RspStatus=t.Status.SUCCESS)
            data=await asyncio.wait_for(queue.get(),20)
            return parse_mac_energy(data,channels)
        # Validate the channel-indexed legacy reply against two single-channel scans.
        for channel in (11,26):
            probe=await energy_scan([channel])
            logging.info('Single-channel validation %s',probe)
        while True:
            values=await energy_scan(list(range(11,27)))
            total=failures=None
            if len(values)!=16: raise RuntimeError(f'Incomplete scan: {len(values)} channels')
            now=time.time()
            record={'time':now,'channels':values,'transmissions':total,'failures':failures}
            observatory.add_scan(record)
            with lock:
                state.update(status='scanning',error=None,updated=now,channels=values)
                state['scans']+=1; state['history']=(state['history']+[record])[-120:]
            with (ROOT/'data/scans.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
            await asyncio.sleep(2)
    finally:
        with contextlib.suppress(Exception): await asyncio.wait_for(app.shutdown(),5)
        tunnel.stop.set()
        await asyncio.to_thread(worker.join,5)

async def collect_task(app):
    if app.get('transport')=='portable':
        with lock: state.update(status='awaiting_device',transport='portable',detail='Waiting for a Wi-Fi survey upload')
        return
    try:
        while True:
            progress_file=ROOT/'data/provision.json'
            progress=json.loads(progress_file.read_text()) if progress_file.exists() else {}
            if progress.get('stage')=='flashing' and (ROOT/'provision.log').exists():
                with (ROOT/'provision.log').open('rb') as f:
                    f.seek(0,2); end=f.tell(); f.seek(max(0,end-4096)); tail=f.read().decode(errors='replace')
                matches=re.findall(r'Writing at .*?\((\d+) %\)',tail)
                if matches: progress['detail']='Installing ESP32 interface: '+matches[-1]+'%'
            with lock: state.update(status=progress.get('stage','awaiting_firmware'),detail=progress.get('detail'),error=progress.get('detail') if progress.get('stage')=='error' else None)
            if progress.get('stage')=='ready': break
            await asyncio.sleep(2)
        while True:
            try:
                await collector(app['serial_port'])
            except asyncio.CancelledError: raise
            except Exception as exc:
                logging.exception('Scanner disconnected; retrying in five seconds')
                with lock: state.update(status='error',error=str(exc) or type(exc).__name__)
                await asyncio.sleep(5)
    except asyncio.CancelledError: raise
    except Exception as exc:
        logging.exception('Scanner stopped')
        with lock: state.update(status='error',error=str(exc))

async def api(request):
    with lock:
        state['settings']=observatory.settings
        state['networks']=observatory.settings['networks']
        return web.json_response(state)
async def networks(request):
    try: settings=observatory.configure({'networks':await request.json()})
    except ValueError as exc: raise web.HTTPBadRequest(text=str(exc))
    return web.json_response(settings)
async def settings(request):
    if request.method=='GET': return web.json_response(observatory.settings)
    try: result=observatory.configure(await request.json())
    except ValueError as exc: raise web.HTTPBadRequest(text=str(exc))
    return web.json_response(result)
async def events(request):
    try: result=observatory.add_event(await request.json())
    except ValueError as exc: raise web.HTTPBadRequest(text=str(exc))
    return web.json_response(result,status=201)
async def sessions(request):
    try: observatory.session(await request.json())
    except ValueError as exc: raise web.HTTPBadRequest(text=str(exc))
    return web.json_response(observatory.settings)
async def analysis(request):
    try:
        minutes=int(request.query.get('minutes','15'))
        if not 1<=minutes<=1440: raise ValueError('Window must be between 1 minute and 24 hours')
        result=observatory.summary(minutes,request.query.get('location') or None,request.query.get('session') or None)
    except ValueError as exc: raise web.HTTPBadRequest(text=str(exc))
    headers={}
    if request.query.get('download')=='1': headers['Content-Disposition']='attachment; filename="zigbee-correlation-report.json"'
    return web.json_response(result,headers=headers)
async def index(request): return web.FileResponse(ROOT/'dashboard/index.html')
async def export(request):
    path=ROOT/'data/scans.jsonl'
    if not path.exists(): raise web.HTTPNotFound(text='No measurements recorded yet')
    return web.FileResponse(path)
async def ihost_export(request):
    path=ROOT/'data/ihost-export-summary.json'
    if not path.exists(): raise web.HTTPNotFound(text='No iHost export imported')
    return web.json_response(json.loads(path.read_text()))
async def portable_status(request):return await request.app['portable_receiver'].status(request)
async def portable_qr(request):return await request.app['portable_receiver'].qr(request)
async def portable_access(request):return await request.app['portable_receiver'].access(request)
async def startup(app):
    receiver=Receiver(observatory,state,lock,ROOT)
    app['portable_receiver']=receiver
    routes=[('GET','/',index),('GET','/api/state',api),('GET','/api/analysis',analysis),
        ('GET','/api/settings',settings),('POST','/api/settings',settings),('POST','/api/networks',networks),
        ('POST','/api/events',events),('POST','/api/sessions',sessions),('GET','/api/export',export),
        ('GET','/api/ihost-export',ihost_export),('GET','/api/portable/status',receiver.status),
        ('GET','/api/portable/access',receiver.access)]
    await receiver.start(routes)
    app['scanner_task']=asyncio.create_task(collect_task(app))
async def cleanup(app):
    app['scanner_task'].cancel()
    with contextlib.suppress(asyncio.CancelledError): await app['scanner_task']
    await app['portable_receiver'].close()

def main():
    global observatory
    parser=argparse.ArgumentParser(); parser.add_argument('--port',default=None); parser.add_argument('--http-port',type=int,default=8765)
    args=parser.parse_args(); logging.basicConfig(level=logging.INFO)
    (ROOT/'data').mkdir(exist_ok=True)
    observatory=Observatory(ROOT/'data')
    app=web.Application(); app['serial_port']=args.port
    transport=ROOT/'data/transport.json'
    app['transport']=json.loads(transport.read_text()).get('mode','uart') if transport.exists() else 'uart'
    if app['transport']=='uart' and not app['serial_port']:
        from hardware import serial_port
        app['serial_port']=serial_port()
    app.router.add_get('/',index); app.router.add_get('/api/state',api); app.router.add_post('/api/networks',networks)
    app.router.add_get('/api/export',export)
    app.router.add_get('/api/settings',settings); app.router.add_post('/api/settings',settings)
    app.router.add_post('/api/events',events); app.router.add_post('/api/sessions',sessions)
    app.router.add_get('/api/analysis',analysis)
    app.router.add_get('/api/ihost-export',ihost_export)
    app.router.add_get('/api/portable/qr',portable_qr)
    app.router.add_get('/api/portable/status',portable_status); app.router.add_get('/api/portable/access',portable_access)
    app.router.add_static('/dashboard/',ROOT/'dashboard',show_index=False)
    app.on_startup.append(startup); app.on_cleanup.append(cleanup)
    web.run_app(app,host='127.0.0.1',port=args.http_port)
if __name__=='__main__': main()

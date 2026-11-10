"""Local HTTP application service; MOCK adapter only, no ROS imports."""
import copy
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import uuid

CORE = Path(__file__).resolve().parents[1] / 'backup_server'
sys.path.insert(0, str(CORE))
from engine import Coordinator

CONFIG = json.loads((CORE / 'scenario.mock.json').read_text())

class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)

class MockAdapter:
    """Future SIM_NAV2/REAL_NAV2 adapters must provide the same service boundary."""
    def __init__(self):
        self.coordinator = Coordinator(copy.deepcopy(CONFIG))
        self.coordinator.events.clear()
        for robot in self.coordinator.robots.values():
            robot.update(task_state='IDLE', phase='IDLE', task_id=None)
        self.started = set()

    def start(self, ids, session):
        c = self.coordinator
        if c.canceled or c.blocked_reason:
            raise RequestError(409, '중단된 모의 세션입니다. 진행 작업을 취소하고 모의 세션을 초기화하세요.')
        if any(name in self.started for name in ids):
            raise RequestError(409, '이 세션에서 이미 요청한 로봇입니다. 재시연하려면 모의 세션을 초기화하세요.')
        for name in ids:
            r = c.robots[name]
            r.update(task_id=f'{session}:{name}', task_state='RUNNING', phase='TO_WAIT')
            self.started.add(name)
            c.emit('TASK_ACCEPTED', name, 'TO_WAIT', f"{r['destination']} 이동 후 회전")

    def tick(self, dt):
        c = self.coordinator
        if not c.canceled and any(r['task_state']=='RUNNING' for r in c.robots.values()):
            c.tick(dt)

    def cancel(self, target):
        c = self.coordinator
        if target=='all':
            if any(r['task_state']=='RUNNING' for r in c.robots.values()):
                c.cancel_all()
        elif c.robots[target]['task_state']=='RUNNING':
            c.cancel_robot(target)

class AppService:
    def __init__(self, log_dir=None, map_review=None, adapter=None):
        self.map_review=copy.deepcopy(map_review)
        self.lock=threading.RLock()
        self.adapter=adapter if adapter is not None else MockAdapter()
        self.mode='SIM_NAV2' if hasattr(self.adapter,'snapshot') else ('MAP_REVIEW' if self.map_review else 'MOCK')
        self.session=uuid.uuid4().hex[:8]
        self.cache={}
        self.events=[]
        self.seq=0
        self.closed=False
        self.event_cursor=0
        self.stop_event=threading.Event()
        self.log=None
        if log_dir is not None:
            log_dir=Path(log_dir); log_dir.mkdir(parents=True,exist_ok=True)
            self.log=(log_dir/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.jsonl')).open('a')
        self.emit('SESSION_CREATED',None,'Gazebo SIM_NAV2 세션 준비 (도메인 84).' if self.mode=='SIM_NAV2' else '모의 세션 준비. 실물 명령 없음.')

    def emit(self,event,robot,reason,phase=None,owner=None):
        self.seq+=1
        row=dict(seq=self.seq,timestamp=datetime.now(timezone.utc).isoformat(),session_id=self.session,
                 event=event,robot_id=robot,reason=reason,phase=phase,owner=owner,mode=self.mode if self.mode=='SIM_NAV2' else 'MOCK')
        self.events.append(row)
        if len(self.events)>500:self.events=self.events[-500:]
        if self.log:
            self.log.write(json.dumps(row,ensure_ascii=False)+'\n');self.log.flush()

    def collect(self):
        source=self.adapter.events if hasattr(self.adapter,'events') else self.adapter.coordinator.events
        for row in source[self.event_cursor:]:
            self.emit(row['event'],row['robot_id'],row['reason'],row.get('phase'),row.get('owner'))
        self.event_cursor=len(source)

    def tick(self,dt=0.05):
        with self.lock:
            self.adapter.tick(dt);self.collect()

    def snapshot(self):
        with self.lock:
            if hasattr(self.adapter,'snapshot'):
                data=self.adapter.snapshot()
                data.update(session_id=self.session,events=copy.deepcopy(self.events))
                return data
            c=self.adapter.coordinator
            s=c.snapshot()
            for r in s['robots']:
                r.update(connection='MOCK_CONNECTED',battery_percent=None,
                         stopped_confirmed=(r['task_state'] in ('IDLE','SUCCEEDED','CANCELED','FAILED') or r['phase']=='WAITING_ZONE'))
            return dict(mode='MAP_REVIEW' if self.map_review else 'MOCK',map_review=copy.deepcopy(self.map_review),
                commands_locked=bool(self.map_review),available_modes=['MAP_REVIEW'] if self.map_review else ['MOCK'],locked_modes=['SIM_NAV2','REAL_NAV2'],
                session_id=self.session,active=any(r['task_state']=='RUNNING' for r in c.robots.values()),
                zone=dict(id=c.zone['id'],owner=c.owner,waiting=list(c.waiting),blocked_reason=c.blocked_reason,
                          occupants=[r['id'] for r in c.robots.values() if c.overlaps(r['position'])]),
                simulation=s,layout=copy.deepcopy(CONFIG),events=copy.deepcopy(self.events),
                started=sorted(self.adapter.started))

    def command(self,path,body):
        with self.lock:
            if not isinstance(body,dict):raise RequestError(400,'JSON object required')
            request_id=body.get('request_id')
            if not isinstance(request_id,str) or not 1<=len(request_id)<=128:
                raise RequestError(400,'request_id required (1–128 characters)')
            signature=json.dumps([path,body],sort_keys=True,ensure_ascii=False)
            if request_id in self.cache:
                previous,reply=self.cache[request_id]
                if previous!=signature:raise RequestError(409,'request_id reused with different content')
                return dict(reply,replayed=True)
            if len(self.cache)>=10000:raise RequestError(429,'Request cache full; restart local application')
            if body.get('session_id')!=self.session:
                raise RequestError(409,'오래된 세션 요청입니다. 현재 상태를 다시 조회하세요.')
            expected_mode='SIM_NAV2' if self.mode=='SIM_NAV2' else 'MOCK'
            if body.get('mode','MOCK')!=expected_mode:raise RequestError(409,'실물·Nav2 시뮬레이션 모드는 아직 잠겨 있거나 현재 모드와 다릅니다.')
            if self.map_review and path in ('/api/v1/tasks','/api/v1/cancel','/api/v1/reset'):
                raise RequestError(409,'지도 확인 모드: 목적지·대기점·공유존 미설정으로 작업 명령이 잠겨 있습니다.')
            if path=='/api/v1/tasks':
                mission=body.get('mission')
                ids={'scenario':['robot_1','robot_2'],'work_B':['robot_1'],'work_A':['robot_2']}.get(mission)
                if ids is None:raise RequestError(400,'Unknown registered mission')
                self.adapter.start(ids,self.session)
            elif path=='/api/v1/cancel':
                target=body.get('target')
                if target not in ['all','robot_1','robot_2']:raise RequestError(400,'Invalid target')
                self.adapter.cancel(target)
            elif path=='/api/v1/reset':
                active=self.adapter.snapshot()['active'] if hasattr(self.adapter,'snapshot') else any(r['task_state']=='RUNNING' for r in self.adapter.coordinator.robots.values())
                if active:
                    raise RequestError(409,'먼저 진행 중인 작업을 취소하세요.')
                if body.get('confirm') is not True:raise RequestError(400,'Reset confirmation required')
                if hasattr(self.adapter,'reset'):
                    self.adapter.reset()
                    self.event_cursor=len(self.adapter.events)
                    self.session=uuid.uuid4().hex[:8]
                    self.emit('SESSION_RESET',None,'Gazebo 시뮬레이션 세션 초기화 완료.')
                else:
                    self.adapter=MockAdapter();self.event_cursor=0;self.session=uuid.uuid4().hex[:8]
                    self.emit('SESSION_RESET',None,'모의 좌표·예약 초기화. 실제 복귀 명령 아님.')
            else:raise RequestError(404,'Unknown command route')
            self.collect()
            reply=dict(status='ACCEPTED',request_id=request_id,session_id=self.session,replayed=False)
            self.cache[request_id]=(signature,reply)
            return reply

    def run(self):
        while not self.stop_event.wait(0.05):
            try:self.tick()
            except Exception as exc:
                with self.lock:
                    if hasattr(self.adapter,'cancel'):self.adapter.cancel('all')
                    if hasattr(self.adapter,'coordinator') and hasattr(self.adapter.coordinator,'fail_all'):
                        self.adapter.coordinator.fail_all('Internal simulation error')
                    self.collect();self.emit('SERVER_ERROR',None,str(exc))
                self.stop_event.set()

    def close(self):
        self.stop_event.set()
        with self.lock:
            if self.closed:return
            self.closed=True
            if hasattr(self.adapter,'close'):self.adapter.close()
            else:self.adapter.cancel('all')
            self.collect()
            if self.log:self.log.close()


def create_http(service,port=8765):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data):
            raw=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def authorized(self):
            host=self.headers.get('Host','')
            if host not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
                raise RequestError(403,'Invalid Host')
            if not hmac.compare_digest(self.headers.get('X-CAS-Token',''),token):
                raise RequestError(403,'Invalid local session token')
        def do_GET(self):
            try:
                self.authorized()
                if self.path!='/api/v1/state':raise RequestError(404,'Unknown route')
                self.reply(200,service.snapshot())
            except RequestError as exc:self.reply(exc.status,dict(error=str(exc)))
        def do_POST(self):
            try:
                self.authorized()
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise RequestError(415,'application/json required')
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:raise RequestError(400,'Invalid content length')
                if not 0<length<=8192:raise RequestError(413,'Body length must be 1–8192 bytes')
                self.connection.settimeout(3)
                try:body=json.loads(self.rfile.read(length))
                except (ValueError,UnicodeError):raise RequestError(400,'Invalid JSON')
                self.reply(200,service.command(self.path,body))
            except RequestError as exc:self.reply(exc.status,dict(error=str(exc)))
            except TimeoutError:self.reply(408,dict(error='Request timeout'))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server,token

"""Local HTTP boundary for the physical CAS dashboard only."""
import copy
from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import uuid


class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class AppService:
    def __init__(self, log_dir=None, adapter=None):
        if adapter is None:
            raise ValueError('Physical adapter required')
        self.adapter = adapter
        self.mode = 'REAL_NAV2'
        self.session = uuid.uuid4().hex[:8]
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.events = []
        self.event_cursor = 0
        self.seq = 0
        self.closed = False
        self.log = None
        if log_dir:
            folder = Path(log_dir)
            folder.mkdir(parents=True, exist_ok=True)
            self.log = (folder/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.jsonl')).open('a')
        self.emit('SESSION_CREATED', None, '실물 관제 준비 (도메인 14/30)')

    def emit(self, event, robot, reason, phase=None, owner=None):
        self.seq += 1
        row = dict(seq=self.seq, timestamp=datetime.now(timezone.utc).isoformat(),
                   session_id=self.session, event=event, robot_id=robot,
                   reason=reason, phase=phase, owner=owner, mode=self.mode)
        self.events.append(row)
        if len(self.events) > 500:
            self.events = self.events[-500:]
        if self.log:
            self.log.write(json.dumps(row, ensure_ascii=False)+'\n')
            self.log.flush()

    def collect(self):
        for row in self.adapter.events[self.event_cursor:]:
            self.emit(row['event'], row['robot_id'], row['reason'], row.get('phase'), row.get('owner'))
        self.event_cursor = len(self.adapter.events)

    def tick(self, dt=.05):
        with self.lock:
            self.adapter.tick(dt)
            self.collect()

    def snapshot(self):
        with self.lock:
            state = self.adapter.snapshot()
            state.update(session_id=self.session, events=copy.deepcopy(self.events))
            return state

    def command(self, path, body):
        with self.lock:
            if not isinstance(body, dict):
                raise RequestError(400, 'JSON object required')
            if body.get('mode') != self.mode or body.get('session_id') != self.session:
                raise RequestError(409, '현재 실물 세션과 다른 요청입니다.')
            if path == '/api/v1/tasks':
                ids = {'scenario':['robot_1','robot_2'], 'work_B':['robot_1'], 'work_A':['robot_2']}.get(body.get('mission'))
                if ids is None:
                    raise RequestError(400, 'Unknown mission')
                self.adapter.start(ids, self.session)
            elif path == '/api/v1/cancel':
                target = body.get('target')
                if target not in ('all','robot_1','robot_2'):
                    raise RequestError(400, 'Invalid target')
                self.adapter.cancel(target)
            elif path == '/api/v1/return-home':
                self.adapter.return_home()
            else:
                raise RequestError(404, 'Unknown command route')
            self.collect()
            return dict(status='ACCEPTED', session_id=self.session)

    def run(self):
        while not self.stop_event.wait(.05):
            try:
                self.tick()
            except Exception as exc:
                with self.lock:
                    self.adapter.halt(str(exc))
                    self.collect()
                self.stop_event.set()

    def close(self):
        self.stop_event.set()
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.adapter.close()
            self.collect()
            if self.log:
                self.log.close()


def create_http(service, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            if not hmac.compare_digest(self.headers.get('X-CAS-Token',''), token):
                raise RequestError(403, 'Invalid local token')

        def do_GET(self):
            try:
                self.authorized()
                if self.path != '/api/v1/state':
                    raise RequestError(404, 'Unknown route')
                self.reply(200, service.snapshot())
            except RequestError as exc:
                self.reply(exc.status, {'error':str(exc)})

        def do_POST(self):
            try:
                self.authorized()
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise RequestError(415, 'application/json required')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 8192:
                    raise RequestError(400, 'Invalid body length')
                self.connection.settimeout(3)
                self.reply(200, service.command(self.path, json.loads(self.rfile.read(length))))
            except RequestError as exc:
                self.reply(exc.status, {'error':str(exc)})
            except (ValueError, UnicodeError):
                self.reply(400, {'error':'Invalid JSON or body length'})
            except TimeoutError:
                self.reply(408, {'error':'Request timeout'})

    server = ThreadingHTTPServer(('127.0.0.1',port), Handler)
    server.daemon_threads = True
    return server, token

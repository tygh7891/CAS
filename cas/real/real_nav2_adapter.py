"""Physical two-domain adapter. Nav2 owns motion; this PC owns zone permission."""
import copy
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

from map_geometry import review_maps

ROBOTS = ('robot_1', 'robot_2')
RADIUS = 0.108  # Encloses the measured rectangle including 1 cm padding.


def zone_distance(pose, zone):
    return math.hypot(max(zone['xmin'] - pose[0], 0, pose[0] - zone['xmax']),
                      max(zone['ymin'] - pose[1], 0, pose[1] - zone['ymax']))


def wait_point(start, goal, zone):
    # Locate the true rectangle entry, then stop at a Euclidean distance of
    # 16 cm. This avoids the excessive diagonal gap of a square expansion.
    clearance = 0.16
    lo, hi = 0.0, 1.0
    for axis, low, high in ((0, zone['xmin'], zone['xmax']),
                            (1, zone['ymin'], zone['ymax'])):
        delta = goal[axis] - start[axis]
        if abs(delta) < 1e-9:
            if not low <= start[axis] <= high:
                raise ValueError('Approach does not intersect the shared zone')
            continue
        a, b = sorted(((low-start[axis])/delta, (high-start[axis])/delta))
        lo, hi = max(lo, a), min(hi, b)
    if lo > hi or zone_distance(start, zone) < clearance:
        raise ValueError('No outside waiting point on the approach')
    left, right = 0.0, lo
    for _ in range(50):
        t = (left+right)/2
        point = [start[i]+t*(goal[i]-start[i]) for i in (0,1)]
        if zone_distance(point, zone) > clearance:
            left = t
        else:
            right = t
    t = (left+right)/2
    yaw = math.atan2(goal[1]-start[1], goal[0]-start[0])
    return [start[0]+t*(goal[0]-start[0]), start[1]+t*(goal[1]-start[1]), yaw]


class RealNav2Adapter:
    mode = 'REAL_NAV2'

    def __init__(self, config_path, request_error_cls=RuntimeError, start_workers=True):
        self.error_cls = request_error_cls
        config_path = Path(config_path).expanduser().resolve()
        self.config = json.loads(config_path.read_text())
        for key in ('map','mask'):
            self.config[key] = str((config_path.parent/self.config[key]).resolve())
        self.zone = self.config['zone']
        self.map_review = review_maps(self.config['map'], self.config['mask'], 'allowed')
        self.points = self.config['robots']
        self.waits = {n: wait_point(self.points[n]['start'], self.points[n]['goal'], self.zone) for n in ROBOTS}
        z = self.zone
        self.map_review['candidates'] = {
            'shared_zone': {'polygon': [[z['xmin'],z['ymin']], [z['xmax'],z['ymin']],
                                        [z['xmax'],z['ymax']], [z['xmin'],z['ymax']]]},
            'points': {}, 'waiting': {}}
        for n in ROBOTS:
            for label, xy in ((n[-1], self.points[n]['start']),
                              (self.points[n]['destination'], self.points[n]['goal'])):
                self.map_review['candidates']['points'][label] = {'x':xy[0], 'y':xy[1]}
        self.live_map = None
        self.events = []
        self.started = set()
        self.owner = None
        self.waiting = []
        self.blocked = None
        self.returning = False
        self.return_queue = []
        self.pending_returns = False
        self.rows = {n: {'phase':'IDLE', 'task_state':'IDLE', 'command':None,
                         'entered':False, 'stop_since':None} for n in ROBOTS}
        self.telemetry = {n: {} for n in ROBOTS}
        self.received = {n: 0.0 for n in ROBOTS}
        self.inbox = queue.Queue()
        self.processes = {}
        self.log_handles = []
        if start_workers:
            self.launch_workers()

    def reject(self, message):
        raise self.error_cls(409, message)

    def emit(self, event, name, reason):
        self.events.append(dict(event=event, robot_id=name, reason=reason,
                                phase=self.rows[name]['phase'] if name else None, owner=self.owner))

    def phase(self, name, phase):
        self.rows[name]['phase'] = phase
        self.emit('PHASE_CHANGED', name, phase)

    def launch_workers(self):
        logs = Path(__file__).parent/'logs'
        logs.mkdir(exist_ok=True)
        try:
            for n in ROBOTS:
                env = dict(os.environ, ROS_DOMAIN_ID=str(self.points[n]['domain']),
                           ROS_AUTOMATIC_DISCOVERY_RANGE='SUBNET', PYTHONUNBUFFERED='1')
                env.pop('ROS_LOCALHOST_ONLY', None)
                env.pop('ROS_DISCOVERY_SERVER', None)
                log = (logs/f'{n}_physical_{time.time_ns()}.log').open('w')
                self.log_handles.append(log)
                p = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('real_worker.py'))],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                     text=True, env=env)
                self.processes[n] = p
                threading.Thread(target=self.read_worker, args=(n,p), daemon=True).start()
        except Exception:
            self.close()
            raise

    def read_worker(self, name, process):
        for line in process.stdout:
            try:
                data = json.loads(line)
                if isinstance(data, dict) and 'ready' in data:
                    self.inbox.put((name, data, time.monotonic()))
            except ValueError:
                pass

    def send(self, name, command):
        process = self.processes.get(name)
        if process:
            process.stdin.write(json.dumps(command)+'\n')
            process.stdin.flush()

    def fresh(self, name):
        st = self.telemetry[name]
        return (time.monotonic()-self.received[name] < 2 and st.get('pose') is not None
                and st.get('velocity') is not None and st.get('ready',False))

    def stopped(self, name):
        v = self.telemetry[name].get('velocity')
        return self.fresh(name) and v is not None and abs(v[0]) < .01 and abs(v[1]) < .03

    def occupied(self, name):
        pose = self.telemetry[name].get('pose')
        return pose is not None and zone_distance(pose, self.zone) <= RADIUS

    def navigate(self, name, target, phase):
        cid = uuid.uuid4().hex
        self.rows[name]['command'] = cid
        self.phase(name, phase)
        self.send(name, {'id':cid, 'kind':'NAVIGATE', 'target':target})

    def spin(self, name):
        cid = uuid.uuid4().hex
        self.rows[name]['command'] = cid
        self.phase(name, 'SPINNING')
        self.send(name, {'id':cid, 'kind':'SPIN', 'angle':2*math.pi})

    def halt(self, reason):
        if self.blocked:
            return
        self.blocked = reason
        self.returning = False
        self.return_queue.clear()
        for n in ROBOTS:
            self.send(n, {'kind':'CANCEL'})
            if self.rows[n]['task_state'] == 'RUNNING':
                self.rows[n]['task_state'] = 'FAILED'
                self.phase(n, 'HALTED')
        self.emit('HALTED', None, reason)

    def start(self, ids, session):
        if self.returning or self.pending_returns or self.blocked:
            self.reject('복귀 중이거나 중단 상태입니다. 출발점 복귀를 먼저 완료하세요.')
        if not all(self.fresh(n) for n in ROBOTS):
            self.reject('두 로봇의 위치·주행 연결을 기다리고 있습니다.')
        for n in ids:
            if n in self.started or self.telemetry[n].get('busy'):
                self.reject('이미 요청한 로봇입니다. 출발점 복귀 후 다시 시작하세요.')
            pose = self.telemetry[n]['pose']
            if math.dist(pose[:2], self.points[n]['start'][:2]) > .15:
                self.reject('출발 위치에서 벗어났습니다. 출발점 복귀를 먼저 실행하세요.')
        for n in ids:
            self.started.add(n)
            self.rows[n].update(task_state='RUNNING', entered=False)
            self.navigate(n, self.waits[n], 'TO_WAIT')

    def cancel(self, target):
        names = ROBOTS if target == 'all' else (target,)
        if self.pending_returns:
            self.pending_returns = False
            self.return_queue.clear()
        # While homing, cancel the complete return sequence.
        if self.returning:
            names = ROBOTS
            self.return_queue.clear()
            self.returning = False
        for n in names:
            self.send(n, {'kind':'CANCEL'})
            self.rows[n]['command'] = None
            if n in self.waiting:
                self.waiting.remove(n)
            if self.rows[n]['task_state'] == 'RUNNING':
                self.rows[n]['task_state'] = 'CANCELED'
                self.phase(n, 'CANCELED')
        if self.owner in names:
            self.blocked = '진입권 보유 작업 취소: 출발점 복귀 필요'
        self.emit('CANCELED', None, '작업 취소 요청')

    def return_home(self):
        if self.returning or self.pending_returns:
            self.reject('이미 출발점 복귀 중입니다.')
        if not all(self.fresh(n) for n in ROBOTS):
            self.reject('두 로봇의 위치·주행 연결이 필요합니다.')
        self.cancel('all')
        self.pending_returns = True
        self.emit('RETURN_REQUESTED', None, '기존 작업 정지 후 순차 출발점 복귀')

    def tick(self, dt=.05):
        while not self.inbox.empty():
            n, data, received = self.inbox.get()
            if n == 'robot_1' and data.get('live_map'):
                self.live_map = data.pop('live_map')
            self.telemetry[n], self.received[n] = data, received
        for n in ROBOTS:
            r = self.rows[n]
            if self.stopped(n):
                if r['stop_since'] is None:
                    r['stop_since'] = time.monotonic()
            else:
                r['stop_since'] = None
        if self.pending_returns:
            if all(self.fresh(n) and not self.telemetry[n].get('busy') and self.stopped(n) for n in ROBOTS):
                occupants = [n for n in ROBOTS if self.occupied(n)]
                if len(occupants) > 1:
                    self.pending_returns = False
                    self.blocked = '두 로봇이 공유존에 겹쳐 있어 자동 복귀를 시작할 수 없습니다.'
                    return
                self.blocked = None
                self.owner = None
                self.waiting.clear()
                self.return_queue = occupants + [n for n in ROBOTS if n not in occupants]
                self.returning = True
                self.pending_returns = False
                self.next_return()
            return
        active = any(r['task_state']=='RUNNING' for r in self.rows.values())
        if active and not all(self.fresh(n) for n in ROBOTS):
            self.halt('실물 위치·주행 상태 수신 중단')
        if self.blocked:
            return
        if not self.returning:
            for n in ROBOTS:
                if self.occupied(n) and self.owner != n:
                    if active:
                        self.halt(f'{n}: 진입권 없이 공유존 본체 진입')
                    return
        for n in ROBOTS:
            r, st = self.rows[n], self.telemetry[n]
            if r['phase'] == 'CROSSING':
                r['entered'] |= self.occupied(n)
                pose = st.get('pose')
                if pose and r['entered'] and pose[0] < self.zone['xmin']-RADIUS-.02:
                    self.owner = None
                    self.emit('ZONE_RELEASED', n, '목적지 방향 본체 전체 이탈')
                    self.phase(n, 'TO_GOAL')
            result = st.get('result')
            if not result or result['id'] != r['command']:
                continue
            r['command'] = None
            if not result['ok']:
                self.halt(f'{n}: {result["detail"]}')
                return
            phases = {'TO_WAIT':'VERIFY_WAIT', 'CROSSING':'VERIFY_GOAL', 'TO_GOAL':'VERIFY_GOAL',
                      'SPINNING':'VERIFY_DONE', 'RETURNING':'VERIFY_HOME'}
            self.phase(n, phases.get(r['phase'], r['phase']))
        for n in ROBOTS:
            r = self.rows[n]
            if not self.stopped(n) or r['stop_since'] is None or time.monotonic()-r['stop_since'] < .3:
                continue
            if r['phase'] == 'VERIFY_WAIT':
                if self.occupied(n):
                    self.halt('대기 위치에서 본체가 공유존에 걸렸습니다.')
                    return
                self.waiting.append(n)
                self.phase(n, 'WAITING_ZONE')
            elif r['phase'] == 'VERIFY_GOAL':
                if self.owner == n:
                    self.halt('목적지 도착 후에도 공유존 이탈이 확인되지 않았습니다.')
                    return
                self.spin(n)
            elif r['phase'] == 'VERIFY_DONE':
                r['task_state'] = 'SUCCEEDED'
                self.phase(n, 'DONE')
            elif r['phase'] == 'VERIFY_HOME':
                r['task_state'] = 'IDLE'
                self.phase(n, 'IDLE')
                self.owner = None
                self.next_return()
        if not self.returning and self.owner is None and self.waiting:
            n = self.waiting[0]
            if all(self.fresh(other) and not self.occupied(other) for other in ROBOTS):
                self.waiting.pop(0)
                self.owner = n
                self.emit('ZONE_GRANTED', n, '공유존 단독 진입 허가')
                goal = self.points[n]['goal']
                self.navigate(n, [*goal[:2], self.waits[n][2]], 'CROSSING')

    def next_return(self):
        if not self.return_queue:
            self.returning = False
            self.started.clear()
            self.blocked = None
            self.emit('RETURN_COMPLETED', None, '두 로봇 출발점·초기 방향 복귀 완료')
            return
        n = self.return_queue.pop(0)
        if any(self.occupied(other) for other in ROBOTS if other != n):
            self.halt('다른 로봇이 공유존에 있어 복귀를 시작할 수 없습니다.')
            self.returning = False
            return
        self.owner = n  # Return is serialized; reserve before the complete route.
        self.started.add(n)
        self.rows[n]['task_state'] = 'RUNNING'
        self.navigate(n, self.points[n]['start'], 'RETURNING')

    def snapshot(self):
        rows = []
        ready = all(self.fresh(n) for n in ROBOTS)
        for n in ROBOTS:
            st, r = self.telemetry[n], self.rows[n]
            pose = st.get('pose')
            rows.append(dict(id=n, destination=self.points[n]['destination'],
                             phase=r['phase'], task_state=r['task_state'],
                             position=[round(x,3) for x in pose[:2]] if pose else None,
                             yaw=pose[2] if pose else 0, pose_valid=self.fresh(n),
                             pose_age_s=time.monotonic()-self.received[n] if self.received[n] else None,
                             connection='REAL_NAV2_OK' if self.fresh(n) else 'REAL_NAV2_WAIT',
                             stopped_confirmed=self.stopped(n), battery_percent=None))
        active = self.pending_returns or any(r['task_state']=='RUNNING' for r in self.rows.values())
        return dict(mode=self.mode, map_review=copy.deepcopy(self.map_review), live_map=self.live_map,
                    commands_locked=not ready and not active, active=active,
                    returning=self.returning or self.pending_returns,
                    preflight_reason=self.blocked or ('실물 로봇 연결 정상' if ready else '실물 위치·Nav2 연결 대기'),
                    available_modes=[self.mode], locked_modes=[],
                    simulation={'robots':rows}, started=sorted(self.started), layout={'routes':{}},
                    zone=dict(id='central_shared_zone', owner=self.owner, waiting=list(self.waiting),
                              blocked_reason=self.blocked, occupants=[n for n in ROBOTS if self.occupied(n)]))

    def close(self):
        for n, p in self.processes.items():
            if p.poll() is None:
                try:
                    self.send(n, {'kind':'CANCEL'})
                except (OSError, ValueError):
                    pass
        deadline = time.monotonic()+2
        for p in self.processes.values():
            if p.poll() is None:
                try:
                    p.wait(timeout=max(.01, deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    p.send_signal(2)
        for p in self.processes.values():
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for log in self.log_handles:
            log.close()

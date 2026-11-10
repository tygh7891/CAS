"""Gazebo SIM_NAV2 adapter for the operator HTTP service (Domain 84 only)."""
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

SIM_DIR = Path(__file__).resolve().parents[1] / 'simulation'
if str(SIM_DIR) not in sys.path:
    sys.path.append(str(SIM_DIR))

from map_geometry import review_maps
from mission_routes import zone_distance
from path_geometry import ClearanceMap
from prepare_map import arrays
from zone_coordinator import MissionCoordinator, through_path

ROBOTS = ('robot_1', 'robot_2')

PHASE_MAP = {
    'IDLE': 'IDLE',
    'TO_WAIT': 'TO_WAIT',
    'VERIFY_WAIT': 'TO_WAIT',
    'WAITING': 'WAITING_ZONE',
    'CROSSING': 'CROSSING',
    'TO_GOAL': 'TO_GOAL',
    'VERIFY_GOAL': 'TO_GOAL',
    'SPINNING': 'SPINNING',
    'VERIFY_DONE': 'SPINNING',
    'DONE': 'DONE',
    'HALTED': 'HALTED',
    'CANCELED': 'HALTED',
}


def path_distance(point, path):
    minimum = float('inf')
    for a, b in zip(path, path[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = dx * dx + dy * dy
        t = 0.0 if norm == 0 else max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / norm))
        minimum = min(minimum, math.dist(point, [a[0] + t * dx, a[1] + t * dy]))
    return minimum


def build_layout(scenario, mission):
    xs = [p[0] for p in scenario['shared_zone']['polygon']]
    ys = [p[1] for p in scenario['shared_zone']['polygon']]
    return dict(
        zone=dict(
            id='central_shared_zone',
            xmin=min(xs),
            xmax=max(xs),
            ymin=min(ys),
            ymax=max(ys),
            polygon=copy.deepcopy(scenario['shared_zone']['polygon']),
        ),
        points=copy.deepcopy(scenario['points']),
        robots=[
            dict(
                id=name,
                start=list(mission[name]['start']),
                wait=list(mission[name]['wait']),
                exit=list(mission[name]['exit']),
                goal=list(mission[name]['goal']),
                destination=mission[name]['destination'],
                yaw=mission[name]['yaw'],
            )
            for name in ROBOTS
        ],
        routes={
            name: [seg['path'] for seg in mission[name]['segments']]
            for name in ROBOTS
        },
    )


class SimNav2Adapter:
    """Bridges AppService to Gazebo Domain 84 Nav2Worker + LeasePump + MissionCoordinator."""

    def __init__(self, generated_dir=None, request_error_cls=RuntimeError):
        if os.environ.get('ROS_DOMAIN_ID') != '84' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
            raise RuntimeError('SIM_NAV2 requires ROS_DOMAIN_ID=84 and ROS_LOCALHOST_ONLY=1')
        self.request_error_cls = request_error_cls
        self.folder = Path(generated_dir or (Path.home() / 'CAS_sim_ws/generated_map')).expanduser().resolve()
        self.lock_file = open(f'/tmp/cas_sim_mission_{os.getuid()}_84.lock', 'w')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.lock_file.close()
            raise RuntimeError('다른 Gazebo 미션 또는 관제 프로세스가 실행 중입니다 (domain 84 lock).') from exc

        try:
            from check_workers import load_bundle
            from nav2_worker import Nav2Worker
            from lease_pump import LeasePump
            import rclpy
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.signals import SignalHandlerOptions
            from std_msgs.msg import String
            from action_msgs.msg import GoalStatusArray

            self.scenario, self.mission, self.source_report = load_bundle(self.folder)
            metadata = json.loads((self.folder / 'map_profile_report.json').read_text())
            self.spec, _, self.allowed = arrays(metadata['source_map'], metadata['source_allowed_mask'])
            self.clearance = ClearanceMap(self.spec, self.allowed)
            self.map_review = review_maps(
                metadata['source_map'],
                metadata['source_allowed_mask'],
                'allowed',
                self.folder / 'scenario.candidates.json',
            )
            self.layout = build_layout(self.scenario, self.mission)
            self.polygon = self.scenario['shared_zone']['polygon']
            self.radius = self.scenario['robot_radius_with_margin_m']
            self.coordinator = MissionCoordinator(self.mission, self.polygon, radius=self.radius)
            self.started = set()
            self.events = []
            self.command_index = 0
            self.coord_event_index = 0
            self.last_phases = {name: 'IDLE' for name in ROBOTS}
            self.preflight_ready = False
            self.preflight_reason = 'Gazebo / Nav2 프리플라이트 점검 중...'
            self.closed = False

            self._rclpy = rclpy
            self._String = String
            if not rclpy.ok():
                rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
                self._owns_rclpy = True
            else:
                self._owns_rclpy = False
            self.executor = SingleThreadedExecutor()
            self.workers = {name: Nav2Worker(name, self.coordinator, allow_actions=True) for name in ROBOTS}
            for worker in self.workers.values():
                self.executor.add_node(worker)

            control = self.workers['robot_1']
            self.relay_session = uuid.uuid4().hex
            self.lease_pub = control.create_publisher(String, '/cas/sim_control/lease', 1)
            self.relay_state = {}
            self.external_actions = {}

            def state_callback(msg):
                value = json.loads(msg.data)
                if value.get('session') == self.relay_session:
                    self.relay_state.update(value, received=time.monotonic())

            self.subscriptions = [
                control.create_subscription(String, '/cas/sim_control/relay_state', state_callback, 1)
            ]
            for robot in ROBOTS:
                for action in ('follow_path', 'spin', 'navigate_to_pose'):
                    key = f'{robot}/{action}'
                    self.subscriptions.append(
                        control.create_subscription(
                            GoalStatusArray,
                            f'/{robot}/{action}/_action/status',
                            lambda msg, name=key: self.external_actions.update(
                                {name: any(s.status in (1, 2, 3) for s in msg.status_list)}
                            ),
                            1,
                        )
                    )

            until = time.monotonic() + 1.0
            while time.monotonic() < until:
                self._spin_once()
            if any(control.count_publishers(f'/{robot}/cmd_vel') for robot in ROBOTS):
                raise RuntimeError('외부 cmd_vel 퍼블리셔가 감지되어 SIM_NAV2 연결을 중단합니다.')

            self.relay = subprocess.Popen(
                [sys.executable, str(SIM_DIR / 'sim_velocity_relay.py'), '--session', self.relay_session],
                start_new_session=True,
            )
            self.pump = LeasePump(self.relay_session)
            self.last_lease = 0.0
            self._heartbeat({})
            self.sender_stop = threading.Event()
            self.sender = threading.Thread(target=self._send_leases, daemon=True)
            self.sender.start()
        except Exception:
            self.lock_file.close()
            raise

    def _heartbeat(self, permits):
        now = time.monotonic()
        self.pump.touch(permits, now)
        self.last_lease = now

    def _send_leases(self):
        while not self.sender_stop.is_set():
            packet = self.pump.packet(time.monotonic())
            if packet is not None and self._rclpy.ok():
                msg = self._String()
                msg.data = json.dumps(packet)
                self.lease_pub.publish(msg)
            self.sender_stop.wait(0.04)

    def _spin_once(self):
        self.executor.spin_once(timeout_sec=0.01)
        now = time.monotonic()
        for worker in self.workers.values():
            worker.poll(now)
        return now

    def _emit(self, event, robot, reason, phase=None, owner=None):
        self.events.append(
            dict(event=event, robot_id=robot, reason=reason, phase=phase, owner=owner)
        )

    def _sync_events(self):
        while self.coord_event_index < len(self.coordinator.events):
            ev = self.coordinator.events[self.coord_event_index]
            self.coord_event_index += 1
            name = ev['robot']
            kind = ev['event']
            phase = PHASE_MAP.get(self.coordinator.robots[name]['phase'], self.coordinator.robots[name]['phase'])
            if kind in ('ZONE_REQUESTED', 'ZONE_GRANTED', 'ZONE_RELEASED', 'CANCELED'):
                self._emit(kind, name, kind, phase=phase, owner=ev.get('owner'))
            elif kind == 'TASK_COMPLETED_STOP_CONFIRMED':
                self._emit('PHASE_CHANGED', name, '목적지 도착 및 회전 정지 확인', phase='DONE', owner=ev.get('owner'))
        for name in ROBOTS:
            mapped = PHASE_MAP.get(self.coordinator.robots[name]['phase'], self.coordinator.robots[name]['phase'])
            if mapped != self.last_phases[name]:
                self.last_phases[name] = mapped
                if mapped not in ('IDLE', 'DONE'):
                    self._emit('PHASE_CHANGED', name, f'단계 전환: {mapped}', phase=mapped, owner=self.coordinator.owner)

    def _evaluate_preflight(self, now):
        if self.relay.poll() is not None:
            return False, '속도 게이트(sim_velocity_relay)가 종료되었습니다.'
        if not self.relay_state or now - self.relay_state.get('received', 0.0) > 0.5:
            return False, '속도 게이트(Relay) 상태 수신 대기 중...'
        if self.relay_state.get('blocked'):
            return False, '속도 게이트(Relay)가 안전 정지(Blocked) 상태입니다.'
        for name in ROBOTS:
            st = self.workers[name].status(now)
            if not st['observation_fresh']:
                return False, f'{name} TF/Odometry 수신 대기 중 ({st["error"] or "stale"})'
            if not (st['follow_path'] and st['spin']):
                return False, f'{name} Nav2 FollowPath/Spin 액션 서버 대기 중'
            if self.coordinator.robots[name]['phase'] == 'IDLE':
                if st['pose'] is None or math.dist(st['pose'], self.mission[name]['start']) > 0.05:
                    return False, f'{name} 위치가 출발점({self.mission[name]["start"]})과 다릅니다.'
                if st['odom_velocity'] is None or abs(st['odom_velocity'][0]) > 0.005 or abs(st['odom_velocity'][1]) > 0.03:
                    return False, f'{name} 정지 확인 대기 중'
        if not self.started and any(self.external_actions.values()):
            return False, '외부 Nav2 액션이 실행 중입니다.'
        return True, 'Gazebo · Nav2 · Relay 프리플라이트 정상 (도메인 84 · 실물 분리)'

    def tick(self, dt=0.05):
        if self.closed:
            return
        now = self._spin_once()
        self.preflight_ready, self.preflight_reason = self._evaluate_preflight(now)
        active = any(
            r['phase'] not in ('IDLE', 'DONE', 'HALTED', 'CANCELED')
            for r in self.coordinator.robots.values()
        )
        if active:
            if self.relay.poll() is not None:
                self.coordinator.halt('Velocity relay exited')
            if now - self.relay_state.get('received', 0.0) > 0.5 or self.relay_state.get('blocked'):
                self.coordinator.halt('Velocity relay lost / lease expired')
            for name, r in self.coordinator.robots.items():
                if r['pose'] is None or r['phase'] in ('IDLE', 'DONE', 'HALTED', 'CANCELED'):
                    continue
                if self.clearance.distance(r['pose']) < 0.10:
                    self.coordinator.halt('Body clearance below 10cm: ' + name)
                phase = r['phase']
                if phase in ('TO_WAIT', 'CROSSING', 'TO_GOAL'):
                    guard = self.mission[name]['segments'][0]['path'] if phase == 'TO_WAIT' else through_path(self.mission[name])
                    if path_distance(r['pose'], guard) > 0.025:
                        self.coordinator.halt('Tracking deviation exceeds 2.5cm: ' + name)
            poses = [self.coordinator.robots[name]['pose'] for name in ROBOTS]
            if all(p is not None for p in poses) and math.dist(*poses) < 0.22:
                self.coordinator.halt('Inter-robot separation below 22cm')

            old_blocked = self.coordinator.blocked
            self.coordinator.tick(now)
            if self.coordinator.blocked and not old_blocked:
                self._emit('HALTED', None, self.coordinator.blocked, owner=self.coordinator.owner)

            while self.command_index < len(self.coordinator.commands):
                command = self.coordinator.commands[self.command_index]
                self.command_index += 1
                if self.coordinator.blocked and command['kind'] != 'CANCEL':
                    continue
                try:
                    self.workers[command['robot']].submit(command)
                except Exception as exc:
                    self.coordinator.halt('Worker dispatch: ' + str(exc))
                    self._emit('HALTED', command['robot'], self.coordinator.blocked, owner=self.coordinator.owner)

        permits = {
            name: worker.active
            for name, worker in self.workers.items()
            if worker.active is not None
            and worker.goal_handle is not None
            and not worker.cancel_requested
            and self.coordinator.robots[name]['phase'] in ('TO_WAIT', 'CROSSING', 'TO_GOAL', 'SPINNING')
        }
        if self.coordinator.blocked:
            permits = {}
        if now - self.last_lease > 0.05:
            self._heartbeat(permits)
        self._sync_events()

    def start(self, ids, session):
        if self.coordinator.blocked:
            raise self.request_error_cls(409, f'중단된 시뮬레이션 세션입니다: {self.coordinator.blocked}')
        if any(name in self.started for name in ids):
            raise self.request_error_cls(409, '이 세션에서 이미 요청한 로봇입니다.')
        now = self._spin_once()
        ready, reason = self._evaluate_preflight(now)
        if not ready:
            raise self.request_error_cls(409, f'프리플라이트 미준비: {reason}')
        for name in ids:
            st = self.workers[name].status(now)
            if st['pose'] is None or math.dist(st['pose'], self.mission[name]['start']) > 0.05:
                raise self.request_error_cls(409, f'{name} 로봇이 출발점 위치에 있지 않습니다.')
        self.coordinator.start(ids)
        for name in ids:
            self.started.add(name)
            dest = self.mission[name]['destination']
            self._emit('TASK_ACCEPTED', name, f'{dest} 이동 후 회전 (SIM_NAV2)', phase='TO_WAIT', owner=self.coordinator.owner)
        self.tick(0.0)

    def cancel(self, target):
        self.coordinator.cancel(target)
        while self.command_index < len(self.coordinator.commands):
            command = self.coordinator.commands[self.command_index]
            self.command_index += 1
            if command['kind'] == 'CANCEL':
                self.workers[command['robot']].cancel()
        if target == 'all' or self.coordinator.blocked:
            self._heartbeat({})
            if self.coordinator.blocked:
                self._emit('HALTED', None, self.coordinator.blocked, owner=self.coordinator.owner)
        self._sync_events()

    def reset(self):
        now = self._spin_once()
        for name in ROBOTS:
            st = self.workers[name].status(now)
            if st['pose'] is None or math.dist(st['pose'], self.mission[name]['start']) > 0.05:
                raise self.request_error_cls(
                    409,
                    f'{name} 로봇이 출발점({self.mission[name]["start"]})을 벗어났습니다. Gazebo와 Nav2를 재시작해 초기 위치로 되돌리세요.',
                )
        self.coordinator = MissionCoordinator(self.mission, self.polygon, radius=self.radius)
        for name, worker in self.workers.items():
            worker.coordinator = self.coordinator
            worker.active = None
            worker.goal_handle = None
            worker.cancel_requested = False
            if math.isfinite(worker.source):
                self.coordinator.robots[name].update(
                    pose=list(worker.coordinator.robots[name]['pose'] or [0.0, 0.0]),
                )
            worker.source = -math.inf
        self.started.clear()
        self.command_index = 0
        self.coord_event_index = 0
        self.last_phases = {name: 'IDLE' for name in ROBOTS}
        self._spin_once()

    def snapshot(self):
        now = time.monotonic()
        robots_out = []
        for name in ROBOTS:
            r = self.coordinator.robots[name]
            st = self.workers[name].status(now)
            raw_phase = r['phase']
            if raw_phase == 'IDLE':
                task_state = 'IDLE'
            elif raw_phase == 'DONE':
                task_state = 'SUCCEEDED'
            elif raw_phase == 'CANCELED':
                task_state = 'CANCELED'
            elif raw_phase == 'HALTED':
                task_state = 'FAILED'
            else:
                task_state = 'RUNNING'
            stopped = r['stopped_since'] is not None and (now - r['stopped_since']) >= 0.3
            pos = [round(r['pose'][0], 3), round(r['pose'][1], 3)] if r['pose'] is not None else [0.0, 0.0]
            robots_out.append(
                dict(
                    id=name,
                    destination=self.mission[name]['destination'],
                    task_state=task_state,
                    phase=PHASE_MAP.get(raw_phase, raw_phase),
                    position=pos,
                    yaw=round(float(st.get('yaw', 0.0)), 3),
                    pose_age_s=round(float(st['pose_age_s']), 2) if st['pose_age_s'] is not None else 99.9,
                    connection='SIM_NAV2_OK' if (st['observation_fresh'] and st['follow_path'] and st['spin']) else 'SIM_NAV2_WAIT',
                    battery_percent=None,
                    stopped_confirmed=bool(stopped),
                )
            )
        occupants = [
            name
            for name, r in self.coordinator.robots.items()
            if r['pose'] is not None and zone_distance(r['pose'], self.polygon) <= self.radius
        ]
        active = any(r['task_state'] == 'RUNNING' for r in robots_out)
        return dict(
            mode='SIM_NAV2',
            map_review=copy.deepcopy(self.map_review),
            commands_locked=not self.preflight_ready and not active,
            preflight_ready=self.preflight_ready,
            preflight_reason=self.preflight_reason,
            available_modes=['SIM_NAV2'],
            locked_modes=['REAL_NAV2'],
            active=active,
            zone=dict(
                id='central_shared_zone',
                owner=self.coordinator.owner,
                waiting=list(self.coordinator.queue),
                blocked_reason=self.coordinator.blocked,
                occupants=occupants,
            ),
            simulation=dict(robots=robots_out),
            layout=copy.deepcopy(self.layout),
            started=sorted(self.started),
        )

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self._rclpy.ok():
                for worker in self.workers.values():
                    worker.cancel()
                until = time.monotonic() + 1.0
                while time.monotonic() < until:
                    self._spin_once()
                    self._heartbeat({})
        finally:
            self.sender_stop.set()
            if self.sender.is_alive():
                self.sender.join(timeout=1.0)
            if getattr(self, 'relay', None) is not None:
                self.relay.terminate()
                try:
                    self.relay.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.relay.kill()
                    self.relay.wait()
            for worker in self.workers.values():
                self.executor.remove_node(worker)
                worker.destroy_node()
            self.executor.shutdown()
            if self._owns_rclpy and self._rclpy.ok():
                self._rclpy.shutdown()
            self.lock_file.close()

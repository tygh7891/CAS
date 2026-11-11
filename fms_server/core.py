"""Central orchestration only: compose independent job/robot/zone managers.

Exactly one authority issues Nav2 commands. Workers know no shared-zone rules.
No Action preemption, no recovery policy, no simulated hardware worker.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from math import hypot
from threading import RLock
from time import monotonic

from .job_manager import JobManager
from .models import Point, Settings
from .robot_manager import RobotManager
from .zone_manager import ZoneManager


class FMS:
    def __init__(self, settings: Settings, now=monotonic):
        self.s = settings
        self.now = now
        self.lock = RLock()
        self.jobs = JobManager(settings.routes, settings.cooldown)
        self.robots_runtime = RobotManager(settings.routes, settings.ttl)
        self.zone = ZoneManager(settings)
        # Read-only compatibility references for local tests; no duplicated state.
        self.robots = self.robots_runtime.robots
        self.history = self.jobs.history
        self.events: deque[dict] = deque(maxlen=500)
        self._event('SERVER_STARTED', 'In-memory state started; verify physical positions before work')

    @property
    def zone_owner(self) -> str | None:
        return self.zone.owner

    @property
    def zone_queue(self) -> deque[str]:
        return self.zone.waiting

    @property
    def blocked(self) -> str | None:
        return self.zone.blocked

    @property
    def zone_entered(self) -> bool:
        return self.zone.entered

    def _event(self, kind: str, message: str, robot_id: str | None = None) -> None:
        self.events.append({'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                            'type': kind, 'robot_id': robot_id, 'message': message})

    def _all_live_and_outside(self, t: float) -> bool:
        return (self.robots_runtime.all_live(t)
                and all(not self.zone.overlaps(r.pose) for r in self.robots.values()))

    def enqueue(self, rid: str, spins: int) -> dict:
        with self.lock:
            job = self.jobs.enqueue(rid, spins)
            self._event('JOB_QUEUED', f'{job.job_id}: {spins} rotations', rid)
            self._advance(self.now())
            return job.to_dict()

    def _issue(self, rid: str, kind: str, target: Point | None = None) -> None:
        job = self.jobs.active(rid)
        if job is None:
            raise RuntimeError('Cannot issue command without active job')
        cmd = self.robots_runtime.issue(rid, job.job_id, kind, target)
        self._event('COMMAND_ISSUED', f'{kind}: {cmd["command_id"][:8]}', rid)

    def _grant_and_navigate(self, rid: str, target: Point) -> None:
        reservation_id = self.zone.grant(rid)
        self._event('ZONE_GRANTED', f'Exclusive reservation {reservation_id[:8]}', rid)
        job = self.jobs.active(rid)
        self.jobs.set_phase(rid, 'OUTBOUND' if job.leg == 'outbound' else 'RETURN')
        self._issue(rid, 'NAVIGATE', target)

    def _request_leg(self, rid: str, t: float) -> None:
        """Central, atomic direct-vs-wait decision. No action preemption."""
        job = self.jobs.active(rid)
        r = self.robots[rid]
        route = self.s.routes[rid]
        if job.leg == 'outbound':
            target, wait = route.endpoint_b, route.wait_a
        else:
            target, wait = route.endpoint_a, route.wait_b
        if self.blocked or not self.robots_runtime.all_live(t):
            self.jobs.set_phase(rid, 'WAITING_TELEMETRY')
            return
        if self.zone.overlaps(r.pose):
            reason = f'{rid} requested a new leg from inside shared zone'
            self.zone.block(reason)
            self._event('ZONE_BLOCKED', reason, rid)
            return
        if self.zone.available() and self._all_live_and_outside(t):
            self._grant_and_navigate(rid, target)
        else:
            if self.zone.request(rid):
                self._event('ZONE_REQUESTED', 'Queued to enter shared zone', rid)
            self.jobs.set_phase(rid, 'TO_WAIT')
            self._issue(rid, 'NAVIGATE', wait)

    def _start(self, rid: str, t: float) -> None:
        if not self.jobs.can_start(rid, t) or self.blocked:
            return
        r = self.robots[rid]
        if not self.robots_runtime.all_live(t) or self.zone.overlaps(r.pose):
            return
        if not r.pose.near(self.s.routes[rid].endpoint_a, self.s.home_tolerance):
            # Never assume a new round-trip can begin away from its home endpoint.
            return
        job = self.jobs.start(rid)
        self._event('JOB_STARTED', f'{job.job_id} started', rid)
        self._request_leg(rid, t)

    def _exited_on_goal_side(self, rid: str) -> bool:
        """When reversing back into entry side, the reservation must remain held."""
        job = self.jobs.active(rid)
        pose = self.robots[rid].pose
        if job is None or pose is None:
            return False
        route = self.s.routes[rid]
        target = route.endpoint_b if job.leg == 'outbound' else route.endpoint_a
        x1, y1, x2, y2 = self.s.zone
        cx, cy = (x1+x2)/2., (y1+y2)/2.
        return (pose.x-cx)*(target.x-cx) + (pose.y-cy)*(target.y-cy) > 0.

    def _observe_zone(self, rid: str) -> None:
        r = self.robots[rid]
        result = self.zone.observe(rid, r.pose,
                                   exited_on_destination_side=self._exited_on_goal_side(rid))
        if result == 'BLOCKED':
            self._event('ZONE_BLOCKED', self.blocked, rid)
        elif result == 'RELEASED':
            self._event('ZONE_RELEASED',
                        'Footprint fully clear on destination side; Nav2 goal may continue', rid)

    def _grant_queued(self, t: float) -> None:
        if self.blocked or self.zone.owner is not None or not self.zone.waiting:
            return
        if not self._all_live_and_outside(t):
            return
        rid = self.zone.waiting[0]
        job = self.jobs.active(rid)
        if job is None or job.phase != 'WAITING_ZONE' or self.robots[rid].command is not None:
            return  # Do not jump ahead of the FIFO head or preempt its waiting-point Action.
        route = self.s.routes[rid]
        target = route.endpoint_b if job.leg == 'outbound' else route.endpoint_a
        self._grant_and_navigate(rid, target)

    def _finish(self, rid: str, status: str, msg: str, t: float) -> None:
        job = self.jobs.finish(rid, status, msg, t)
        self._event('JOB_' + status, f'{job.job_id}: {msg}', rid)
        # Robot command must already have been consumed before finishing.
        # No automatic clearing of a possible zone reservation on failure.

    def _receive_result(self, rid: str, payload: dict, t: float) -> None:
        job = self.jobs.active(rid)
        if job is None:
            return
        result_row = self.robots_runtime.accept_result(rid, payload)
        if result_row is None:
            return
        cmd, outcome = result_row
        if outcome != 'SUCCEEDED':
            self._finish(rid, 'FAILED', f'{cmd["kind"]} result: {outcome}', t)
            return
        route = self.s.routes[rid]
        r = self.robots[rid]
        if cmd['kind'] == 'NAVIGATE':
            if job.phase == 'TO_WAIT':
                wait = route.wait_a if job.leg == 'outbound' else route.wait_b
                if r.pose is None or not r.pose.near(wait, self.s.home_tolerance):
                    self._finish(rid, 'FAILED', 'Waiting point not confirmed', t)
                else:
                    self.jobs.set_phase(rid, 'WAITING_ZONE')
                    self._event('WAIT_REACHED', 'Waiting point reached', rid)
            elif job.leg == 'outbound':
                if self.zone.owner == rid:
                    self._finish(rid, 'FAILED', 'Crossing was never verified clear', t)
                else:
                    self.jobs.set_phase(rid, 'WORKING')
                    if job.spin_count == 0:
                        self.jobs.set_leg(rid, 'return')
                        self._request_leg(rid, t)
                    else:
                        self._issue(rid, 'SPIN')
            elif job.leg == 'return':
                if self.zone.owner == rid:
                    self._finish(rid, 'FAILED', 'Return crossing not verified clear', t)
                else:
                    self._finish(rid, 'COMPLETED', 'Returned to start after one cycle', t)
        elif cmd['kind'] == 'SPIN':
            if self.jobs.spin_completed(rid):
                self._issue(rid, 'SPIN')
            else:
                self.jobs.set_leg(rid, 'return')
                self._request_leg(rid, t)

    def worker_poll(self, rid: str, data: dict) -> dict:
        if rid not in self.robots:
            raise ValueError('Unknown robot')
        with self.lock:
            t = self.now()
            previous_active = self.jobs.active(rid) is not None
            previously_owned_zone = self.zone.owner == rid
            restarted, fresh_pose = self.robots_runtime.report(rid, data, t)
            if restarted and (previous_active or previously_owned_zone):
                self.jobs.queues[rid].halted = True
                reason = f'{rid} worker restarted during an active operation'
                self.zone.block(reason)
                self._event('ZONE_BLOCKED', reason, rid)
            if fresh_pose:
                self._observe_zone(rid)
            self._receive_result(rid, data, t)
            self._advance(t)
            return {'command': self.robots[rid].command, 'server_blocked': self.blocked}

    def _advance(self, t: float) -> None:
        # Driven by Worker polls / job registration; no background planner thread.
        if self.blocked:
            return
        for rid in self.robots:
            job = self.jobs.active(rid)
            if job and job.phase == 'WAITING_TELEMETRY' and self.robots[rid].command is None:
                self._request_leg(rid, t)
        self._grant_queued(t)
        for rid in self.robots:
            self._start(rid, t)
        self._grant_queued(t)

    def _start_reason(self, rid: str, t: float) -> str:
        q = self.jobs.queues[rid]
        if q.halted:
            return 'Action failure: no recovery is implemented'
        if self.blocked:
            return self.blocked
        if q.active:
            return 'Job running'
        if not q.pending:
            return 'Queue empty'
        if t < q.cooldown_until:
            return f'Cooldown {q.cooldown_until-t:.1f}s'
        if not self.robots_runtime.all_live(t):
            return 'Waiting for fresh location from BOTH robots'
        pose = self.robots[rid].pose
        if self.zone.overlaps(pose):
            return 'Robot position overlaps shared zone'
        if not pose.near(self.s.routes[rid].endpoint_a, self.s.home_tolerance):
            return 'Robot is not at endpoint_a (start pose)'
        return 'Ready to start'

    def status(self) -> dict:
        with self.lock:
            t = self.now()
            def robot_snapshot(rid):
                r = self.robots[rid]
                q = self.jobs.queues[rid]
                job = q.active
                # Robot Action status is not redundantly stored as a Job phase.
                display_phase = (r.command['kind'] if r.command else
                                 job.phase if job else 'FAILED' if q.halted else 'IDLE')
                return {'ready': self.robots_runtime.live(rid, t),
                        'pose': r.pose.as_json() if r.pose else None,
                        'pose_age_s': round(t-r.last_pose_at, 2) if r.pose else None,
                        'phase': display_phase,
                        'leg': job.leg if job else '',
                        'active': job.to_dict() if job else None,
                        'pending': self.jobs.pending(rid),
                        'halted': q.halted,
                        'start_reason': self._start_reason(rid, t),
                        'feedback': r.feedback,
                        'cooldown_remaining_s': round(max(0., q.cooldown_until-t), 1)}
            return {'configured': True,
                    'zone': self.zone.snapshot(),
                    'settings': {'next_job_delay_s': self.s.cooldown,
                                 'telemetry_timeout_s': self.s.ttl,
                                 'active_robots': list(self.robots)},
                    'routes': {rid: {key: getattr(route, key).as_json() for key in
                               ('endpoint_a', 'endpoint_b', 'wait_a', 'wait_b')}
                               for rid, route in self.s.routes.items()},
                    'robots': {rid: robot_snapshot(rid) for rid in self.robots},
                    'events': list(self.events), 'history': list(self.jobs.history)}

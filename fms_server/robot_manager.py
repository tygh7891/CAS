"""Robot runtime observations and exactly-one-active-Nav2-command contract.

No knowledge of jobs, crossing priority, routes, or task scheduling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .models import Point


@dataclass
class RobotState:
    rid: str
    command: dict | None = None
    last_result_command: str | None = None
    pose: Point | None = None
    last_pose_at: float = -1e9
    online_at: float = -1e9
    session_id: str | None = None
    last_seq: int = -1
    ready: bool = False
    feedback: dict = field(default_factory=dict)


class RobotManager:
    def __init__(self, robot_ids, telemetry_timeout_s: float):
        self.robots = {rid: RobotState(rid) for rid in robot_ids}
        self.ttl = telemetry_timeout_s

    def live(self, robot_id: str, now: float) -> bool:
        r = self.robots[robot_id]
        return r.ready and r.pose is not None and now - r.last_pose_at < self.ttl

    def all_live(self, now: float) -> bool:
        return all(self.live(rid, now) for rid in self.robots)

    def report(self, robot_id: str, data: dict[str, Any], now: float) -> tuple[bool, bool]:
        """Update telemetry; return (worker_restart_during_session, fresh_pose_received)."""
        r = self.robots[robot_id]
        session = data.get('session_id')
        seq = data.get('seq')
        if not isinstance(session, str) or len(session) < 6 or type(seq) is not int or seq < 0:
            raise ValueError('Invalid worker session/sequence')
        changed = session != r.session_id
        restarted = changed and r.session_id is not None
        if changed:
            r.session_id = session
            r.last_seq = -1
        if seq <= r.last_seq:
            raise ValueError('Stale worker sequence')
        r.last_seq = seq
        r.online_at = now
        r.ready = data.get('ready') is True
        fresh_pose = False
        raw = data.get('pose')
        age = data.get('pose_age_s')
        if raw is not None and type(age) in (int, float) and 0 <= age < self.ttl:
            p = Point.parse(raw)
            r.pose = p
            r.last_pose_at = now - float(age)
            fresh_pose = True
        r.feedback = data.get('feedback') if isinstance(data.get('feedback'), dict) else {}
        return restarted, fresh_pose

    def issue(self, robot_id: str, job_id: str, kind: str, target: Point | None = None) -> dict:
        r = self.robots[robot_id]
        if r.command is not None:
            raise RuntimeError('An action is already assigned: no preemption')
        command = {'command_id': uuid4().hex, 'kind': kind, 'job_id': job_id,
                   'target': target.as_json() if target else None}
        if kind == 'SPIN':
            command['angle_rad'] = 6.283185307179586
        r.command = command
        return command

    def accept_result(self, robot_id: str, data: dict) -> tuple[dict, str] | None:
        r = self.robots[robot_id]
        if r.command is None:
            return None
        cid = data.get('result_command_id')
        result = data.get('result')
        if (cid != r.command['command_id'] or result not in ('SUCCEEDED', 'FAILED', 'CANCELED')
                or r.last_result_command == cid):
            return None
        r.last_result_command = cid
        command = r.command
        r.command = None
        return command, result

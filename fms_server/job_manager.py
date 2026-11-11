"""One-cycle job queue and lifecycle, independent of robots and zone geometry.

This manager never issues navigation commands and does not inspect robot poses.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from uuid import uuid4

from .models import Job


@dataclass
class JobQueue:
    pending: deque[Job] = field(default_factory=deque)
    active: Job | None = None
    cooldown_until: float = 0.0
    halted: bool = False


class JobManager:
    def __init__(self, robot_ids, cooldown_s: float):
        self.queues = {rid: JobQueue() for rid in robot_ids}
        self.cooldown_s = cooldown_s
        self.history: deque[dict] = deque(maxlen=500)

    def enqueue(self, robot_id: str, spin_count: int) -> Job:
        if robot_id not in self.queues:
            raise ValueError('Unknown robot')
        if type(spin_count) is not int or not 0 <= spin_count <= 100:
            raise ValueError('spin_count must be an integer from 0 to 100')
        job = Job(uuid4().hex[:12], robot_id, spin_count)
        self.queues[robot_id].pending.append(job)
        return job

    def active(self, robot_id: str) -> Job | None:
        return self.queues[robot_id].active

    def can_start(self, robot_id: str, now: float) -> bool:
        q = self.queues[robot_id]
        return not q.halted and q.active is None and now >= q.cooldown_until and bool(q.pending)

    def start(self, robot_id: str) -> Job:
        q = self.queues[robot_id]
        if q.active is not None or not q.pending or q.halted:
            raise RuntimeError('Job cannot start')
        job = q.pending.popleft()
        q.active = job
        job.status = 'ACTIVE'
        job.leg = 'outbound'
        job.phase = 'OUTBOUND'
        return job

    def set_phase(self, robot_id: str, phase: str) -> None:
        job = self.active(robot_id)
        if job is None:
            raise RuntimeError('No active job')
        job.phase = phase

    def set_leg(self, robot_id: str, leg: str) -> None:
        job = self.active(robot_id)
        if job is None or leg not in ('outbound', 'return'):
            raise RuntimeError('Invalid job leg')
        job.leg = leg

    def spin_completed(self, robot_id: str) -> bool:
        job = self.active(robot_id)
        if job is None:
            raise RuntimeError('No active job')
        job.spins_done += 1
        return job.spins_done < job.spin_count

    def finish(self, robot_id: str, status: str, message: str, now: float) -> Job:
        q = self.queues[robot_id]
        job = q.active
        if job is None or status not in ('COMPLETED', 'FAILED'):
            raise RuntimeError('Invalid job finish')
        job.status = status
        job.phase = status
        job.message = message
        self.history.appendleft(job.to_dict())
        q.active = None
        if status == 'COMPLETED':
            q.cooldown_until = now + self.cooldown_s
        else:
            # Recovery policy intentionally deferred, as requested.
            q.halted = True
        return job

    def pending(self, robot_id: str) -> list[dict]:
        return [job.to_dict() for job in self.queues[robot_id].pending]

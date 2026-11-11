"""Single exclusive crossing reservation and FIFO queue.

No ROS commands, job stages, or action results are stored in this class.
A reservation is distinct from observed physical occupancy.
"""
from __future__ import annotations

from collections import deque
from uuid import uuid4

from .models import Point, Settings


class ZoneManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.owner: str | None = None
        self.reservation_id: str | None = None
        self.entered = False
        self.waiting: deque[str] = deque()
        self.blocked: str | None = None

    def overlaps(self, pose: Point) -> bool:
        return self.settings.overlap(pose)

    def available(self) -> bool:
        return self.owner is None and not self.waiting and not self.blocked

    def request(self, robot_id: str) -> bool:
        if self.owner == robot_id or robot_id in self.waiting:
            return False
        self.waiting.append(robot_id)
        return True

    def grant(self, robot_id: str) -> str:
        if self.owner is not None or self.blocked:
            raise RuntimeError('Shared zone is reserved or blocked')
        if self.waiting:
            if self.waiting[0] != robot_id:
                raise RuntimeError('Cannot bypass FIFO reservation queue')
            self.waiting.popleft()
        self.owner = robot_id
        self.reservation_id = uuid4().hex
        self.entered = False
        return self.reservation_id

    def observe(self, robot_id: str, pose: Point, *, exited_on_destination_side: bool) -> str | None:
        """Return 'RELEASED'/'BLOCKED'/None. Requires actual entry before exit release."""
        inside = self.overlaps(pose)
        if inside and self.owner != robot_id:
            if not self.blocked:
                self.blocked = f'Unreserved zone occupancy by {robot_id}. No new goals.'
                return 'BLOCKED'
            return None
        if self.owner == robot_id:
            if inside:
                self.entered = True
            elif self.entered and exited_on_destination_side:
                self.owner = None
                self.reservation_id = None
                self.entered = False
                return 'RELEASED'
        return None

    def block(self, reason: str) -> None:
        if not self.blocked:
            self.blocked = reason

    def snapshot(self) -> dict:
        return {'owner': self.owner, 'entered': self.entered,
                'waiting': list(self.waiting), 'blocked': self.blocked,
                'bounds': list(self.settings.zone), 'clearance_m': self.settings.clearance}

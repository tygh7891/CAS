from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

from fms_geometry import Pose, ZoneBounds


class Phase(StrEnum):
    TO_WAIT = "TO_WAIT"
    APPROACH_ZONE = "APPROACH_ZONE"
    WAITING_ZONE = "WAITING_ZONE"
    CROSSING = "CROSSING"
    TO_GOAL = "TO_GOAL"
    SPINNING = "SPINNING"
    TO_START = "TO_START"
    TURN_AT_START = "TURN_AT_START"


class TaskState(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELING = "CANCELING"
    CANCELED = "CANCELED"


class CommandKind(StrEnum):
    NAVIGATE = "NAVIGATE"
    TRAVERSE = "TRAVERSE"
    SPIN = "SPIN"
    CANCEL = "CANCEL"
    RESET_DEMO = "RESET_DEMO"


class Result(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class Command:
    command_id: str
    task_id: str
    kind: CommandKind
    target: Pose | None = None
    reservation_id: str | None = None
    spin_angle_rad: float | None = None


@dataclass
class Task:
    task_id: str
    state: TaskState = TaskState.RUNNING
    phase: Phase | None = None
    command: Command | None = None
    error_code: str | None = None
    returning: bool = False
    heading_corrected: bool = False

    @property
    def active(self) -> bool:
        return self.state in (TaskState.RUNNING, TaskState.CANCELING)

    def issue(
        self,
        kind: CommandKind,
        target: Pose | None = None,
        reservation_id: str | None = None,
        *,
        spin_angle_rad: float | None = None,
    ) -> None:
        self.command = Command(
            uuid4().hex, self.task_id, kind, target, reservation_id, spin_angle_rad
        )


@dataclass
class Reservation:
    reservation_id: str
    robot_id: str
    entered: bool = False


class Zone:
    def __init__(self, bounds: ZoneBounds, radius_m: float) -> None:
        self.bounds = bounds
        self.radius_m = radius_m
        self.waiting: deque[str] = deque()
        self.reservation: Reservation | None = None

    def overlaps(self, pose: Pose) -> bool:
        return self.bounds.overlaps(pose, self.radius_m)

    def request(self, robot_id: str) -> None:
        if robot_id not in self.waiting and not self.owns(robot_id):
            self.waiting.append(robot_id)

    def owns(self, robot_id: str) -> bool:
        return self.reservation is not None and self.reservation.robot_id == robot_id

    def grant(self) -> Reservation | None:
        if self.reservation is None and self.waiting:
            self.reservation = Reservation(uuid4().hex, self.waiting.popleft())
            return self.reservation
        return None

    def observe(self, reservation_id: str, pose: Pose) -> None:
        reservation = self.reservation
        if reservation and reservation.reservation_id == reservation_id:
            reservation.entered |= self.overlaps(pose)

    def release(
        self, reservation_id: str, pose: Pose, *, canceled: bool = False
    ) -> bool:
        reservation = self.reservation
        if (
            reservation
            and reservation.reservation_id == reservation_id
            and (reservation.entered or canceled)
            and not self.overlaps(pose)
        ):
            self.reservation = None
            return True
        return False

    def cancel_waiting(self, robot_id: str) -> None:
        if robot_id in self.waiting:
            self.waiting.remove(robot_id)

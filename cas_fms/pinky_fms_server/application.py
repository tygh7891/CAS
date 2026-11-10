from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from math import pi, remainder
from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4

from fms_geometry import Pose
from fms_settings import DEMO_TITLES, DemoPreset
from pinky_fms_server.domain import (
    Command,
    CommandKind,
    Phase,
    Result,
    Task,
    TaskState,
    Zone,
)

if TYPE_CHECKING:
    from fms_settings import Scenario

WAYPOINT_TOLERANCE_M = 0.02
RESET_YAW_TOLERANCE_RAD = 0.1
DEMO_DROPOUT_S = 5.0
BATTERY_STALE_S = 15.0


class Conflict(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    session_id: str
    sequence: int
    observed_at_s: float
    pose: Pose
    stopped: bool
    command_id: str | None
    result: Result | None
    ready: bool = True
    detail: str = ""


@dataclass(frozen=True)
class WorkerReply:
    command: Command | None
    location_paused: bool


@dataclass(frozen=True)
class Reading:
    value: float
    at_s: float


@dataclass(frozen=True)
class Telemetry:
    at_s: float
    scan_at_s: float | None
    odom_at_s: float | None
    percent: Reading | None
    voltage: Reading | None


@dataclass(frozen=True)
class FleetEvent:
    elapsed_s: int
    kind: str
    text: str


class FleetService:
    def __init__(
        self,
        scenario: Scenario,
        clock: Callable[[], float] = monotonic,
        *,
        demo_mode: bool = False,
        real_mode: bool = False,
        motion_enabled: bool = True,
    ) -> None:
        self.scenario = scenario
        self.clock = clock
        self.zone = Zone(scenario.zone, scenario.robot_radius_m)
        self.observations: dict[str, Observation] = {}
        self.telemetry: dict[str, Telemetry] = {}
        self.tasks: dict[str, Task] = {}
        self.run_id: str | None = None
        self.run_requests: dict[str, str] = {}
        self.cancel_requests: dict[str, str] = {}
        self.demo_mode = demo_mode
        self.real_mode = real_mode
        self.motion_enabled = motion_enabled
        self._reset_commands: dict[str, Command] = {}
        self._reset_failed = False
        self._paused_robot_id: str | None = None
        self._resume_after_s: dict[str, float] = {}
        self._preset: DemoPreset | None = None
        self._preset_triggered = False
        self._demo_resume_at_s: float | None = None
        self._events: deque[FleetEvent] = deque(maxlen=32)
        self._started_at_s = clock()
        self._lock = Lock()

    def start(self, request_id: str, preset: DemoPreset | None = None) -> str:
        with self._lock:
            if request_id in self.run_requests:
                return self.run_requests[request_id]
            if not self.motion_enabled:
                raise Conflict("읽기 전용 모드에서는 주행할 수 없습니다.")
            if preset is not None and not self.demo_mode:
                raise Conflict("시연 시나리오는 가상 모드에서만 실행할 수 있습니다.")
            now = self.clock()
            if not self._can_start(now):
                raise Conflict(
                    "두 로봇의 주행 준비, 출발 위치와 정지 상태를 확인하세요."
                )
            repeat_demo = self.demo_mode and (
                self.run_id is not None or preset is not None
            )
            run_id = uuid4().hex
            self.run_requests[request_id] = run_id
            self.run_id = run_id
            self._reset_failed = False
            self._preset = preset
            self._preset_triggered = False
            self._demo_resume_at_s = None
            self._started_at_s = now
            self._events.clear()
            if preset is not None:
                self._event("scenario", f"{DEMO_TITLES[preset]} 시작")
            if repeat_demo:
                self._event("resetting", "두 로봇을 출발점으로 초기화 중")
                self._reset_commands = {
                    robot_id: Command(
                        uuid4().hex,
                        f"{run_id}:{robot_id}",
                        CommandKind.RESET_DEMO,
                        route.start,
                    )
                    for robot_id, route in self.scenario.routes.items()
                }
            else:
                self._start_tasks()
            return run_id

    def _start_tasks(self) -> None:
        self._event("depart", "두 로봇이 출발점에서 대기점으로 이동")
        self.tasks = {}
        for robot_id, route in self.scenario.routes.items():
            task = Task(f"{self.run_id}:{robot_id}", phase=Phase.TO_WAIT)
            task.issue(CommandKind.NAVIGATE, route.wait)
            self.tasks[robot_id] = task

    def _finish_demo_reset(self, now: float) -> None:
        failed = False
        for robot_id, command in self._reset_commands.items():
            observation = self.observations[robot_id]
            if (
                not self._fresh(robot_id, now)
                or observation.command_id != command.command_id
                or not observation.stopped
            ):
                return
            if observation.result == Result.FAILED:
                failed = True
                continue
            if (
                observation.result != Result.SUCCEEDED
                or command.target is None
                or observation.pose.distance_to(command.target) > WAYPOINT_TOLERANCE_M
                or abs(
                    remainder(observation.pose.yaw_rad - command.target.yaw_rad, 2 * pi)
                )
                > RESET_YAW_TOLERANCE_RAD
            ):
                return
        self._reset_commands.clear()
        self._reset_failed = failed
        if failed:
            self._event("failed", "출발점 초기화 실패")
        else:
            self.zone = Zone(self.scenario.zone, self.scenario.robot_radius_m)
            self._start_tasks()

    def _event(self, kind: str, text: str) -> None:
        self._events.append(
            FleetEvent(int(self.clock() - self._started_at_s), kind, text)
        )

    def _name(self, robot_id: str) -> str:
        return f"{self.scenario.routes[robot_id].start_label}번 로봇"

    def cancel(self, run_id: str, request_id: str) -> None:
        with self._lock:
            previous = self.cancel_requests.get(request_id)
            if previous == run_id:
                return
            if previous or self.run_id != run_id or not self._active():
                raise Conflict("취소할 수 있는 현재 작업이 없습니다.")
            self.cancel_requests[request_id] = run_id
            self._cancel_active()

    def _cancel_active(self) -> None:
        self._event("cancel_requested", "작업 취소 요청 접수 · 정지 확인 중")
        for robot_id, task in self.tasks.items():
            if task.state != TaskState.RUNNING:
                continue
            self.zone.cancel_waiting(robot_id)
            reservation = self.zone.reservation
            reservation_id = (
                reservation.reservation_id
                if reservation and self.zone.owns(robot_id)
                else None
            )
            task.state = TaskState.CANCELING
            task.issue(CommandKind.CANCEL, reservation_id=reservation_id)

    def set_location_paused(self, robot_id: str, paused: bool) -> None:
        with self._lock:
            if not self.demo_mode:
                raise Conflict(
                    "위치 보고 중단·복구는 가상 시연에서만 사용할 수 있습니다."
                )
            if robot_id not in self.scenario.routes:
                raise ValueError("Unknown robot")
            now = self.clock()
            if paused:
                if self._paused_robot_id == robot_id:
                    return
                if (
                    self._paused_robot_id
                    or self._location_pause_target(now) != robot_id
                ):
                    raise Conflict(
                        "교차로 안의 로봇이 통과 중일 때 위치를 중단할 수 있습니다."
                    )
                self._pause_location(robot_id)
            elif self._paused_robot_id == robot_id:
                self._resume_location(robot_id, now)
            elif self._paused_robot_id is not None:
                raise Conflict("위치 보고가 중단된 로봇을 확인하세요.")

    def _pause_location(self, robot_id: str) -> None:
        self._paused_robot_id = robot_id
        self._event(
            "location_paused", f"{self._name(robot_id)} 위치 보고 중단 · 다음 진입 보류"
        )

    def _resume_location(self, robot_id: str, now: float) -> None:
        self._paused_robot_id = None
        self._demo_resume_at_s = None
        self._resume_after_s[robot_id] = now
        self._event(
            "location_resume_requested", f"{self._name(robot_id)} 위치 보고 재개 요청"
        )

    def _trigger_preset(self, now: float) -> None:
        if self._preset is not None and any(
            task.state == TaskState.FAILED for task in self.tasks.values()
        ):
            if any(task.state == TaskState.RUNNING for task in self.tasks.values()):
                self._cancel_active()
            return
        if self._preset_triggered or self._preset not in (
            DemoPreset.DROPOUT,
            DemoPreset.CANCEL,
        ):
            return
        robot_id = self._location_pause_target(now)
        if robot_id is None or not self.zone.bounds.overlaps(
            self.observations[robot_id].pose, 0
        ):
            return
        self._preset_triggered = True
        if self._preset == DemoPreset.DROPOUT:
            self._pause_location(robot_id)
            self._demo_resume_at_s = now + DEMO_DROPOUT_S
        else:
            self._cancel_active()

    def poll(
        self,
        robot_id: str,
        session_id: str,
        observation: Observation | None,
        telemetry: Telemetry | None = None,
        *,
        telemetry_only: bool = False,
    ) -> WorkerReply:
        with self._lock:
            if robot_id not in self.scenario.routes:
                raise KeyError(robot_id)
            now = self.clock()
            last = self.observations.get(robot_id)
            if last and last.session_id != session_id:
                raise Conflict("Worker가 교체되었습니다. 가상 시연을 다시 시작하세요.")
            if telemetry is not None:
                if telemetry.at_s > now:
                    raise ValueError("Telemetry time cannot be in the future")
                previous = self.telemetry.get(robot_id)
                if previous is None or telemetry.at_s > previous.at_s:
                    self.telemetry[robot_id] = telemetry
            if telemetry_only:
                return WorkerReply(None, self._paused_robot_id == robot_id)
            if (
                self._paused_robot_id is not None
                and self._demo_resume_at_s is not None
                and now >= self._demo_resume_at_s
            ):
                self._resume_location(self._paused_robot_id, now)
            if observation is None and (not self.demo_mode or last is None):
                raise ValueError("Expected a position observation")
            if observation is None or self._paused_robot_id == robot_id:
                return self._worker_reply(robot_id)
            if observation.observed_at_s > now:
                raise ValueError("Observation time cannot be in the future")
            resume_after_s = self._resume_after_s.get(robot_id)
            if (
                resume_after_s is not None
                and observation.observed_at_s < resume_after_s
            ):
                return self._worker_reply(robot_id)
            if last and (
                observation.sequence <= last.sequence
                or observation.observed_at_s <= last.observed_at_s
            ):
                return self._worker_reply(robot_id)
            if self._resume_after_s.pop(robot_id, None) is not None:
                self._event(
                    "location_resumed", f"{self._name(robot_id)}의 새 위치 수신"
                )
            self.observations[robot_id] = observation
            if self._reset_commands:
                self._finish_demo_reset(now)
            else:
                task = self.tasks.get(robot_id)
                if task and self._fresh(robot_id, now):
                    self._advance(robot_id, task, observation)
                self._trigger_preset(now)
                self._grant_next(now)
            return self._worker_reply(robot_id)

    def _worker_reply(self, robot_id: str) -> WorkerReply:
        task = self.tasks.get(robot_id)
        command = self._reset_commands.get(robot_id) or (task.command if task else None)
        return WorkerReply(command, self._paused_robot_id == robot_id)

    def _location_pause_target(self, now: float) -> str | None:
        reservation = self.zone.reservation
        if (
            not self.demo_mode
            or self._paused_robot_id
            or not reservation
            or not reservation.entered
        ):
            return None
        robot_id = reservation.robot_id
        if (
            self.tasks[robot_id].state == TaskState.RUNNING
            and self._fresh(robot_id, now)
            and self.zone.overlaps(self.observations[robot_id].pose)
        ):
            return robot_id
        return None

    def _advance(self, robot_id: str, task: Task, observation: Observation) -> None:
        command = task.command
        if command is None or observation.command_id != command.command_id:
            return
        if task.state == TaskState.CANCELING:
            if observation.result != Result.CANCELED or not observation.stopped:
                return
            if command.reservation_id and self.zone.release(
                command.reservation_id, observation.pose, canceled=True
            ):
                self._event(
                    "zone_released", f"{self._name(robot_id)} 정지 · 교차로 밖 확인"
                )
            task.state = TaskState.CANCELED
            task.command = None
            self._event("canceled", f"{self._name(robot_id)}의 취소와 정지 확인")
            return
        if task.phase == Phase.CROSSING and command.reservation_id:
            self.zone.observe(command.reservation_id, observation.pose)
        if observation.result == Result.FAILED:
            task.state = TaskState.FAILED
            task.error_code = "WORKER_FAILED"
            task.command = None
            self._event("failed", f"{self._name(robot_id)} 작업 실패")
            return
        if observation.result != Result.SUCCEEDED or not observation.stopped:
            return
        if command.target and observation.pose.distance_to(command.target) > (
            WAYPOINT_TOLERANCE_M
        ):
            if self.real_mode:
                task.state = TaskState.FAILED
                task.error_code = "WAYPOINT_NOT_REACHED"
                task.command = None
                self._event("failed", f"{self._name(robot_id)}의 목표 위치 불일치")
            return
        match task.phase:
            case Phase.TO_WAIT:
                task.phase = Phase.WAITING_ZONE
                task.command = None
                self.zone.request(robot_id)
                self._event("waiting", f"{self._name(robot_id)} 대기점 도착")
            case Phase.CROSSING:
                if command.reservation_id and self.zone.release(
                    command.reservation_id, observation.pose
                ):
                    task.phase = Phase.TO_GOAL
                    task.issue(
                        CommandKind.NAVIGATE, self.scenario.routes[robot_id].goal
                    )
                    self._event(
                        "zone_released", f"{self._name(robot_id)}의 교차로 이탈 확인"
                    )
            case Phase.TO_GOAL:
                task.phase = Phase.SPINNING
                task.issue(CommandKind.SPIN)
                self._event(
                    "spinning", f"{self._name(robot_id)} 목적지 도착 · 회전 시작"
                )
            case Phase.SPINNING:
                task.state = TaskState.SUCCEEDED
                task.phase = None
                task.command = None
                self._event(
                    "completed", f"{self._name(robot_id)} 회전 완료 · 정지 확인"
                )

    def _grant_next(self, now: float) -> None:
        if self.zone.reservation or not self.zone.waiting:
            return
        if (
            not self._preset_triggered
            and self._preset in (DemoPreset.DROPOUT, DemoPreset.CANCEL)
            and len(self.zone.waiting) < len(self.scenario.routes)
        ):
            return
        if any(
            not self._fresh(robot_id, now)
            or not self.observations[robot_id].ready
            or self.zone.overlaps(self.observations[robot_id].pose)
            for robot_id in self.scenario.routes
        ):
            return
        robot_id = self.zone.waiting[0]
        route = self.scenario.routes[robot_id]
        observation = self.observations[robot_id]
        if (
            not observation.stopped
            or observation.pose.distance_to(route.wait) > WAYPOINT_TOLERANCE_M
        ):
            return
        reservation = self.zone.grant()
        if reservation:
            task = self.tasks[robot_id]
            task.phase = Phase.CROSSING
            task.issue(CommandKind.NAVIGATE, route.exit, reservation.reservation_id)
            self._event("zone_granted", f"{self._name(robot_id)}에 교차로 진입권 부여")

    def _fresh(self, robot_id: str, now: float) -> bool:
        observation = self.observations.get(robot_id)
        return (
            observation is not None
            and self._paused_robot_id != robot_id
            and robot_id not in self._resume_after_s
            and now - observation.observed_at_s < self.scenario.stale_after_s
        )

    def _active(self) -> bool:
        return any(task.active for task in self.tasks.values())

    def _can_start(self, now: float) -> bool:
        if not self.motion_enabled or self._active() or self._reset_commands:
            return False
        if not all(
            self._fresh(robot_id, now)
            and self.observations[robot_id].ready
            and self.observations[robot_id].stopped
            for robot_id in self.scenario.routes
        ):
            return False
        if self.demo_mode and self.run_id is not None:
            return True
        return self.zone.reservation is None and all(
            self.observations[robot_id].pose.distance_to(route.start)
            <= WAYPOINT_TOLERANCE_M
            and (
                not self.real_mode
                or abs(
                    remainder(
                        self.observations[robot_id].pose.yaw_rad - route.start.yaw_rad,
                        2 * pi,
                    )
                )
                <= 0.2
            )
            for robot_id, route in self.scenario.routes.items()
        )

    def status(self) -> dict[str, object]:
        with self._lock:
            now = self.clock()
            reservation = self.zone.reservation
            owner = reservation.robot_id if reservation else None
            stale = any(
                not self._fresh(robot_id, now) or not self.observations[robot_id].ready
                for robot_id in self.scenario.routes
            )
            blocked = bool(owner and (stale or not self.tasks[owner].active)) or bool(
                self.zone.waiting and stale
            )
            hold_reason = ""
            if blocked:
                if self._paused_robot_id:
                    hold_reason = f"{self._name(self._paused_robot_id)} 위치 보고 중단"
                elif stale:
                    hold_reason = "새 위치 또는 주행 준비 상태 확인 중"
                else:
                    hold_reason = "교차로를 비웠는지 확인되지 않았습니다"
            return {
                "map_id": self.scenario.map_id,
                "run_id": self.run_id,
                "resetting": bool(self._reset_commands),
                "reset_failed": self._reset_failed,
                "real_mode": self.real_mode,
                "motion_enabled": self.motion_enabled,
                "can_start": self._can_start(now),
                "demo_preset": self._preset,
                "events": [asdict(event) for event in self._events],
                "can_cancel": any(
                    task.state == TaskState.RUNNING for task in self.tasks.values()
                ),
                "zone_owner": owner,
                "zone_blocked": blocked,
                "zone_hold_reason": hold_reason,
                "zone_waiting": list(self.zone.waiting),
                "location_pause_target": self._location_pause_target(now),
                "paused_robot_id": self._paused_robot_id,
                "robots": [
                    self._robot_status(robot_id, now)
                    for robot_id in self.scenario.routes
                ],
            }

    def _robot_status(self, robot_id: str, now: float) -> dict[str, object]:
        task = self.tasks.get(robot_id)
        observation = self.observations.get(robot_id)
        telemetry = self.telemetry.get(robot_id)
        percent = telemetry.percent if telemetry else None
        voltage = telemetry.voltage if telemetry else None
        age_s = now - (percent or voltage).at_s if (percent or voltage) else None
        return {
            "robot_id": robot_id,
            "task_id": task.task_id if task else None,
            "task_state": task.state if task else TaskState.IDLE,
            "phase": task.phase if task else None,
            "connected": self._fresh(robot_id, now),
            "ready": bool(
                observation and observation.ready and self._fresh(robot_id, now)
            ),
            "detail": observation.detail if observation else "",
            "location_paused": self._paused_robot_id == robot_id,
            "pose": asdict(observation.pose) if observation else None,
            "pose_age_s": round(now - observation.observed_at_s, 2)
            if observation
            else None,
            "battery_percent": percent.value if percent else None,
            "battery_voltage": voltage.value if voltage else None,
            "battery_age_s": round(age_s, 1) if age_s is not None else None,
            "battery_stale": age_s is not None and age_s >= BATTERY_STALE_S,
            "scan_received": bool(
                telemetry
                and telemetry.scan_at_s is not None
                and now - telemetry.scan_at_s < self.scenario.stale_after_s
            ),
            "odom_received": bool(
                telemetry
                and telemetry.odom_at_s is not None
                and now - telemetry.odom_at_s < self.scenario.stale_after_s
            ),
            "error_code": task.error_code if task else None,
        }

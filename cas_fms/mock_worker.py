import argparse
import json
from dataclasses import asdict, dataclass
from math import tau
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fms_geometry import Pose
from fms_settings import DEFAULT_SCENARIO, load_scenario

POLL_PERIOD_S = 0.1
NAVIGATION_SPEED_M_S = 0.30
SPIN_DURATION_S = 1.6


@dataclass
class Motion:
    start: Pose
    target: Pose
    duration_s: float
    elapsed_s: float = 0.0

    def advance(self, dt_s: float) -> Pose:
        self.elapsed_s = min(self.duration_s, self.elapsed_s + dt_s)
        ratio = self.elapsed_s / self.duration_s
        return Pose(
            self.start.x_m + (self.target.x_m - self.start.x_m) * ratio,
            self.start.y_m + (self.target.y_m - self.start.y_m) * ratio,
            self.start.yaw_rad + (self.target.yaw_rad - self.start.yaw_rad) * ratio,
        )


class MockRobot:
    def __init__(self, start: Pose) -> None:
        self.pose = start
        self.session_id = uuid4().hex
        self.sequence = 0
        self.command_id: str | None = None
        self.result: str | None = None
        self.motion: Motion | None = None
        self.location_paused = False

    def receive_poll(self, reply: dict[str, Any]) -> None:
        self.location_paused = reply.get("location_paused", False)
        self.receive(reply["command"])

    def receive(self, command: dict[str, Any] | None) -> None:
        if command is None or command["command_id"] == self.command_id:
            return
        self.command_id = command["command_id"]
        match command["kind"]:
            case "NAVIGATE":
                target = Pose(**command["target"])
                duration = max(
                    0.1, self.pose.distance_to(target) / NAVIGATION_SPEED_M_S
                )
                self.motion = Motion(self.pose, target, duration)
                self.result = "RUNNING"
            case "SPIN":
                target = Pose(self.pose.x_m, self.pose.y_m, self.pose.yaw_rad + tau)
                self.motion = Motion(self.pose, target, SPIN_DURATION_S)
                self.result = "RUNNING"
            case "CANCEL":
                self.motion = None
                self.result = "CANCELED"
            case "RESET_DEMO":
                self.pose = Pose(**command["target"])
                self.motion = None
                self.result = "SUCCEEDED"
            case _:
                self.motion = None
                self.result = "FAILED"

    def advance(self, dt_s: float) -> None:
        motion = self.motion
        if motion:
            self.pose = motion.advance(dt_s)
            if motion.elapsed_s == motion.duration_s:
                self.motion = None
                self.result = "SUCCEEDED"

    def observe(self, now: float) -> dict[str, object]:
        if self.location_paused:
            return {"session_id": self.session_id, "location_paused": True}
        self.sequence += 1
        return {
            "session_id": self.session_id,
            "sequence": self.sequence,
            "observed_at_s": now,
            "pose": asdict(self.pose),
            "stopped": self.motion is None,
            "command_id": self.command_id,
            "result": self.result,
        }


def run_worker(server_url: str, robot_id: str, scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    robot = MockRobot(scenario.routes[robot_id].start)
    url = f"{server_url}/api/workers/{robot_id}/poll"
    last_tick = monotonic()
    while True:
        now = monotonic()
        robot.advance(min(now - last_tick, POLL_PERIOD_S * 1.5))
        last_tick = now
        request = Request(
            url,
            data=json.dumps(robot.observe(now)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=0.8) as response:
                robot.receive_poll(json.load(response))
        except HTTPError:
            raise
        except (URLError, TimeoutError):
            pass
        sleep(POLL_PERIOD_S)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CAS A1 mock worker")
    parser.add_argument("--server", required=True)
    parser.add_argument("--robot", choices=("robot_1", "robot_2"), required=True)
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    args = parser.parse_args()
    run_worker(args.server.rstrip("/"), args.robot, args.scenario)


if __name__ == "__main__":
    main()

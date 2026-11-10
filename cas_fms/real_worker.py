import argparse
import logging
from math import isclose, isfinite
from pathlib import Path
from time import monotonic

import rclpy
import yaml
from builtin_interfaces.msg import Time as TimeMessage
from geometry_msgs.msg import Twist
from nav2_msgs.msg import CostmapFilterInfo
from nav_msgs.msg import OccupancyGrid, Odometry
from PyQt5.QtGui import QImage
from rcl_interfaces.msg import ParameterType
from rclpy.parameter_client import AsyncParameterClient
from rclpy.qos import DurabilityPolicy, QoSProfile
from rclpy.time import Time
from sensor_msgs.msg import LaserScan

from fms_settings import Scenario, load_scenario, require_verified_layout
from ros_nav_worker import LEASE_S, RosNavWorker, run_worker

RAW_VELOCITY = "/fms/cmd_vel_raw"
GUARDED_VELOCITY = "/cmd_vel_nav"
MOTOR_VELOCITY = "/cmd_vel"
MAX_LINEAR_M_S = 0.10
MAX_ANGULAR_RAD_S = 0.60
MAX_STOP_TIMEOUT_S = 0.5
FILTER_INFO = "/keepout_filter_info"
MASK = "/keepout_filter_mask"


class ExpectedGrid:
    def __init__(self, path: Path) -> None:
        metadata = yaml.safe_load(path.read_text())
        image = QImage(str(path.with_name(metadata["image"])))
        if image.isNull() or metadata.get("mode", "trinary") != "trinary":
            raise ValueError(f"Expected a trinary occupancy map: {path}")
        self.width, self.height = image.width(), image.height()
        self.resolution = metadata["resolution"]
        self.origin_x, self.origin_y, _ = metadata["origin"]
        self.cells = []
        for y in reversed(range(self.height)):
            for x in range(self.width):
                occupancy = image.pixelColor(x, y).red() / 255
                if not metadata["negate"]:
                    occupancy = 1 - occupancy
                if occupancy >= metadata["occupied_thresh"]:
                    self.cells.append(100)
                elif occupancy <= metadata["free_thresh"]:
                    self.cells.append(0)
                else:
                    self.cells.append(-1)

    def matches(self, message: OccupancyGrid) -> bool:
        info = message.info
        position, rotation = info.origin.position, info.origin.orientation
        return (
            message.header.frame_id == "map"
            and (info.width, info.height) == (self.width, self.height)
            and isclose(info.resolution, self.resolution, abs_tol=1e-6)
            and isclose(position.x, self.origin_x, abs_tol=1e-6)
            and isclose(position.y, self.origin_y, abs_tol=1e-6)
            and max(abs(rotation.x), abs(rotation.y), abs(rotation.z)) < 1e-6
            and isclose(abs(rotation.w), 1.0, abs_tol=1e-6)
            and list(message.data) == self.cells
        )


class RealWorker(RosNavWorker):
    def __init__(
        self,
        robot_id: str,
        scenario: Scenario,
        scenario_path: Path,
        url: str,
        *,
        enable_motion: bool,
    ) -> None:
        super().__init__(
            robot_id,
            scenario.zone,
            scenario.robot_radius_m,
            url,
            use_sim_time=False,
            velocity_input=RAW_VELOCITY,
            velocity_output=GUARDED_VELOCITY if enable_motion else None,
        )
        self.enable_motion = enable_motion
        self.stale_after_s = min(scenario.stale_after_s, LEASE_S)
        metadata = yaml.safe_load(scenario_path.read_text())
        self.expected_map = ExpectedGrid(scenario_path.parent / metadata["map"])
        self.expected_mask = ExpectedGrid(scenario_path.parent / metadata["keepout"])
        self.map_ready = False
        self.filter_ready = False
        self.graph_ready = False
        self.smoother_checked_at = 0.0
        self.next_smoother_check = 0.0
        self.smoother_check = None
        self.smoother_params = AsyncParameterClient(self, "/velocity_smoother")
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, "map", self._map, latched)
        self.create_subscription(CostmapFilterInfo, FILTER_INFO, self._filter, latched)

    def _can_report(self) -> bool:
        return self.odom_at > 0

    def _map(self, message: OccupancyGrid) -> None:
        self.map_ready = self.expected_map.matches(message)

    def _keepout(self, message: OccupancyGrid) -> None:
        self.keepout_ready = self.expected_mask.matches(message)

    def _filter(self, info: CostmapFilterInfo) -> None:
        self.filter_ready = (
            info.type == 0
            and info.filter_mask_topic == MASK
            and info.base == 0.0
            and info.multiplier == 1.0
        )

    def _message_age_s(self, stamp: TimeMessage) -> float:
        return (self.get_clock().now() - Time.from_msg(stamp)).nanoseconds / 1e9

    def _pose_observed_at(self, stamp: TimeMessage, now: float) -> float | None:
        age = self._message_age_s(stamp)
        return now - max(0.0, age) if -0.1 <= age < self.stale_after_s else None

    def _projection_horizon_s(self) -> float:
        return 0.65

    def _scan(self, message: LaserScan) -> None:
        age = self._message_age_s(message.header.stamp)
        if len(message.ranges) and -0.1 <= age < self.stale_after_s:
            self.scan_at = monotonic() - max(0.0, age)

    def _odometry(self, message: Odometry) -> None:
        age = self._message_age_s(message.header.stamp)
        twist = message.twist.twist
        if -0.1 <= age < self.stale_after_s and all(
            isfinite(value)
            for value in (twist.linear.x, twist.linear.y, twist.angular.z)
        ):
            super()._odometry(message)
            self.odom_at -= max(0.0, age)

    def _publisher_names(self, topic: str) -> list[str]:
        return sorted(p.node_name for p in self.get_publishers_info_by_topic(topic))

    def _subscriber_names(self, topic: str) -> set[str]:
        return {s.node_name for s in self.get_subscriptions_info_by_topic(topic)}

    def _check_graph(self, now: float) -> None:
        self.graph_ready = (
            self._publisher_names(MOTOR_VELOCITY) == ["velocity_smoother"]
            and "pinky_bringup" in self._subscriber_names(MOTOR_VELOCITY)
            and set(self._publisher_names(RAW_VELOCITY))
            == {"behavior_server", "controller_server"}
            and self._publisher_names(GUARDED_VELOCITY)
            == ([self.get_name()] if self.enable_motion else [])
            and "velocity_smoother" in self._subscriber_names(GUARDED_VELOCITY)
            and {"global_costmap", "local_costmap"}
            <= self._subscriber_names(FILTER_INFO)
            and {"global_costmap", "local_costmap"} <= self._subscriber_names(MASK)
            and len(self._publisher_names("/map"))
            == len(self._publisher_names(MASK))
            == 1
        )
        if self.smoother_check is not None and self.smoother_check.done():
            response = self.smoother_check.result()
            self.smoother_check = None
            if response is not None and len(response.values) == 3:
                timeout, stamped, simulated = response.values
                if (
                    0 < timeout.double_value <= MAX_STOP_TIMEOUT_S
                    and stamped.type == simulated.type == ParameterType.PARAMETER_BOOL
                    and not (stamped.bool_value or simulated.bool_value)
                ):
                    self.smoother_checked_at = now
                else:
                    self.smoother_checked_at = 0.0
        if (
            now >= self.next_smoother_check
            and self.smoother_params.services_are_ready()
        ):
            if self.smoother_check is not None:
                self.smoother_check.cancel()
            self.smoother_check = self.smoother_params.get_parameters(
                ["velocity_timeout", "enable_stamped_cmd_vel", "use_sim_time"]
            )
            self.next_smoother_check = now + 0.5

    def _detail(self, now: float) -> str:
        if now - min(self.scan_at, self.odom_at, self.pose_at) >= self.stale_after_s:
            return "라이다·위치·오도메트리 수신을 확인하세요."
        if not (self.map_ready and self.keepout_ready and self.filter_ready):
            return "공유 맵과 진입 제한 마스크를 확인하세요."
        if not self._nav_ready():
            return "Nav2 주행·회전 연결을 확인하세요."
        if not self.graph_ready or now - self.smoother_checked_at >= 1.2:
            return "속도 명령 경로와 로봇의 자동 정지 설정을 확인하세요."
        return ""

    def _status_fields(self, now: float) -> dict[str, object]:
        detail = self._detail(now)
        return {"ready": not detail, "detail": detail}

    def _motion_ready(self, now: float) -> bool:
        return self.enable_motion and not self._detail(now)

    def _velocity(self, twist: Twist) -> None:
        command = Twist()
        if self.goal_handle is not None and all(
            isfinite(value) for value in (twist.linear.x, twist.angular.z)
        ):
            command.linear.x = max(-MAX_LINEAR_M_S, min(MAX_LINEAR_M_S, twist.linear.x))
            command.angular.z = max(
                -MAX_ANGULAR_RAD_S, min(MAX_ANGULAR_RAD_S, twist.angular.z)
            )
        super()._velocity(command)

    def tick(self, now: float) -> None:
        self._check_graph(now)
        if self.result == "RUNNING" and (
            not self._motion_ready(now) or now - self.lease_at >= LEASE_S
        ):
            self.abort_requested = True
        super().tick(now)


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect an FMS Worker to Pinky Nav2")
    parser.add_argument("--server", required=True)
    parser.add_argument("--robot", choices=("robot_1", "robot_2"), required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--enable-motion", action="store_true")
    args = parser.parse_args()
    if args.enable_motion:
        try:
            require_verified_layout(args.scenario)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    logging.basicConfig(level=logging.INFO)
    rclpy.init()
    url = f"{args.server}/api/workers/{args.robot}/poll"
    worker = RealWorker(
        args.robot,
        load_scenario(args.scenario),
        args.scenario,
        url,
        enable_motion=args.enable_motion,
    )
    run_worker(worker)


if __name__ == "__main__":
    main()

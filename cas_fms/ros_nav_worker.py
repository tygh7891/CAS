import json
import logging
from dataclasses import asdict
from math import atan2, cos, hypot, isfinite, sin, tau
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import rclpy
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Time as TimeMessage
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose, Spin
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32
from tf2_ros import Buffer, TransformException, TransformListener

from fms_geometry import CROSSING_STOP_MARGIN_M, Pose, ZoneBounds

REPORT_INTERVAL_S = 0.10
LEASE_S = 0.60
LOG = logging.getLogger(__name__)


class RosNavWorker(Node):
    def __init__(
        self,
        robot_id: str,
        zone: ZoneBounds,
        radius_m: float,
        url: str,
        *,
        use_sim_time: bool,
        velocity_input: str = "cmd_vel",
        velocity_output: str | None = "fms_cmd_vel",
    ) -> None:
        super().__init__(
            "cas_fms_worker",
            parameter_overrides=[Parameter("use_sim_time", value=use_sim_time)],
        )
        self.robot_id = robot_id
        self.zone = zone
        self.radius_m = radius_m
        self.url = url
        self.session_id = uuid4().hex
        self.sequence = 0
        self.odom_at = 0.0
        self.scan_at = 0.0
        self.battery: dict[str, dict[str, float]] = {}
        self.pose_at = 0.0
        self.lease_at = 0.0
        self.stopped = False
        self.pose: Pose | None = None
        self.keepout_ready = False
        self.last_stamp: tuple[int, int] | None = None
        self.paused = False
        self.command: dict[str, Any] | None = None
        self.result: str | None = None
        self.pending_goal = None
        self.goal_handle = None
        self.pending_result = None
        self.cancel_requested = False
        self.cancel_sent = False
        self.abort_requested = False
        self.tf = Buffer(node=self)
        self.listener = TransformListener(self.tf, self)
        self.navigate = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.spin = ActionClient(self, Spin, "spin")
        self.velocity = None
        if velocity_output is not None:
            self.velocity = self.create_publisher(Twist, velocity_output, 1)
            self.create_subscription(Twist, velocity_input, self._velocity, 1)
        self.create_subscription(Odometry, "odom", self._odometry, 10)
        self.create_subscription(LaserScan, "scan", self._scan, qos_profile_sensor_data)
        self.create_subscription(
            Float32, "battery/percent", self._battery_percent, qos_profile_sensor_data
        )
        self.create_subscription(
            Float32, "battery/voltage", self._battery_voltage, qos_profile_sensor_data
        )
        self.create_subscription(
            OccupancyGrid,
            "keepout_filter_mask",
            self._keepout,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )

    def _keepout(self, mask: OccupancyGrid) -> None:
        self.keepout_ready = mask.header.frame_id == "map" and bool(mask.data)

    def _scan(self, msg: LaserScan) -> None:
        if len(msg.ranges):
            self.scan_at = monotonic()

    def _battery_percent(self, msg: Float32) -> None:
        if 0 <= msg.data <= 100:
            self.battery["percent"] = {"value": msg.data, "at_s": monotonic()}

    def _battery_voltage(self, msg: Float32) -> None:
        if 0 <= msg.data <= 100:
            self.battery["voltage"] = {"value": msg.data, "at_s": monotonic()}

    def _odometry(self, msg: Odometry) -> None:
        self.odom_at = monotonic()
        twist = msg.twist.twist
        self.stopped = hypot(twist.linear.x, twist.linear.y) < 0.015 and (
            abs(twist.angular.z) < 0.05
        )

    def _velocity(self, twist: Twist) -> None:
        now = monotonic()
        if self.velocity is None:
            return
        if (
            self.result != "RUNNING"
            or self.cancel_requested
            or self.abort_requested
            or self.pose is None
            or now - min(self.pose_at, self.odom_at, self.lease_at) > LEASE_S
            or not self._motion_ready(now)
        ):
            self.velocity.publish(Twist())
            return
        if not self.command or not self.command.get("reservation_id"):
            travel = twist.linear.x * self._projection_horizon_s()
            x, y, yaw = self.pose.x_m, self.pose.y_m, self.pose.yaw_rad
            projected = Pose(x + travel * cos(yaw), y + travel * sin(yaw), yaw)
            radius = self.radius_m
            if self.command and self.command["kind"] == "TRAVERSE":
                radius += CROSSING_STOP_MARGIN_M
            if self.zone.overlaps(self.pose, radius) or self.zone.overlaps(
                projected, radius
            ):
                self.velocity.publish(Twist())
                return
        self.velocity.publish(twist)

    def _projection_horizon_s(self) -> float:
        return 0.25

    def _motion_ready(self, now: float) -> bool:
        return True

    def _status_fields(self, now: float) -> dict[str, object]:
        return {}

    def _can_report(self) -> bool:
        return self.keepout_ready and self._nav_ready()

    def _nav_ready(self) -> bool:
        return self.navigate.server_is_ready() and self.spin.server_is_ready()

    def _update_pose(self, now: float) -> None:
        try:
            transform = self.tf.lookup_transform("map", "base_footprint", Time())
        except TransformException:
            return
        stamp = transform.header.stamp
        stamp_key = (stamp.sec, stamp.nanosec)
        observed_at = self._pose_observed_at(stamp, now)
        if stamp_key == self.last_stamp or observed_at is None:
            return
        xyz = transform.transform.translation
        q = transform.transform.rotation
        if not all(isfinite(value) for value in (xyz.x, xyz.y, q.x, q.y, q.z, q.w)):
            return
        self.last_stamp = stamp_key
        yaw = atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y**2 + q.z**2))
        self.pose = Pose(xyz.x, xyz.y, yaw)
        self.pose_at = observed_at

    def _pose_observed_at(self, stamp: TimeMessage, now: float) -> float | None:
        return now

    def tick(self, now: float) -> None:
        self._update_pose(now)
        self._update_action()
        self._update_reset(now)
        if self.velocity is not None and (
            self.result != "RUNNING"
            or self.cancel_requested
            or self.abort_requested
            or now - min(self.lease_at, self.pose_at, self.odom_at) > LEASE_S
            or not self._motion_ready(now)
        ):
            self.velocity.publish(Twist())
        telemetry_only = self.pose is None or not self._can_report()
        payload: dict[str, object] = {
            "session_id": self.session_id,
            "telemetry": {
                "at_s": now,
                "scan_at_s": self.scan_at or None,
                "odom_at_s": self.odom_at or None,
                **self.battery,
            },
        }
        if telemetry_only:
            payload["telemetry_only"] = True
        elif self.paused:
            payload["location_paused"] = True
        else:
            self.sequence += 1
            payload.update(
                sequence=self.sequence,
                observed_at_s=min(self.pose_at, self.odom_at),
                pose=asdict(self.pose),
                stopped=self.stopped,
                command_id=self.command["command_id"] if self.command else None,
                reservation_id=self.command.get("reservation_id")
                if self.command
                else None,
                result=self.result,
            )
            payload.update(self._status_fields(now))
        request = Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=0.30) as response:
                reply = json.load(response)
        except HTTPError:
            raise
        except (URLError, TimeoutError):
            return
        if telemetry_only:
            return
        self.lease_at = monotonic()
        self.paused = reply["location_paused"]
        command = reply["command"]
        if self.velocity is not None and command is not None:
            if (
                self.command is None
                or command["command_id"] != self.command["command_id"]
            ):
                self._receive(command)
            elif command["kind"] == "TRAVERSE":
                self.command = command

    def _receive(self, command: dict[str, Any]) -> None:
        self.command = command
        self.result = "RUNNING"
        kind = command["kind"]
        LOG.info("%s received %s", self.robot_id, kind)
        if kind == "CANCEL":
            self.cancel_requested = True
            self._update_action()
            return
        self.cancel_requested = self.cancel_sent = False
        self.abort_requested = False
        if not self._motion_ready(monotonic()):
            self.result = "FAILED"
            return
        if kind in ("NAVIGATE", "TRAVERSE"):
            target = Pose(**command["target"])
            goal = NavigateToPose.Goal()
            goal.pose = self._goal_pose(target)
            self.pending_goal = self.navigate.send_goal_async(goal)
        elif kind == "SPIN":
            goal = Spin.Goal()
            angle = command.get("spin_angle_rad")
            goal.target_yaw = tau if angle is None else angle
            goal.time_allowance.sec = 30
            self.pending_goal = self.spin.send_goal_async(goal)
        elif kind == "RESET_DEMO":
            self._reset(Pose(**command["target"]))
        else:
            self.result = "FAILED"

    def _update_action(self) -> None:
        if self.pending_goal is not None and self.pending_goal.done():
            self.goal_handle = self.pending_goal.result()
            self.pending_goal = None
            if self.goal_handle.accepted:
                self.pending_result = self.goal_handle.get_result_async()
            else:
                self.goal_handle = None
                self.result = "FAILED"
        if (
            (self.cancel_requested or self.abort_requested)
            and self.goal_handle is not None
            and not self.cancel_sent
        ):
            self.goal_handle.cancel_goal_async()
            self.cancel_sent = True
        if self.pending_result is not None and self.pending_result.done():
            response = self.pending_result.result()
            self.pending_result = self.goal_handle = None
            self.result = (
                "SUCCEEDED"
                if response.status == GoalStatus.STATUS_SUCCEEDED
                else "FAILED"
            )
            LOG.info("%s action %s: %s", self.robot_id, self.result, response.result)
        if (
            (self.cancel_requested or self.abort_requested)
            and self.pending_goal is None
            and self.goal_handle is None
        ):
            self.result = "CANCELED" if self.cancel_requested else "FAILED"

    def _goal_pose(self, pose: Pose) -> PoseStamped:
        stamped = PoseStamped()
        stamped.header.frame_id = "map"
        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.pose.position.x = pose.x_m
        stamped.pose.position.y = pose.y_m
        stamped.pose.orientation.z = sin(pose.yaw_rad / 2)
        stamped.pose.orientation.w = cos(pose.yaw_rad / 2)
        return stamped

    def _reset(self, pose: Pose) -> None:
        self.result = "FAILED"

    def _update_reset(self, now: float) -> None:
        pass


def run_worker(worker: RosNavWorker) -> None:
    next_tick = 0.0
    try:
        while rclpy.ok():
            rclpy.spin_once(worker, timeout_sec=0.02)
            now = monotonic()
            if now >= next_tick:
                worker.tick(now)
                next_tick = now + REPORT_INTERVAL_S
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        worker.destroy_node()
        rclpy.try_shutdown()

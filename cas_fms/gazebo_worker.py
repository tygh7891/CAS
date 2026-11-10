import argparse
import logging
import subprocess
from math import remainder, tau
from pathlib import Path
from time import monotonic

import rclpy
from geometry_msgs.msg import Twist
from nav2_msgs.srv import SetInitialPose

from fms_geometry import Pose, ZoneBounds
from fms_settings import load_scenario
from gazebo_scene import WORLD_NAME, gazebo_pose_request
from ros_nav_worker import RosNavWorker, run_worker

LOG = logging.getLogger(__name__)


class GazeboWorker(RosNavWorker):
    def __init__(
        self, robot_id: str, zone: ZoneBounds, radius_m: float, url: str
    ) -> None:
        super().__init__(robot_id, zone, radius_m, url, use_sim_time=True)
        self.initial_pose = self.create_client(SetInitialPose, "set_initial_pose")
        self.reset_service = None
        self.reset_at = 0.0
        self.reset_target: Pose | None = None

    def _reset(self, pose: Pose) -> None:
        self.velocity.publish(Twist())
        if not self.initial_pose.service_is_ready():
            self.result = "FAILED"
            return
        try:
            reply = subprocess.run(
                [
                    "gz",
                    "service",
                    "-s",
                    f"/world/{WORLD_NAME}/set_pose",
                    "--reqtype",
                    "gz.msgs.Pose",
                    "--reptype",
                    "gz.msgs.Boolean",
                    "--timeout",
                    "1500",
                    "--req",
                    gazebo_pose_request(self.robot_id, pose),
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            if "data: true" not in reply.stdout:
                raise RuntimeError(reply.stdout.strip())
        except (subprocess.SubprocessError, RuntimeError) as error:
            LOG.error("%s reset failed: %s", self.robot_id, error)
            self.result = "FAILED"
            return
        stamped = self._goal_pose(pose)
        request = SetInitialPose.Request()
        request.pose.header = stamped.header
        request.pose.pose.pose = stamped.pose
        request.pose.pose.covariance[0] = request.pose.pose.covariance[7] = 0.000025
        request.pose.pose.covariance[35] = 0.0004
        self.reset_service = self.initial_pose.call_async(request)
        self.reset_target = pose
        self.reset_at = monotonic()

    def _update_reset(self, now: float) -> None:
        if self.reset_target is None:
            return
        if now - self.reset_at > 8.0:
            self.result = "FAILED"
            self.reset_target = self.reset_service = None
        elif (
            self.reset_service.done()
            and min(self.pose_at, self.odom_at) > self.reset_at + 0.4
            and self.stopped
            and self.pose is not None
            and self.pose.distance_to(self.reset_target) <= 0.02
            and abs(remainder(self.pose.yaw_rad - self.reset_target.yaw_rad, tau))
            <= 0.1
        ):
            self.result = "SUCCEEDED"
            self.reset_target = self.reset_service = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simulated Pinky Nav2 Worker")
    parser.add_argument("--server", required=True)
    parser.add_argument("--robot", choices=("robot_1", "robot_2"), required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    rclpy.init()
    url = f"{args.server}/api/workers/{args.robot}/poll"
    scenario = load_scenario(args.scenario)
    worker = GazeboWorker(args.robot, scenario.zone, scenario.robot_radius_m, url)
    run_worker(worker)


if __name__ == "__main__":
    main()

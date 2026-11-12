"""One PC process per physical ROS domain; JSON-line IPC, no commands at startup."""
import json
import math
import queue
import sys
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from nav2_msgs.action import NavigateToPose, Spin
from nav_msgs.msg import Odometry, OccupancyGrid
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy, ReliabilityPolicy
from tf2_ros import Buffer, TransformListener


class Worker(Node):
    def __init__(self):
        super().__init__('cas_physical_worker')
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.spin = ActionClient(self, Spin, '/spin')
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.pending_map = None
        self.create_subscription(OccupancyGrid, '/map', self.map_received,
                                 QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                            reliability=ReliabilityPolicy.RELIABLE))
        self.inbox = queue.Queue()
        self.current = None
        self.goal_handle = None
        self.cancel_requested = False
        self.result = None
        self.velocity = None
        self.odom_received = 0.0
        self.create_subscription(Odometry, '/odom', self.odom, qos_profile_sensor_data)
        self.create_timer(0.05, self.poll)
        self.create_timer(0.2, self.report)
        threading.Thread(target=self.read_input, daemon=True).start()

    def map_received(self, msg):
        o = msg.info.origin
        q = o.orientation
        self.pending_map = dict(width=msg.info.width, height=msg.info.height,
                                resolution=msg.info.resolution, frame=msg.header.frame_id,
                                origin=[o.position.x, o.position.y,
                                        math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))],
                                data=list(msg.data))

    def read_input(self):
        for line in sys.stdin:
            try:
                self.inbox.put(json.loads(line))
            except ValueError:
                pass
        self.inbox.put({'kind': 'CANCEL'})

    def odom(self, msg):
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if abs(self.get_clock().now().nanoseconds * 1e-9 - stamp) > 2:
            return
        self.velocity = [msg.twist.twist.linear.x, msg.twist.twist.angular.z]
        self.odom_received = time.monotonic()

    def poll(self):
        while not self.inbox.empty():
            command = self.inbox.get()
            if command['kind'] == 'CANCEL':
                self.cancel_requested = True
                if self.goal_handle:
                    self.goal_handle.cancel_goal_async()
            elif self.current is None:
                self.submit(command)

    def submit(self, command):
        kind = command['kind']
        self.current = command['id']
        self.result = None
        self.cancel_requested = False
        if kind == 'NAVIGATE':
            client = self.nav
            goal = NavigateToPose.Goal()
            goal.pose.header.frame_id = 'map'
            goal.pose.header.stamp = self.get_clock().now().to_msg()
            x, y, yaw = command['target']
            goal.pose.pose.position.x = float(x)
            goal.pose.pose.position.y = float(y)
            goal.pose.pose.orientation.z = math.sin(yaw / 2)
            goal.pose.pose.orientation.w = math.cos(yaw / 2)
        else:
            client = self.spin
            goal = Spin.Goal()
            goal.target_yaw = float(command.get('angle', 2 * math.pi))
            goal.time_allowance = Duration(seconds=120).to_msg()
        if not client.server_is_ready():
            self.finish(False, 'Action server unavailable')
            return
        client.send_goal_async(goal).add_done_callback(self.accepted)

    def accepted(self, future):
        try:
            self.goal_handle = future.result()
            if not self.goal_handle.accepted:
                self.finish(False, 'Goal rejected')
                return
            if self.cancel_requested:
                self.goal_handle.cancel_goal_async()
            self.goal_handle.get_result_async().add_done_callback(self.completed)
        except Exception as exc:
            self.finish(False, str(exc))

    def completed(self, future):
        try:
            response = future.result()
            code = getattr(response.result, 'error_code', 0)
            self.finish(response.status == 4 and code == 0,
                        f'status={response.status}, error={code}')
        except Exception as exc:
            self.finish(False, str(exc))

    def finish(self, ok, detail):
        self.result = {'id': self.current, 'ok': ok, 'detail': detail}
        self.current = None
        self.goal_handle = None

    def report(self):
        pose = None
        pose_age = None
        try:
            t = self.buffer.lookup_transform('map', 'base_footprint', Time())
            stamp = t.header.stamp.sec + t.header.stamp.nanosec * 1e-9
            pose_age = self.get_clock().now().nanoseconds * 1e-9 - stamp
            if -2 <= pose_age <= 2:
                q = t.transform.rotation
                yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
                pose = [t.transform.translation.x, t.transform.translation.y, yaw]
        except Exception:
            pass
        velocity = self.velocity if time.monotonic() - self.odom_received < 1 else None
        report = {'pose': pose, 'pose_age': pose_age, 'velocity': velocity,
                          'ready': self.nav.server_is_ready() and self.spin.server_is_ready(),
                          'busy': self.current, 'result': self.result}
        if self.pending_map is not None:
            report['live_map'] = self.pending_map
            self.pending_map = None
        print(json.dumps(report), flush=True)


def main():
    rclpy.init()
    node = Worker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.goal_handle:
            node.goal_handle.cancel_goal_async()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.05)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

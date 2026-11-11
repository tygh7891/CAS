"""ROS2 worker: exactly one Nav2 goal at a time; no action cancellation/preemption.

Start one process per domain. All shared-zone logic lives in fms_server.
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose, Spin
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener


class Worker(Node):
    def __init__(self):
        super().__init__('pinky_fms_worker')
        self.declare_parameter('robot_id', 'robot_1')
        self.declare_parameter('server_url', 'http://127.0.0.1:8765')
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('robot_frame', 'base_footprint')
        self.robot_id = self.get_parameter('robot_id').value
        self.server_url = self.get_parameter('server_url').value.rstrip('/')
        self.map_frame = self.get_parameter('map_frame').value
        self.robot_frame = self.get_parameter('robot_frame').value
        self.session_id = uuid4().hex
        self.seq = 0
        self.tf_buffer = Buffer(node=self)
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.spin_client = ActionClient(self, Spin, 'spin')
        self.command_id = None
        self.action_status = 'NONE'
        self.result = None
        self.goal_handle = None
        self.feedback = {}
        self.last_pose = None
        self.pose_age = None
        self.http = ThreadPoolExecutor(max_workers=1, thread_name_prefix='fms_http')
        self.request_future = None
        self.timer = self.create_timer(0.1, self._tick)
        self.get_logger().info(f'Worker {self.robot_id}; FMS={self.server_url}; domain from ROS_DOMAIN_ID')

    @staticmethod
    def _post(url, data):
        body = json.dumps(data).encode('utf-8')
        req = Request(url, body, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(req, timeout=0.65) as response:
            return json.loads(response.read().decode('utf-8'))

    def _sample_tf(self):
        try:
            tf = self.tf_buffer.lookup_transform(self.map_frame, self.robot_frame, Time())
            translation, q = tf.transform.translation, tf.transform.rotation
            yaw = math.atan2(2 * (q.w*q.z + q.x*q.y), 1-2*(q.y*q.y + q.z*q.z))
            pose = {'x': float(translation.x), 'y': float(translation.y), 'yaw': yaw}
            age = (self.get_clock().now().nanoseconds -
                   (tf.header.stamp.sec * 1_000_000_000 + tf.header.stamp.nanosec)) / 1e9
            if not all(math.isfinite(v) for v in pose.values()) or not -0.1 <= age < 30:
                self.last_pose, self.pose_age = None, None
                return
            self.last_pose, self.pose_age = pose, max(0., age)
        except TransformException:
            self.last_pose, self.pose_age = None, None

    def _tick(self):
        self._sample_tf()
        if self.request_future is not None:
            if not self.request_future.done():
                return
            try:
                answer = self.request_future.result()
                self._apply_server_command(answer.get('command'))
                if answer.get('server_blocked'):
                    self.get_logger().warn('FMS BLOCKED: ' + str(answer['server_blocked']))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                self.get_logger().warn(f'FMS poll failed: {exc}')
            finally:
                self.request_future = None
        self.seq += 1
        payload = {'session_id': self.session_id, 'seq': self.seq,
                   'ready': self.nav_client.server_is_ready() and self.spin_client.server_is_ready()
                            and self.last_pose is not None and self.pose_age is not None,
                   'pose': self.last_pose, 'pose_age_s': self.pose_age,
                   'feedback': dict(self.feedback),
                   'result_command_id': self.command_id if self.result else None,
                   'result': self.result}
        url = f'{self.server_url}/api/workers/{self.robot_id}/poll'
        self.request_future = self.http.submit(self._post, url, payload)

    def _apply_server_command(self, command):
        if command is None:
            return
        cid = command['command_id']
        if cid == self.command_id:
            return
        if self.action_status == 'RUNNING':
            # Central FMS must never replace an active Nav2 goal.
            self.get_logger().error('Rejected unexpected new goal while previous action RUNNING')
            return
        kind = command['kind']
        self.command_id = cid
        self.action_status = 'RUNNING'
        self.result = None
        self.goal_handle = None
        self.feedback = {'kind': kind}
        if kind == 'NAVIGATE':
            p = command['target']
            goal = NavigateToPose.Goal()
            pose = PoseStamped()
            pose.header.frame_id = self.map_frame
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x, pose.pose.position.y = float(p['x']), float(p['y'])
            pose.pose.orientation.z = math.sin(float(p['yaw']) / 2.)
            pose.pose.orientation.w = math.cos(float(p['yaw']) / 2.)
            goal.pose = pose
            client = self.nav_client
        elif kind == 'SPIN':
            goal = Spin.Goal()
            goal.target_yaw = float(command['angle_rad'])
            # Duration default 0: no extra FMS-imposed Spin timeout.
            # A time-limit policy is intentionally left for later discussion.
            client = self.spin_client
        else:
            self._done('FAILED', f'Unknown command kind: {kind}')
            return
        if not client.server_is_ready():
            self._done('FAILED', f'Nav2 Action Server unavailable: {kind}')
            return
        self.get_logger().info(f'Action {kind} (goal {cid[:8]})')
        future = client.send_goal_async(goal, feedback_callback=self._on_feedback)
        future.add_done_callback(self._on_accepted)

    def _on_feedback(self, msg):
        fb = msg.feedback
        # Nav2 feedback is published to central FMS; GUI reads server snapshot.
        if hasattr(fb, 'distance_remaining'):
            self.feedback = {'kind': 'NAVIGATE', 'distance_remaining_m': round(float(fb.distance_remaining), 3),
                             'navigation_time_s': fb.navigation_time.sec + fb.navigation_time.nanosec / 1e9}
        elif hasattr(fb, 'angular_distance_traveled'):
            self.feedback = {'kind': 'SPIN', 'angular_distance_traveled_rad': round(float(fb.angular_distance_traveled), 3)}

    def _on_accepted(self, future):
        try:
            handle = future.result()
            if not handle or not handle.accepted:
                self._done('FAILED', 'Nav2 Action goal was rejected')
                return
            self.goal_handle = handle
            handle.get_result_async().add_done_callback(self._on_result)
        except Exception as exc:
            self._done('FAILED', f'Goal acceptance error: {exc}')

    def _on_result(self, future):
        try:
            wrapper = future.result()
            status = wrapper.status
            outcome = 'SUCCEEDED' if status == GoalStatus.STATUS_SUCCEEDED else 'FAILED'
            detail = getattr(wrapper.result, 'error_msg', '') or str(getattr(wrapper.result, 'error_code', ''))
            self._done(outcome, detail)
        except Exception as exc:
            self._done('FAILED', f'Action result error: {exc}')

    def _done(self, result, detail):
        self.result = result
        self.action_status = result
        self.feedback['result_detail'] = str(detail)
        self.get_logger().info(f'Action result {result}: {detail}')

    def close(self):
        self.timer.cancel()
        self.http.shutdown(wait=False, cancel_futures=True)


def main(args=None):
    rclpy.init(args=args)
    node = Worker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

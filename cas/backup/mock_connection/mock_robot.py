#!/usr/bin/env python3
"""Mock action server. No motor commands, no real Nav2 action names."""
import argparse
import threading
import time
from common import configure, PREFIX

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--robot', choices=['robot_1', 'robot_2'], required=True)
args = parser.parse_args()
domain = configure(args.robot)

import rclpy
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from nav2_msgs.action import NavigateToPose, Spin
from std_srvs.srv import Trigger

class MockRobot(Node):
    def __init__(self):
        super().__init__('cas_mock_robot')
        self.lock = threading.Lock()
        self.busy = False
        self.group = ReentrantCallbackGroup()
        self.identity = self.create_service(Trigger, PREFIX + '/identity', self.identify,
                                            callback_group=self.group)
        self.actions = []
        for cls, name in [(NavigateToPose, 'navigate_to_pose'), (Spin, 'spin')]:
            self.actions.append(ActionServer(self, cls, PREFIX + '/' + name,
                execute_callback=lambda handle, cls=cls: self.execute(handle, cls),
                goal_callback=self.accept, cancel_callback=self.cancel,
                callback_group=self.group))
        self.log('READY: PC localhost only; no /cmd_vel publisher')

    def log(self, msg):
        print(f'[{args.robot} domain={domain}] {msg}', flush=True)

    def identify(self, request, response):
        response.success = True
        response.message = f'CAS_MOCK:{args.robot}:{domain}'
        return response

    def accept(self, request):
        with self.lock:
            if self.busy:
                self.log('REJECTED: another mock task is running')
                return GoalResponse.REJECT
            self.busy = True
        return GoalResponse.ACCEPT

    def cancel(self, handle):
        self.log('CANCEL requested')
        return CancelResponse.ACCEPT

    def execute(self, handle, cls):
        result = cls.Result()
        kind = 'NAVIGATE' if cls is NavigateToPose else 'SPIN'
        label = handle.request.behavior_tree if cls is NavigateToPose else str(handle.request.target_yaw)
        self.log(f'ACCEPTED {kind}: {label}')
        start = time.monotonic()
        try:
            for step in range(20):
                if handle.is_cancel_requested:
                    handle.canceled()
                    self.log(f'CANCELED {kind}')
                    return result
                if not rclpy.ok():
                    return result
                feedback = cls.Feedback()
                if cls is NavigateToPose:
                    feedback.current_pose.header.frame_id = 'cas_mock/' + args.robot + '/map'
                    feedback.current_pose.header.stamp = self.get_clock().now().to_msg()
                    feedback.current_pose.pose.orientation.w = 1.0
                    feedback.current_pose.pose.position.x = handle.request.pose.pose.position.x * step / 20
                    feedback.distance_remaining = (20-step) / 20.0
                else:
                    feedback.angular_distance_traveled = handle.request.target_yaw * step / 20
                handle.publish_feedback(feedback)
                time.sleep(0.1)
            if handle.is_cancel_requested:
                handle.canceled()
                self.log(f'CANCELED {kind}')
            else:
                if cls is Spin:
                    elapsed = time.monotonic()-start
                    result.total_elapsed_time.sec = int(elapsed)
                    result.total_elapsed_time.nanosec = int((elapsed-int(elapsed))*1e9)
                handle.succeed()
                self.log(f'SUCCEEDED {kind}')
            return result
        finally:
            with self.lock:
                self.busy = False

rclpy.init()
node = MockRobot()
executor = MultiThreadedExecutor(num_threads=4)
executor.add_node(node)
try:
    executor.spin()
except KeyboardInterrupt:
    pass
finally:
    executor.shutdown(timeout_sec=3)
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

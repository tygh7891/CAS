#!/usr/bin/env python3
"""Test domain identity, Navigate/Spin success, and cancellation against mocks."""
import argparse
import math
import subprocess
import sys
import time
from pathlib import Path
from common import configure, PREFIX

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--robot', choices=['robot_1', 'robot_2'])
args = parser.parse_args()
if args.robot is None:
    processes = []
    try:
        for name in ['robot_1', 'robot_2']:
            processes.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--robot', name]))
        codes = [p.wait() for p in processes]
        print('ALL PASSED' if all(c == 0 for c in codes) else 'FAILED: inspect robot logs', flush=True)
        sys.exit(0 if all(c == 0 for c in codes) else 1)
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=5)

domain = configure(args.robot)
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose, Spin
from std_srvs.srv import Trigger

rclpy.init()
node = Node('cas_mock_test_client')
clients = []
feedback_count = 0
wrong_feedback = False

def log(msg):
    print(f'[TEST {args.robot} domain={domain}] {msg}', flush=True)

def await_future(future, timeout=8):
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
    if not future.done():
        raise RuntimeError('Response timeout')
    result = future.result()
    if result is None:
        raise RuntimeError('Empty response')
    return result

def feedback(msg):
    global feedback_count, wrong_feedback
    feedback_count += 1
    if hasattr(msg.feedback, 'current_pose'):
        if msg.feedback.current_pose.header.frame_id != 'cas_mock/' + args.robot + '/map':
            wrong_feedback = True

try:
    ident = node.create_client(Trigger, PREFIX + '/identity')
    if not ident.wait_for_service(timeout_sec=8):
        raise RuntimeError('Mock server absent; start the corresponding mock terminal')
    response = await_future(ident.call_async(Trigger.Request()))
    expected = f'CAS_MOCK:{args.robot}:{domain}'
    if not response.success or response.message != expected:
        raise RuntimeError(f'Wrong domain/server identity: {response.message}')
    log('PASS identity = ' + response.message)
    nav = ActionClient(node, NavigateToPose, PREFIX + '/navigate_to_pose')
    spin = ActionClient(node, Spin, PREFIX + '/spin')
    clients.extend([nav, spin])
    for client in clients:
        if not client.wait_for_server(timeout_sec=8):
            raise RuntimeError('Mock Action server missing')
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = 'cas_mock/' + args.robot + '/map'
    goal.pose.pose.orientation.w = 1.0
    goal.pose.pose.position.x = 1.0
    goal.behavior_tree = 'TEST_' + args.robot + '_MOVE'
    handle = await_future(nav.send_goal_async(goal, feedback_callback=feedback))
    if not handle.accepted:
        raise RuntimeError('Move rejected')
    result = await_future(handle.get_result_async())
    if result.status != GoalStatus.STATUS_SUCCEEDED or result.result.error_code != 0 or wrong_feedback:
        raise RuntimeError('Move result or robot identity mismatch')
    log('PASS movement success (simulation only)')
    # Allow server callback cleanup before the next task.
    time.sleep(0.15)
    rotation = Spin.Goal()
    rotation.target_yaw = math.tau
    rotation.time_allowance.sec = 10
    handle = await_future(spin.send_goal_async(rotation, feedback_callback=feedback))
    if not handle.accepted:
        raise RuntimeError('Spin rejected')
    result = await_future(handle.get_result_async())
    if result.status != GoalStatus.STATUS_SUCCEEDED or result.result.error_code != 0:
        raise RuntimeError('Spin failed')
    log('PASS spin success (simulation only)')
    time.sleep(0.15)
    goal.behavior_tree = 'TEST_' + args.robot + '_CANCEL'
    handle = await_future(nav.send_goal_async(goal, feedback_callback=feedback))
    if not handle.accepted:
        raise RuntimeError('Cancel test goal rejected')
    end = time.monotonic()+0.4
    while time.monotonic()<end:
        rclpy.spin_once(node, timeout_sec=0.05)
    canceled = await_future(handle.cancel_goal_async())
    if not canceled.goals_canceling:
        raise RuntimeError('Cancellation rejected')
    result = await_future(handle.get_result_async())
    if result.status != GoalStatus.STATUS_CANCELED:
        raise RuntimeError('Cancellation did not reach CANCELED')
    if feedback_count == 0 or wrong_feedback:
        raise RuntimeError('No feedback or wrong robot feedback')
    log(f'PASS cancellation; feedback={feedback_count}; no wrong-robot feedback')
except Exception as exc:
    log('FAIL ' + str(exc))
    sys.exit(1)
finally:
    for client in clients:
        client.destroy()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

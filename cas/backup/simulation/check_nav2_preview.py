"""Read-only B3 lifecycle, TF, Action and output isolation check. Never sends goals."""
import json
import time
import rclpy
from rclpy.node import Node
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose, FollowPath, Spin
from rclpy.action import ActionClient
from tf2_ros import Buffer, TransformListener
from rclpy.time import Time


def main():
    rclpy.init()
    nodes = []
    checks = {}
    clients = []
    buffers = []
    actions = []
    for robot in ['robot_1', 'robot_2']:
        node = Node('cas_preview_check', namespace=robot, cli_args=['--ros-args', '-r', f'/tf:=/{robot}/tf', '-r', f'/tf_static:=/{robot}/tf_static'])
        nodes.append(node)
        buffer = Buffer()
        listener = TransformListener(buffer, node)
        buffers.append((robot, buffer, listener))
        for name in ['map_server', 'keepout_mask_server', 'costmap_filter_info_server', 'amcl',
                     'planner_server', 'controller_server', 'behavior_server', 'bt_navigator',
                     'velocity_smoother', 'smoother_server']:
            client = node.create_client(GetState, f'/{robot}/{name}/get_state')
            clients.append((f'{robot}/{name}', client, None))
        for kind, action_type in [('navigate_to_pose', NavigateToPose), ('follow_path', FollowPath), ('spin', Spin)]:
            actions.append((f'{robot}/{kind}', ActionClient(node, action_type, f'/{robot}/{kind}')))
    # tf2's default subscriptions are remapped per node via wrapper CLI arguments.
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        for node in nodes:
            rclpy.spin_once(node, timeout_sec=0.02)
        for index, (name, client, future) in enumerate(clients):
            if future is None and client.service_is_ready():
                clients[index] = (name, client, client.call_async(GetState.Request()))
            elif future is not None and future.done():
                checks[name] = future.result().current_state.id == 3
                clients[index] = (name, client, None)
    for name, _, _ in clients:
        checks.setdefault(name, False)
    for name, client in actions:
        checks[name] = client.server_is_ready()
    poses = {}
    for robot, buffer, _ in buffers:
        try:
            tf = buffer.lookup_transform('map', f'{robot}/base_footprint', Time())
            poses[robot] = dict(x=tf.transform.translation.x, y=tf.transform.translation.y)
            checks[f'{robot}/map_tf'] = True
        except Exception as error:
            checks[f'{robot}/map_tf'] = False
            poses[robot] = str(error)
        checks[f'{robot}/motor_output_disconnected'] = nodes[0].count_publishers(f'/{robot}/cmd_vel') == 0
    print(json.dumps(dict(domain=84, checks=checks, map_poses=poses), indent=2))
    passed = all(checks.values())
    print('B3 PREVIEW CHECK ' + ('PASSED' if passed else 'FAILED') + ' — NO GOALS SENT')
    for node in nodes:
        node.destroy_node()
    rclpy.shutdown()
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

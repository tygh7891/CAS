"""Request ComputePathToPose only. No Navigate, Spin or velocity publisher."""
import json
import math
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose
from action_msgs.msg import GoalStatus
from prepare_map import arrays
from path_geometry import audit


def wait(node, future, seconds=30):
    rclpy.spin_until_future_complete(node, future, timeout_sec=seconds)
    if not future.done():
        raise TimeoutError('Planner response timeout; no motion goal was sent')
    return future.result()


def main():
    folder = Path.home() / 'CAS_sim_ws/generated_map'
    report = json.loads((folder/'map_profile_report.json').read_text())
    scenario = json.loads((folder/'scenario.candidates.json').read_text())
    spec, _, allowed = arrays(report['source_map'], report['source_allowed_mask'])
    if scenario['map_sha256'] != spec.digest:
        raise ValueError('Candidate map mismatch')
    rclpy.init()
    node = Node('cas_path_audit', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
    results = {}
    paths = {}
    try:
        for robot, start, target in [('robot_1', '1', 'B'), ('robot_2', '2', 'A')]:
            try:
                if any(node.count_publishers(f'/{name}/cmd_vel') for name in ['robot_1', 'robot_2']):
                    raise RuntimeError('Motor output is not isolated; stop this check')
                client = ActionClient(node, ComputePathToPose, f'/{robot}/compute_path_to_pose')
                if not client.wait_for_server(timeout_sec=15):
                    raise RuntimeError('Planner action not ready')
                goal = ComputePathToPose.Goal()
                goal.planner_id = 'GridBased'
                goal.use_start = False  # Nav2 uses current localized pose, not an invented start.
                goal.goal.header.frame_id = 'map'
                end = scenario['points'][target]
                goal.goal.pose.position.x = end['x']
                goal.goal.pose.position.y = end['y']
                goal.goal.pose.orientation.w = 1.0
                handle = wait(node, client.send_goal_async(goal))
                if not handle.accepted:
                    raise RuntimeError('Planner rejected request')
                future = handle.get_result_async()
                try:
                    response = wait(node, future)
                except TimeoutError:
                    wait(node, handle.cancel_goal_async(), 5)
                    raise
                value = response.result
                if response.status != GoalStatus.STATUS_SUCCEEDED or value.error_code:
                    raise RuntimeError(f'Planner status={response.status} code={value.error_code}: {value.error_msg}')
                if value.path.header.frame_id != 'map' or any(p.header.frame_id not in ['', 'map'] for p in value.path.poses):
                    raise ValueError('Unexpected path frame')
                points = [(p.pose.position.x, p.pose.position.y) for p in value.path.poses]
                checks = audit(points, spec, allowed, scenario['shared_zone']['polygon'], scenario['robot_radius_with_margin_m'])
                begin = scenario['points'][start]
                checks['start_error_m'] = math.dist(points[0], (begin['x'], begin['y']))
                checks['goal_error_m'] = math.dist(points[-1], (end['x'], end['y']))
                checks['passed'] = all(checks[k] for k in ['center_in_allowed_lane', 'footprint_clear', 'shared_zone_crossed']) and checks['start_error_m'] <= .05 and checks['goal_error_m'] <= .04
                results[robot] = checks
                paths[robot] = points
                client.destroy()
            except Exception as error:
                results[robot] = dict(passed=False, error=str(error))
        payload = dict(domain=84, mode='PLAN_ONLY_NO_MOTION', map_sha256=spec.digest,
                       coordinates_confirmed=False, checks=results, paths=paths)
        logs = folder/'path_checks'
        logs.mkdir(exist_ok=True)
        stem = time.strftime('%Y%m%d_%H%M%S')
        output = logs/f'{stem}.json'
        output.write_text(json.dumps(payload, indent=2, allow_nan=False))
        image = Image.open(spec.image_path).convert('RGB')
        pixels = np.array(image)
        pixels[~allowed] = (100, 100, 100)
        pixels[allowed] = (180, 230, 240)
        image = Image.fromarray(pixels).resize((spec.width*4, spec.height*4))
        draw = ImageDraw.Draw(image)
        polygon = [tuple(v*4 for v in spec.world_to_image(*p)) for p in scenario['shared_zone']['polygon']]
        draw.line(polygon+[polygon[0]], fill='yellow', width=3)
        for robot, points in paths.items():
            if len(points)>1:
                draw.line([tuple(v*4 for v in spec.world_to_image(*p)) for p in points], fill='blue' if robot=='robot_1' else 'red', width=3)
        for label, point in scenario['points'].items():
            x,y = (v*4 for v in spec.world_to_image(point['x'],point['y']))
            draw.text((x+4,y), label, fill='black')
        image.save(logs/f'{stem}.png')
        print(json.dumps(dict(checks=results, report=str(output), preview=str(logs/f'{stem}.png')), indent=2))
        passed = len(results)==2 and all(v['passed'] for v in results.values())
        print('PATH CHECK ' + ('PASSED' if passed else 'FAILED') + ' — NO MOTION GOALS SENT')
        return 0 if passed else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())

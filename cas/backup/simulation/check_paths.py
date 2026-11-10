"""Request ComputePathToPose only. No Navigate, Spin or velocity publisher."""
import argparse
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
from mission_routes import routes, zone_distance


def wait(node, future, seconds=30):
    rclpy.spin_until_future_complete(node, future, timeout_sec=seconds)
    if not future.done():
        raise TimeoutError('Planner response timeout; no motion goal was sent')
    return future.result()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--segments', action='store_true', help='Plan each stop/permission leg without moving')
    args = parser.parse_args()
    folder = Path.home() / 'CAS_sim_ws/generated_map'
    report = json.loads((folder/'map_profile_report.json').read_text())
    scenario = json.loads((folder/'scenario.candidates.json').read_text())
    spec, _, allowed = arrays(report['source_map'], report['source_allowed_mask'])
    if scenario['map_sha256'] != spec.digest:
        raise ValueError('Candidate map mismatch')
    results = {}
    paths = {}
    reference = None
    if args.segments:
        for candidate in sorted((folder/'path_checks').glob('*.json'), reverse=True):
            data=json.loads(candidate.read_text())
            if (not data.get('explicit_future_starts') and data.get('map_sha256')==spec.digest
                    and all(data.get('checks',{}).get(name,{}).get('passed') for name in ['robot_1','robot_2'])
                    and all(name in data.get('paths',{}) for name in ['robot_1','robot_2'])):
                reference=data['paths'];break
        if reference is None:
            raise ValueError('Run full path check first; no matching passed reference paths')
    # Full-route mode only needs the direction, not segmented geometry.
    mission = routes(scenario,reference) if args.segments else {
        robot:dict(yaw=math.atan2(scenario['points'][target]['y']-scenario['points'][start]['y'],
                                  scenario['points'][target]['x']-scenario['points'][start]['x']))
        for robot,start,target in [('robot_1','1','B'),('robot_2','2','A')]}

    cases = []
    for robot, start, target in [('robot_1', '1', 'B'), ('robot_2', '2', 'A')]:
        if args.segments:
            cases.extend((robot, segment['name'], segment['start'], segment['goal']) for segment in mission[robot]['segments'])
        else:
            cases.append((robot, 'full', [scenario['points'][start][k] for k in ['x','y']], [scenario['points'][target][k] for k in ['x','y']]))
    rclpy.init()
    node = Node('cas_path_audit', parameter_overrides=[rclpy.parameter.Parameter('use_sim_time', value=True)])
    try:
        for robot, segment, begin, end in cases:
            key = f'{robot}/{segment}' if args.segments else robot
            try:
                if any(node.count_publishers(f'/{name}/cmd_vel') for name in ['robot_1', 'robot_2']):
                    raise RuntimeError('Motor output is not isolated; stop this check')
                client = ActionClient(node, ComputePathToPose, f'/{robot}/compute_path_to_pose')
                if not client.wait_for_server(timeout_sec=15):
                    raise RuntimeError('Planner action not ready')
                goal = ComputePathToPose.Goal()
                goal.planner_id = 'GridBased'
                goal.use_start = args.segments
                if args.segments:
                    # Future legs use explicit hypothetical start poses: planning only.
                    goal.start.header.frame_id = 'map'
                    goal.start.pose.position.x, goal.start.pose.position.y = begin
                    goal.start.pose.orientation.z = math.sin(mission[robot]['yaw']/2)
                    goal.start.pose.orientation.w = math.cos(mission[robot]['yaw']/2)
                goal.goal.header.frame_id = 'map'
                goal.goal.pose.position.x, goal.goal.pose.position.y = end
                goal.goal.pose.orientation.z = math.sin(mission[robot]['yaw']/2)
                goal.goal.pose.orientation.w = math.cos(mission[robot]['yaw']/2)
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
                checks['start_error_m'] = math.dist(points[0], begin)
                checks['goal_error_m'] = math.dist(points[-1], end)
                needs_crossing = segment in ['full','crossing']
                checks['zone_rule_ok'] = checks['shared_zone_crossed'] if needs_crossing else not checks['shared_zone_crossed']
                if not needs_crossing:
                    # Sample complete legs to check body/zone overlap before grant / after release.
                    minimum = float('inf')
                    for a,b in zip(points,points[1:]):
                        count=max(1, math.ceil(math.dist(a,b)/.0025))
                        for i in range(count+1):
                            p=[a[k]+(b[k]-a[k])*i/count for k in range(2)]
                            minimum=min(minimum,zone_distance(p,scenario['shared_zone']['polygon']))
                    checks['min_body_zone_gap_m'] = minimum-scenario['robot_radius_with_margin_m']-.00125
                    checks['zone_rule_ok'] = checks['zone_rule_ok'] and checks['min_body_zone_gap_m']>.04
                checks['passed'] = all(checks[k] for k in ['center_in_allowed_lane', 'footprint_clear', 'zone_rule_ok']) and checks['start_error_m'] <= .05 and checks['goal_error_m'] <= .04
                results[key] = checks
                paths[key] = points
                client.destroy()
            except Exception as error:
                results[key] = dict(passed=False, error=str(error))
        payload = dict(domain=84, mode='PLAN_ONLY_NO_MOTION', map_sha256=spec.digest,
                       coordinates_confirmed=False, explicit_future_starts=args.segments, mission_routes=mission, checks=results, paths=paths)
        logs = folder/'path_checks'
        logs.mkdir(exist_ok=True)
        stem = ('segments_' if args.segments else '') + time.strftime('%Y%m%d_%H%M%S')
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
                draw.line([tuple(v*4 for v in spec.world_to_image(*p)) for p in points], fill='blue' if robot.startswith('robot_1') else 'red', width=3)
        for label, point in scenario['points'].items():
            x,y = (v*4 for v in spec.world_to_image(point['x'],point['y']))
            draw.text((x+4,y), label, fill='black')
        if args.segments:
            for robot, route in mission.items():
                for label in ['wait','exit']:
                    x,y = (v*4 for v in spec.world_to_image(*route[label]))
                    draw.ellipse((x-4,y-4,x+4,y+4),outline='orange',width=2)
                    draw.text((x+4,y), robot[-1]+':'+label, fill='black')
        image.save(logs/f'{stem}.png')
        print(json.dumps(dict(checks=results, report=str(output), preview=str(logs/f'{stem}.png')), indent=2))
        passed = len(results)==len(cases) and all(v['passed'] for v in results.values())
        print('PATH CHECK ' + ('PASSED' if passed else 'FAILED') + ' — NO MOTION GOALS SENT')
        return 0 if passed else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())

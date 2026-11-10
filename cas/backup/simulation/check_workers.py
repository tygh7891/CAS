"""Read-only check of live two-Worker telemetry and prepared action interfaces."""
import json
import math
import os
from pathlib import Path
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from prepare_map import arrays
from path_geometry import audit
from zone_coordinator import MissionCoordinator
from nav2_worker import Nav2Worker


def load_bundle(folder):
    scenario=json.loads((folder/'scenario.candidates.json').read_text())
    report=json.loads((folder/'map_profile_report.json').read_text())
    spec,_,allowed=arrays(report['source_map'],report['source_allowed_mask'])
    for file in sorted((folder/'path_checks').glob('segments_*.json'),reverse=True):
        bundle=json.loads(file.read_text())
        if bundle.get('path_source')!='VERIFIED_FULL_PATH_SLICES':continue
        if bundle.get('map_sha256')!=spec.digest or scenario['map_sha256']!=spec.digest:continue
        expected={f'{robot}/{leg}' for robot in ['robot_1','robot_2'] for leg in ['approach','crossing','departure']}
        if set(bundle.get('checks',{}))!=expected or not all(v.get('passed') for v in bundle['checks'].values()):continue
        mission=bundle['mission_routes']
        if not all(math.dist(mission.get(r,{}).get('start',[math.inf,math.inf]),[scenario['points'][s]['x'],scenario['points'][s]['y']])<=.05
                   and math.dist(mission.get(r,{}).get('goal',[math.inf,math.inf]),[scenario['points'][t]['x'],scenario['points'][t]['y']])<=.04
                   for r,s,t in [('robot_1','1','B'),('robot_2','2','A')]):
            continue
        for robot,route in mission.items():
            for leg in route['segments']:
                actual=audit(leg['path'],spec,allowed,scenario['shared_zone']['polygon'],.10)
                if not actual['footprint_clear']:raise ValueError('Saved path fails current map audit')
                if actual['shared_zone_crossed']!=(leg['name']=='crossing'):raise ValueError('Saved path zone mismatch')
        return scenario,mission,str(file)
    raise ValueError('No matching passed segmented path report. Run check_paths.sh --segments first.')


def main():
    if os.environ.get('ROS_DOMAIN_ID')!='84':raise RuntimeError('Simulation domain 84 required')
    folder=Path.home()/'CAS_sim_ws/generated_map'
    scenario,mission,source=load_bundle(folder)
    coordinator=MissionCoordinator(mission,scenario['shared_zone']['polygon'])
    rclpy.init();executor=SingleThreadedExecutor()
    workers=[Nav2Worker(name,coordinator) for name in ['robot_1','robot_2']]
    for worker in workers:executor.add_node(worker)
    passed=False;stable=None;last_print=0.0;checks={}
    print('CAS WORKER CHECK: read-only; no mission start; action submission disabled',flush=True)
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            executor.spin_once(timeout_sec=.02)
            now=time.monotonic()
            for worker in workers:worker.poll(now)
            statuses=[worker.status(now) for worker in workers]
            checks={}
            for worker,status in zip(workers,statuses):
                name=worker.robot
                checks[name+'/telemetry']=status['observation_fresh']
                checks[name+'/follow_path']=status['follow_path']
                checks[name+'/spin']=status['spin']
                checks[name+'/start_pose']=status['pose'] is not None and math.dist(status['pose'],mission[name]['start'])<=.05
                checks[name+'/stopped']=status['odom_velocity'] is not None and abs(status['odom_velocity'][0])<=.005 and abs(status['odom_velocity'][1])<=.03
                checks[name+'/motor_output_disconnected']=worker.count_publishers(f'/{name}/cmd_vel')==0
                checks[name+'/submission_disabled']=not status['actions_enabled']
            if now-last_print>=2:
                print(json.dumps(dict(workers=statuses),ensure_ascii=False),flush=True);last_print=now
            if all(checks.values()):
                if stable is None:stable=now
                if now-stable>=1.0:passed=True;break
            else:stable=None
        payload=dict(mode='READ_ONLY_WORKERS',source_report=source,checks=checks,
                     workers=[worker.status(time.monotonic()) for worker in workers],
                     coordinator_started=False,commands_generated=len(coordinator.commands))
        logdir=folder/'worker_checks';logdir.mkdir(exist_ok=True)
        file=logdir/(time.strftime('%Y%m%d_%H%M%S')+'.json')
        file.write_text(json.dumps(payload,indent=2,allow_nan=False))
        print(json.dumps(payload,indent=2),flush=True)
        print(('WORKER CHECK PASSED' if passed else 'WORKER CHECK FAILED')+' — NO GOALS SENT\nREPORT: '+str(file))
        return 0 if passed else 1
    finally:
        for worker in workers:executor.remove_node(worker);worker.destroy_node()
        executor.shutdown();rclpy.shutdown()


if __name__=='__main__':raise SystemExit(main())

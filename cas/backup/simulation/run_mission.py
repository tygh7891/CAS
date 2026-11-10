"""Gazebo-only mission runner. --start is mandatory. Real domains unsupported."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String
from action_msgs.msg import GoalStatusArray
from check_workers import load_bundle
from nav2_worker import Nav2Worker
from zone_coordinator import MissionCoordinator
from prepare_map import arrays
from path_geometry import ClearanceMap
from velocity_gate import ROBOTS


def path_distance(point,path):
    minimum=float('inf')
    for a,b in zip(path,path[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];norm=dx*dx+dy*dy
        t=0.0 if norm==0 else max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/norm))
        minimum=min(minimum,math.dist(point,[a[0]+t*dx,a[1]+t*dy]))
    return minimum


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',action='store_true',help='Start motion of BOTH Gazebo robots')
    args=parser.parse_args()
    if not args.start:parser.error('--start required: this starts Gazebo motion')
    if os.environ.get('ROS_DOMAIN_ID')!='84' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
        raise RuntimeError('Only localhost Gazebo domain 84 is supported')
    lock=open(f'/tmp/cas_sim_mission_{os.getuid()}_84.lock','w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    folder=Path.home()/'CAS_sim_ws/generated_map'
    scenario,mission,report=load_bundle(folder)
    metadata=json.loads((folder/'map_profile_report.json').read_text())
    spec,_,allowed=arrays(metadata['source_map'],metadata['source_allowed_mask'])
    clearance=ClearanceMap(spec,allowed)
    coordinator=MissionCoordinator(mission,scenario['shared_zone']['polygon'])
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO);executor=SingleThreadedExecutor()
    workers={name:Nav2Worker(name,coordinator,allow_actions=True) for name in ROBOTS}
    for worker in workers.values():executor.add_node(worker)
    control=workers['robot_1'];session=uuid.uuid4().hex
    lease_pub=control.create_publisher(String,'/cas/sim_control/lease',1)
    relay_state={};external_actions={}
    def state_callback(msg):
        value=json.loads(msg.data)
        if value.get('session')==session:relay_state.update(value,received=time.monotonic())
    subscriptions=[control.create_subscription(String,'/cas/sim_control/relay_state',state_callback,1)]
    for robot in ROBOTS:
        for action in ['follow_path','spin','navigate_to_pose']:
            key=robot+'/'+action
            subscriptions.append(control.create_subscription(GoalStatusArray,f'/{robot}/{action}/_action/status',
                lambda msg,name=key:external_actions.update({name:any(s.status in [1,2,3] for s in msg.status_list)}),1))
    logs=folder/'mission_logs';logs.mkdir(exist_ok=True)
    logfile=logs/(time.strftime('%Y%m%d_%H%M%S')+'.jsonl')
    stream=logfile.open('w');relay=None;sequence=0;command_index=0;event_index=0
    started=False;success=False;failure=None;last_status=0.0;last_lease=0.0
    def log(kind,**values):
        entry=dict(wall_time=time.time(),kind=kind,**values)
        line=json.dumps(entry,ensure_ascii=False,allow_nan=False)
        print(line,flush=True);stream.write(line+'\n');stream.flush()
    def heartbeat(permits):
        nonlocal sequence,last_lease
        now=time.monotonic();sequence+=1
        msg=String();msg.data=json.dumps(dict(session=session,sequence=sequence,expires=now+.25,permits=permits))
        lease_pub.publish(msg);last_lease=now
    def spin_once():
        executor.spin_once(timeout_sec=.01)
        now=time.monotonic()
        for worker in workers.values():worker.poll(now)
        return now
    try:
        log('PREFLIGHT',source_report=report,mode='GAZEBO_ONLY',log=str(logfile))
        # Discover existing writers before creating our relay.
        until=time.monotonic()+2
        while time.monotonic()<until:spin_once()
        if any(control.count_publishers(f'/{robot}/cmd_vel') for robot in ROBOTS):
            raise RuntimeError('Existing cmd_vel publisher: stop other simulator control / relay first')
        relay=subprocess.Popen([sys.executable,str(Path(__file__).with_name('sim_velocity_relay.py')),'--session',session],start_new_session=True)
        deadline=time.monotonic()+25;stable=None
        while time.monotonic()<deadline:
            now=spin_once()
            if now-last_lease>.05:heartbeat({})
            if relay.poll() is not None:raise RuntimeError('Velocity relay exited')
            statuses=[worker.status(now) for worker in workers.values()]
            ready=bool(relay_state) and now-relay_state['received']<.5 and not relay_state.get('blocked')
            for status in statuses:
                ready=ready and status['observation_fresh'] and status['follow_path'] and status['spin']
                ready=ready and status['pose'] is not None and math.dist(status['pose'],mission[status['robot']]['start'])<=.05
                ready=ready and status['odom_velocity'] is not None and abs(status['odom_velocity'][0])<=.005 and abs(status['odom_velocity'][1])<=.03
            ready=ready and not any(external_actions.values())
            if ready:
                if stable is None:stable=now
                if now-stable>=1:break
            else:stable=None
        else:raise RuntimeError('Preflight did not become ready: '+json.dumps(statuses))
        coordinator.start();started=True
        log('MISSION_STARTED',sequence='wait -> permission -> exit -> destination -> spin -> stopped')
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            now=spin_once()
            if relay.poll() is not None:coordinator.halt('Velocity relay exited')
            if now-relay_state.get('received',0)>.5 or relay_state.get('blocked'):
                coordinator.halt('Velocity relay lost / lease expired')
            for name,r in coordinator.robots.items():
                if r['pose'] is None:continue
                if clearance.distance(r['pose'])<.10:coordinator.halt('Body clearance below 10cm: '+name)
                phase=r['phase']
                if phase in ['TO_WAIT','CROSSING','TO_GOAL']:
                    index={'TO_WAIT':0,'CROSSING':1,'TO_GOAL':2}[phase]
                    if path_distance(r['pose'],mission[name]['segments'][index]['path'])>.025:
                        coordinator.halt('Tracking deviation exceeds 2.5cm: '+name)
            poses=[coordinator.robots[name]['pose'] for name in ROBOTS]
            if all(p is not None for p in poses) and math.dist(*poses)<.22:
                coordinator.halt('Inter-robot separation below 22cm')
            coordinator.tick(now)
            while command_index<len(coordinator.commands):
                command=coordinator.commands[command_index];command_index+=1
                if coordinator.blocked and command['kind']!='CANCEL':continue
                try:
                    workers[command['robot']].submit(command)
                    log('COMMAND',robot=command['robot'],command_id=command['id'],command=command['kind'])
                except Exception as error:coordinator.halt('Worker dispatch: '+str(error))
            permits={name:worker.active for name,worker in workers.items()
                     if worker.active is not None and worker.goal_handle is not None and not worker.cancel_requested
                     and coordinator.robots[name]['phase'] in ['TO_WAIT','CROSSING','TO_GOAL','SPINNING']}
            if coordinator.blocked:permits={}
            if now-last_lease>.05:heartbeat(permits)
            while event_index<len(coordinator.events):
                log('EVENT',**coordinator.events[event_index]);event_index+=1
            if now-last_status>1:
                log('STATUS',owner=coordinator.owner,queue=coordinator.queue,
                    robots={name:dict(phase=r['phase'],pose=r['pose'],velocity=workers[name].velocity) for name,r in coordinator.robots.items()})
                last_status=now
            if coordinator.blocked:raise RuntimeError(coordinator.blocked)
            if all(r['phase']=='DONE' for r in coordinator.robots.values()):success=True;break
        else:raise RuntimeError('Mission wall-clock timeout')
    except (Exception,KeyboardInterrupt) as error:
        failure=str(error) or 'Operator interrupted'
        coordinator.halt(failure)
        log('HALTED',reason=failure,owner_retained=coordinator.owner)
    finally:
        # Leave relay alive while sending empty leases and waiting for zero odom.
        if rclpy.ok():
            for worker in workers.values():worker.cancel()
            until=time.monotonic()+2;stopped=False
            while time.monotonic()<until:
                now=spin_once();heartbeat({})
                stopped=all(w.velocity is not None and abs(w.velocity[0])<=.005 and abs(w.velocity[1])<=.03
                            and now-coordinator.robots[w.robot]['received']<.5 for w in workers.values())
            log('FINAL_STOP',confirmed=stopped,mission_success=success,reason=failure)
            if not stopped:success=False
        else:success=False
        if relay is not None:
            relay.terminate()
            try:relay.wait(timeout=3)
            except subprocess.TimeoutExpired:relay.kill();relay.wait()
        for worker in workers.values():executor.remove_node(worker);worker.destroy_node()
        executor.shutdown()
        if rclpy.ok():rclpy.shutdown()
        stream.close();lock.close()
    print(('MISSION PASSED' if success else 'MISSION STOPPED / NOT COMPLETE')+' | '+str(logfile),flush=True)
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())

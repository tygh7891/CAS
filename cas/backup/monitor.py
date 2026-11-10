#!/usr/bin/env python3
"""CAS read-only ROS2 monitor. Never publishes commands."""
import argparse
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time

ROBOTS = [('pinky1', 'robot_1', 14), ('pinky2', 'robot_2', 30)]
STALE = 3.0

def worker():
    import rclpy
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import Float32
    from rclpy.qos import qos_profile_sensor_data
    rclpy.init()
    node = rclpy.create_node('cas_readonly_monitor')
    def received(topic, msg):
        if topic == 'odom':
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            data = dict(x=p.x, y=p.y, yaw=math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)), v=msg.twist.twist.linear.x, w=msg.twist.twist.angular.z, frame=msg.header.frame_id)
        elif topic == 'scan':
            data = dict(samples=len(msg.ranges), valid=sum(math.isfinite(x) and msg.range_min <= x <= msg.range_max for x in msg.ranges))
        else:
            data = msg.data if math.isfinite(msg.data) else None
        print(json.dumps(dict(topic=topic, data=data)), flush=True)
    subscriptions = [node.create_subscription(cls, '/' + topic, lambda msg, t=topic: received(t, msg), qos_profile_sensor_data) for topic, cls in [('odom', Odometry), ('scan', LaserScan), ('battery/voltage', Float32), ('battery/percent', Float32)]]
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--duration', type=float, default=0, help='seconds; 0 runs until Ctrl+C')
    parser.add_argument('--json', action='store_true', help='print one final JSON snapshot; requires --duration')
    args = parser.parse_args()
    if args.worker:
        worker()
        return
    if args.duration < 0 or (args.json and args.duration <= 0):
        parser.error('--json requires --duration > 0; duration cannot be negative')
    events = queue.Queue()
    processes = []
    state = {name: dict(ip=ip, domain=domain, topics={}, errors=[]) for name, ip, domain in ROBOTS}
    def read_output(name, pipe, errors=False):
        for line in pipe:
            if errors:
                events.put((name, None, line.strip()))
            else:
                try:
                    events.put((name, json.loads(line), None))
                except ValueError:
                    events.put((name, None, line.strip()))
    def snapshot():
        now = time.monotonic()
        result = {}
        for name, info in state.items():
            topics = {topic: dict(data=entry['data'], age_s=round(now-entry['received'], 2), count=entry['count'], fresh=now-entry['received'] <= (12.0 if topic.startswith('battery/') else STALE)) for topic, entry in info['topics'].items()}
            odom = topics.get('odom', {})
            result[name] = dict(ip=info['ip'], domain=info['domain'], status='RECEIVING' if odom.get('fresh') else ('STALE' if odom else 'WAITING'), worker_exit=processes[list(state).index(name)].poll(), topics=topics, errors=info['errors'][-3:])
        return result
    start = time.monotonic()
    try:
        for name, ip, domain in ROBOTS:
            env = dict(os.environ, ROS_DOMAIN_ID=str(domain))
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), '--worker'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            processes.append(p)
            for pipe, errors in [(p.stdout, False), (p.stderr, True)]:
                threading.Thread(target=read_output, args=(name, pipe, errors), daemon=True).start()
        next_display = 0
        while args.duration == 0 or time.monotonic()-start < args.duration:
            try:
                name, event, error = events.get(timeout=0.1)
                if error:
                    state[name]['errors'] = (state[name]['errors']+[error])[-3:]
                elif event:
                    old = state[name]['topics'].get(event['topic'], {})
                    state[name]['topics'][event['topic']] = dict(data=event['data'], received=time.monotonic(), count=old.get('count', 0)+1)
            except queue.Empty:
                pass
            if not args.json and time.monotonic() >= next_display:
                snap = snapshot()
                lines = ['CAS | 읽기 전용 상태 모니터 | 종료: Ctrl+C', '위치는 로봇별 odom 기준(m), 공통 지도 좌표가 아닙니다.']
                for name, info in snap.items():
                    lines.append(f"\n{name}  {info['ip']}  Domain {info['domain']}  {info['status']}")
                    if info['worker_exit'] is not None:
                        lines.append(f"  수신 프로그램 종료: {info['worker_exit']}")
                    for topic in ['odom', 'scan', 'battery/voltage', 'battery/percent']:
                        item = info['topics'].get(topic)
                        lines.append(f"  {topic}: " + (f"{item['data']} | {item['age_s']}초 전 | {'정상' if item['fresh'] else '수신 지연'}" if item else '수신 대기'))
                    lines.extend('  오류: '+e for e in info['errors'])
                print(('\033[2J\033[H' if sys.stdout.isatty() else '')+'\n'.join(lines), flush=True)
                next_display = time.monotonic()+1
        if args.json:
            print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        pass
    finally:
        import signal
        for p in processes:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGINT)
        for p in processes:
            try:
                p.wait(timeout=4)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()

if __name__ == '__main__':
    main()

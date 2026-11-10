"""PC terminal: approved lifted-wheel test for robot1, domain 14 only."""
import json
import time
from pathlib import Path
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data

rclpy.init(domain_id=14)
node=rclpy.create_node('cas_robot1_timeout_test')
samples=[]
def odom(msg):
    samples.append(dict(t=time.monotonic(),v=msg.twist.twist.linear.x,w=msg.twist.twist.angular.z))
sub=node.create_subscription(Odometry,'/odom',odom,qos_profile_sensor_data)
pub=None
report={}
def wait(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        rclpy.spin_once(node,timeout_sec=0.02)
try:
    wait(2.0)
    if not samples or time.monotonic()-samples[-1]['t']>0.3:
        raise RuntimeError('No fresh odometry; no movement command sent')
    if abs(samples[-1]['v'])>0.003 or abs(samples[-1]['w'])>0.03:
        raise RuntimeError('Robot not stationary; no movement command sent')
    if node.get_publishers_info_by_topic('/cmd_vel'):
        raise RuntimeError('Another cmd_vel publisher exists; no movement command sent')
    pub=node.create_publisher(Twist,'/cmd_vel',1)
    wait(1.0)
    if pub.get_subscription_count()!=1:
        raise RuntimeError('Expected exactly one cmd_vel subscriber; no movement command sent')
    cmd=Twist();cmd.linear.x=0.02
    start=time.monotonic()
    last_sent=None
    for _ in range(10):
        pub.publish(cmd)
        last_sent=time.monotonic()
        wait(0.1)
    wait(2.0)
    relevant=[s for s in samples if s['t']>=start]
    moving=[s for s in relevant if abs(s['v'])>0.003]
    # Require a 0.3 second window of fresh odometry below the thresholds.
    stopped_at=None
    for i,s in enumerate(relevant):
        if s['t']<last_sent or not moving or s['t']<moving[0]['t']:
            continue
        window=[x for x in relevant[i:] if x['t']<=s['t']+0.3]
        if len(window)>=6 and window[-1]['t']-s['t']>=0.25 and all(abs(x['v'])<0.003 and abs(x['w'])<0.03 for x in window):
            stopped_at=s['t'];break
    tail=[s for s in relevant if s['t']>last_sent+1.0]
    report=dict(domain=14,command_m_s=0.02,commands=10,max_measured_v=max((abs(s['v']) for s in relevant),default=0),motion_observed=bool(moving),stop_after_last_command_s=None if stopped_at is None else round(stopped_at-last_sent,3),late_sample_count=len(tail),late_samples_stationary=bool(tail) and all(abs(s['v'])<0.003 and abs(s['w'])<0.03 for s in tail),samples=[dict(t_after_last=round(s['t']-last_sent,3),v=s['v'],w=s['w']) for s in relevant])
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False),flush=True)
finally:
    if pub is not None:
        for _ in range(3):
            pub.publish(Twist());wait(0.1)
    if report:
        Path(__file__).resolve().with_name('robot1_test_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    node.destroy_node()
    rclpy.shutdown()

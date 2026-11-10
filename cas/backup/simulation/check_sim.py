"""Read-only ROS checks for B2 shared world. Run with isolated environment."""
import math
import time
import json
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan,JointState
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage

rclpy.init()
n=Node('cas_b2_readonly_check')
counts={};latest={};errors=[];subs=[]
def callback(key,msg):
    counts[key]=counts.get(key,0)+1
    if key=='clock':latest[key]=msg.clock.sec+msg.clock.nanosec/1e9;return
    robot,topic=key.split('/')
    if topic=='odom':
        latest[key]=dict(frame=msg.header.frame_id,child=msg.child_frame_id,x=msg.pose.pose.position.x,y=msg.pose.pose.position.y)
        if msg.header.frame_id!=robot+'/odom' or msg.child_frame_id!=robot+'/base_footprint':errors.append(key+' frame mismatch')
    elif topic=='scan':
        latest[key]=dict(frame=msg.header.frame_id,samples=len(msg.ranges),finite=sum(math.isfinite(v) for v in msg.ranges))
        if msg.header.frame_id!=robot+'/rplidar_link':errors.append(key+' frame mismatch')
    elif topic=='joint_states':
        latest[key]=list(msg.name)
        if any(not name.startswith(robot+'/') for name in msg.name):errors.append(key+' unprefixed joint')
    else:
        latest[key]=[(t.header.frame_id,t.child_frame_id) for t in msg.transforms]
        if any(not t.header.frame_id.startswith(robot+'/') or not t.child_frame_id.startswith(robot+'/') for t in msg.transforms):errors.append(key+' unprefixed frame')
subs.append(n.create_subscription(Clock,'/clock',lambda m:callback('clock',m),qos_profile_sensor_data))
for robot in ['robot_1','robot_2']:
    for topic,cls in [('odom',Odometry),('scan',LaserScan),('joint_states',JointState),('tf',TFMessage)]:
        key=robot+'/'+topic
        subs.append(n.create_subscription(cls,'/'+key,lambda m,k=key:callback(k,m),qos_profile_sensor_data))
clock_start=None
try:
    end=time.monotonic()+15
    while time.monotonic()<end:
        rclpy.spin_once(n,timeout_sec=.1)
        if clock_start is None and 'clock' in latest:clock_start=latest['clock']
    checks={k:counts.get(k,0)>1 for k in ['clock']+[r+'/'+t for r in ['robot_1','robot_2'] for t in ['odom','scan','joint_states','tf']]}
    checks['clock_advancing']=clock_start is not None and latest.get('clock',0)>clock_start
    for robot in ['robot_1','robot_2']:
        checks[robot+'/cmd_vel_receiver']=bool(n.get_subscriptions_info_by_topic('/'+robot+'/cmd_vel'))
        checks[robot+'/lidar_ranges']=latest.get(robot+'/scan',{}).get('finite',0)>0
    print(json.dumps(dict(domain=n.context.get_domain_id(),checks=checks,counts=counts,latest=latest,errors=sorted(set(errors))),ensure_ascii=False,indent=2))
    good=all(checks.values()) and not errors
    print('B2 SENSOR CHECK PASSED (SIMULATION ONLY)' if good else 'B2 SENSOR CHECK FAILED; inspect Gazebo logs')
finally:
    n.destroy_node()
    if rclpy.ok():rclpy.shutdown()
raise SystemExit(0 if good else 1)

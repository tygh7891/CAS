"""Read real robot1 telemetry only; never create command publishers or Actions."""
import json
import math
import os
import time
os.environ['ROS_DOMAIN_ID']='14'
os.environ.pop('ROS_LOCALHOST_ONLY',None)
os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE']='SUBNET'
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32
from rclpy.qos import qos_profile_sensor_data
rclpy.init()
n=Node('cas_a3_robot1_readonly')
state={}
def receive(topic,msg):
    if topic=='odom':
        p=msg.pose.pose.position
        data=dict(x=p.x,y=p.y,v=msg.twist.twist.linear.x,w=msg.twist.twist.angular.z,frame=msg.header.frame_id)
    else:
        data=msg.data if math.isfinite(msg.data) else None
    state[topic]=dict(data=data,received=time.monotonic())
subs=[n.create_subscription(cls,'/'+topic,lambda msg,t=topic:receive(t,msg),qos_profile_sensor_data) for topic,cls in [('odom',Odometry),('battery/percent',Float32),('battery/voltage',Float32)]]
last=0.0
try:
    while rclpy.ok():
        rclpy.spin_once(n,timeout_sec=0.1)
        now=time.monotonic()
        if now-last>=1.0:
            result={k:dict(data=v['data'],age_s=round(now-v['received'],2)) for k,v in state.items()}
            odom=result.get('odom')
            status='RECEIVING' if odom and odom['age_s']<=3 else ('STALE' if odom else 'WAITING')
            print(json.dumps(dict(mode='REAL_READ_ONLY',robot_id='robot_1',domain=14,status=status,topics=result)),flush=True)
            last=now
except KeyboardInterrupt:
    pass
finally:
    n.destroy_node()
    if rclpy.ok():rclpy.shutdown()

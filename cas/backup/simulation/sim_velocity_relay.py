"""Independent wall-clock watchdog: preview velocity -> Gazebo, domain 84 only."""
import argparse
import json
import os
import time
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from velocity_gate import VelocityGate, ROBOTS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',required=True);args=parser.parse_args()
    if os.environ.get('ROS_DOMAIN_ID')!='84' or os.environ.get('ROS_LOCALHOST_ONLY')!='1':
        raise RuntimeError('Relay requires localhost-only simulation domain 84')
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO);node=Node('cas_sim_velocity_relay')
    gate=VelocityGate(args.session)
    publishers={robot:node.create_publisher(Twist,f'/{robot}/cmd_vel',1) for robot in ROBOTS}
    state_pub=node.create_publisher(String,'/cas/sim_control/relay_state',1)
    def lease(message):
        try:gate.lease(json.loads(message.data),time.monotonic())
        except (ValueError,TypeError):pass
    subscriptions=[node.create_subscription(String,'/cas/sim_control/lease',lease,1)]
    for robot in ROBOTS:
        subscriptions.append(node.create_subscription(Twist,f'/{robot}/nav2_preview_cmd_vel',
            lambda msg,name=robot:gate.velocity(name,msg.linear.x,msg.angular.z,time.monotonic()),1))
    def tick():
        now=time.monotonic()
        for robot,publisher in publishers.items():
            command=Twist();command.linear.x,command.angular.z=gate.output(robot,now);publisher.publish(command)
        state=String();state.data=json.dumps(dict(session=args.session,blocked=gate.blocked,sequence=gate.sequence))
        state_pub.publish(state)
    timer=node.create_timer(.025,tick)  # Node uses wall clock; Gazebo pause cannot stop watchdog.
    print('CAS SIM RELAY: zeros until authorized lease; max 0.08m/s, 0.4rad/s',flush=True)
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        if rclpy.ok():
            for _ in range(8):
                for publisher in publishers.values():publisher.publish(Twist())
                time.sleep(.025)
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':main()

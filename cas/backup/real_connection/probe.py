"""Read-only physical-robot discovery. No Action clients or command publishers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rclpy.action.graph import get_action_server_names_and_types_by_node
from rclpy.parameter import parameter_value_to_python
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
from rcl_interfaces.srv import GetParameters
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import LaserScan
from tf2_msgs.msg import TFMessage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot',required=True,choices=['robot_1','robot_2'])
    parser.add_argument('--domain',required=True,type=int,choices=[14,30])
    args=parser.parse_args()
    rclpy.init(domain_id=args.domain)
    node=Node('cas_real_readonly_probe_'+args.robot)
    print(f'{args.robot}: domain {args.domain} discovery / telemetry only; NO MOTION COMMANDS',flush=True)
    observations={};tf_edges={};subscriptions=[];clients={};futures={};parameters={};parameter_errors={}
    def record(topic,msg):
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
        value=dict(frame=msg.header.frame_id,source_stamp=stamp,pc_wall_minus_source_s=time.time()-stamp)
        if isinstance(msg,Odometry):
            value.update(child_frame=msg.child_frame_id,x=msg.pose.pose.position.x,y=msg.pose.pose.position.y,
                         linear=msg.twist.twist.linear.x,angular=msg.twist.twist.angular.z)
        elif isinstance(msg,LaserScan):value.update(samples=len(msg.ranges))
        else:
            origin=msg.info.origin
            value.update(width=msg.info.width,height=msg.info.height,resolution=msg.info.resolution,
                         origin=dict(x=origin.position.x,y=origin.position.y,
                                     q=[origin.orientation.x,origin.orientation.y,origin.orientation.z,origin.orientation.w]),
                         occupancy_sha256=hashlib.sha256(msg.data.tobytes()).hexdigest())
        observations[topic]=value
    def transforms(topic,msg):
        edges=tf_edges.setdefault(topic,{})
        for tf in msg.transforms:
            edges[(tf.header.frame_id,tf.child_frame_id)]=dict(parent=tf.header.frame_id,child=tf.child_frame_id,
                source_stamp=tf.header.stamp.sec+tf.header.stamp.nanosec/1e9)
        observations[topic]=list(edges.values())
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
        nodes=sorted(node.get_node_names_and_namespaces())
        topics=dict(node.get_topic_names_and_types())
        actions={}
        for name,namespace in nodes:
            if name==node.get_name():continue
            for action,types in get_action_server_names_and_types_by_node(node,name,namespace):actions[action]=types
            if any(word in name for word in ['amcl','controller_server','planner_server','behavior_server','map_server','bt_navigator','local_costmap','global_costmap']):
                full=namespace.rstrip('/')+'/'+name
                client=node.create_client(GetParameters,full+'/get_parameters');clients[full]=client
        for topic,types in topics.items():
            if 'nav_msgs/msg/Odometry' in types:
                subscriptions.append(node.create_subscription(Odometry,topic,lambda msg,t=topic:record(t,msg),qos_profile_sensor_data))
            elif 'sensor_msgs/msg/LaserScan' in types:
                subscriptions.append(node.create_subscription(LaserScan,topic,lambda msg,t=topic:record(t,msg),qos_profile_sensor_data))
            elif 'nav_msgs/msg/OccupancyGrid' in types and topic.endswith('/map'):
                subscriptions.append(node.create_subscription(OccupancyGrid,topic,lambda msg,t=topic:record(t,msg),
                    QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL)))
            elif 'tf2_msgs/msg/TFMessage' in types:
                qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL) if topic.endswith('/tf_static') else qos_profile_sensor_data
                subscriptions.append(node.create_subscription(TFMessage,topic,lambda msg,t=topic:transforms(t,msg),qos))
        names=['use_sim_time','robot_base_frame','base_frame_id','odom_frame_id','global_frame','global_frame_id','robot_radius','footprint_padding','yaml_filename']
        deadline=time.monotonic()+6
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.02)
            for full,client in clients.items():
                if not client.service_is_ready():continue
                for name in names:
                    key=(full,name)
                    if key not in futures:
                        request=GetParameters.Request();request.names=[name]
                        futures[key]=client.call_async(request)
                    elif name not in parameters.get(full,{}) and futures[key].done():
                        try:
                            values=futures[key].result().values
                            parameters.setdefault(full,{})[name]=parameter_value_to_python(values[0]) if values else None
                            if not values:parameter_errors.setdefault(full,{})[name]='No value returned (possibly undeclared)'
                        except Exception as error:
                            parameters.setdefault(full,{})[name]=None
                            parameter_errors.setdefault(full,{})[name]=str(error)
        endpoints={}
        for topic in topics:
            if topic.endswith('/cmd_vel') or topic.endswith('/cmd_vel_nav'):
                endpoints[topic]=dict(
                    publishers=[info.node_namespace.rstrip('/')+'/'+info.node_name for info in node.get_publishers_info_by_topic(topic)],
                    subscribers=[info.node_namespace.rstrip('/')+'/'+info.node_name for info in node.get_subscriptions_info_by_topic(topic)])
        result=dict(mode='READ_ONLY_REAL_DISCOVERY',expected_robot=args.robot,domain=args.domain,
                    identity_verified=False,note='Domain mapping is provisional; discovery does not verify physical identity or authorize motion.',
                    network={key:os.environ.get(key) for key in ['ROS_LOCALHOST_ONLY','ROS_AUTOMATIC_DISCOVERY_RANGE','RMW_IMPLEMENTATION']},
                    nodes=[namespace.rstrip('/')+'/'+name for name,namespace in nodes if name!=node.get_name()],
                    topics=topics,action_servers=actions,cmd_vel_endpoints=endpoints,observations=observations,parameters=parameters,parameter_errors=parameter_errors)
        directory=Path(__file__).resolve().parent/'logs';directory.mkdir(exist_ok=True)
        file=directory/(args.robot+'_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
        file.write_text(json.dumps(result,indent=2,ensure_ascii=False))
        print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
        print('READ-ONLY PROBE COMPLETE; NOT A MOTION READINESS APPROVAL\nREPORT: '+str(file),flush=True)
        return 0
    finally:
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':raise SystemExit(main())

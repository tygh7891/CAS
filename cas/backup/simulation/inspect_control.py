"""Read-only publisher / relay diagnostics, no goals or velocity output."""
import json
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main():
    rclpy.init();node=Node('cas_inspect_control');states=[]
    subscription=node.create_subscription(String,'/cas/sim_control/relay_state',lambda msg:states.append(msg.data),1)
    try:
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
        topics={}
        for robot in ['robot_1','robot_2']:
            for name in ['cmd_vel','nav2_preview_cmd_vel']:
                topic=f'/{robot}/{name}'
                topics[topic]=[dict(node=info.node_namespace.rstrip('/')+'/'+info.node_name,type=info.topic_type)
                               for info in node.get_publishers_info_by_topic(topic)]
        print(json.dumps(dict(publishers=topics,relay_states=states[-3:]),indent=2))
        print('READ ONLY: no command sent')
    finally:
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

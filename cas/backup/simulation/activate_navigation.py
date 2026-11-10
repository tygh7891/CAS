"""Wait for localization TF and advancing clock, then activate Nav2; no goals."""
import argparse
import time
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.time import Time
from tf2_ros import Buffer,TransformListener
from lifecycle_msgs.srv import GetState
from nav2_msgs.srv import ManageLifecycleNodes


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--robot',required=True,choices=['robot_1','robot_2']);args=parser.parse_args()
    robot=args.robot;rclpy.init()
    node=Node('cas_navigation_start_gate',namespace=robot,parameter_overrides=[Parameter('use_sim_time',value=True)],
              cli_args=['--ros-args','-r',f'/tf:=/{robot}/tf','-r',f'/tf_static:=/{robot}/tf_static'])
    buffer=Buffer();listener=TransformListener(buffer,node)
    state=node.create_client(GetState,f'/{robot}/amcl/get_state')
    manager=node.create_client(ManageLifecycleNodes,f'/{robot}/lifecycle_manager_navigation/manage_nodes')
    pending=None;active=False;last=0;stable=None
    try:
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.02)
            if pending is None and state.service_is_ready():pending=state.call_async(GetState.Request())
            elif pending is not None and pending.done():
                active=pending.result().current_state.id==3;pending=None
            clock=node.get_clock().now().nanoseconds
            valid=active and clock>last>0 and manager.service_is_ready()
            if valid:
                try:buffer.lookup_transform('map',f'{robot}/base_footprint',Time())
                except Exception:valid=False
            if valid:
                if stable is None:stable=time.monotonic()
                if time.monotonic()-stable>=1:
                    request=ManageLifecycleNodes.Request();request.command=ManageLifecycleNodes.Request.STARTUP
                    future=manager.call_async(request)
                    rclpy.spin_until_future_complete(node,future,timeout_sec=60)
                    if not future.done() or not future.result().success:raise RuntimeError('Navigation startup failed; inspect lifecycle logs')
                    print(robot+': NAVIGATION ACTIVE (localization / clock ready)',flush=True)
                    return 0
            # Clock callbacks and service callbacks interleave: unchanged time is normal.
            elif not active or clock<=0:stable=None
            last=max(last,clock)
        raise RuntimeError(robot+': localization/clock readiness timeout; no motion commands sent')
    finally:
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':raise SystemExit(main())

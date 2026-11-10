"""PC-side per-robot Nav2 adapter. Default is read-only; no cmd_vel publisher."""
import math
import time
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from nav2_msgs.action import FollowPath, Spin
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener


def make_goal(command):
    if command['kind']=='FOLLOW_PATH':
        points=command['target']
        if len(points)<2 or not all(len(p)==2 and all(math.isfinite(v) for v in p) for p in points):
            raise ValueError('Invalid verified path')
        goal=FollowPath.Goal()
        goal.controller_id='FollowPath'
        goal.goal_checker_id='general_goal_checker'
        goal.progress_checker_id='progress_checker'
        goal.path.header.frame_id='map'
        for i,point in enumerate(points):
            pose=PoseStamped()
            pose.header.frame_id='map'
            pose.pose.position.x=float(point[0]);pose.pose.position.y=float(point[1])
            a,b=(point,points[i+1]) if i+1<len(points) else (points[i-1],point)
            yaw=math.atan2(b[1]-a[1],b[0]-a[0])
            pose.pose.orientation.z=math.sin(yaw/2)
            pose.pose.orientation.w=math.cos(yaw/2)
            goal.path.poses.append(pose)
        return goal
    if command['kind']=='SPIN':
        if not math.isfinite(command['target']) or abs(command['target'])>2*math.pi+1e-6:
            raise ValueError('Invalid spin angle')
        goal=Spin.Goal();goal.target_yaw=float(command['target']);goal.time_allowance.sec=60
        return goal
    raise ValueError('Unsupported command kind')


def source_valid(stamp,clock,previous):
    return all(math.isfinite(v) for v in [stamp,clock]) and stamp>previous and -.05<=clock-stamp<=.5


class Nav2Worker(Node):
    def __init__(self,robot,coordinator,allow_actions=False):
        if robot not in ['robot_1','robot_2']:raise ValueError('Unknown robot')
        super().__init__('cas_nav2_worker',namespace=robot,
                         parameter_overrides=[Parameter('use_sim_time',value=True)],
                         cli_args=['--ros-args','-r',f'/tf:=/{robot}/tf','-r',f'/tf_static:=/{robot}/tf_static'])
        self.robot,self.coordinator,self.allow_actions=robot,coordinator,allow_actions
        self.buffer=Buffer();self.listener=TransformListener(self.buffer,self)
        self.action_clients={'FOLLOW_PATH':ActionClient(self,FollowPath,f'/{robot}/follow_path'),
                      'SPIN':ActionClient(self,Spin,f'/{robot}/spin')}
        self.subscription=self.create_subscription(Odometry,f'/{robot}/odom',self.odom_callback,qos_profile_sensor_data)
        self.odom=None;self.received=-math.inf;self.source=-math.inf;self.velocity=None
        self.active=None;self.goal_handle=None;self.cancel_requested=False;self.deadline=0.0
        self.odom_count=0;self.reject_count=0;self.last_clock_delta=None
        self.last_error='Waiting for odometry / TF'
        self.feedback=None

    def odom_callback(self,msg):
        self.odom_count+=1
        if msg.header.frame_id!=f'{self.robot}/odom' or msg.child_frame_id!=f'{self.robot}/base_footprint':
            self.last_error='Unexpected odom frame';return
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
        clock=self.get_clock().now().nanoseconds/1e9
        old=self.source
        if self.odom is not None:
            previous=self.odom.header.stamp
            old=max(old,previous.sec+previous.nanosec/1e9)
        self.last_clock_delta=clock-stamp
        if not source_valid(stamp,clock,old):
            self.reject_count+=1
            self.last_error=f'Odom stamp rejected: clock-stamp={clock-stamp:.3f}s, previous={old:.3f}, stamp={stamp:.3f}'
            return
        self.odom=msg;self.received=time.monotonic()

    def poll(self,now):
        if self.active is not None and now>self.deadline and not self.cancel_requested:
            self.coordinator.halt('Worker action timeout: '+self.robot)
            self.cancel()
        if self.odom is None:return
        msg=self.odom;stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9
        if stamp<=self.source or now-self.received>.5:return
        clock=self.get_clock().now().nanoseconds/1e9
        if not source_valid(stamp,clock,self.source):return
        try:
            tf=self.buffer.lookup_transform('map',f'{self.robot}/base_footprint',Time.from_msg(msg.header.stamp))
        except Exception as error:
            self.last_error=str(error);return
        twist=msg.twist.twist
        linear=math.hypot(twist.linear.x,twist.linear.y);angular=twist.angular.z
        pose=[tf.transform.translation.x,tf.transform.translation.y]
        if self.coordinator.observation(self.robot,pose,stamp,self.received,linear,angular):
            self.source=stamp;self.velocity=[linear,angular];self.last_error=None

    def submit(self,command):
        if command['robot']!=self.robot:raise ValueError('Wrong-robot command rejected')
        if not self.allow_actions:raise RuntimeError('Read-only Worker: action submission disabled')
        if command['kind']=='CANCEL':self.cancel();return
        if self.active is not None:raise RuntimeError('Another command is still active')
        goal=make_goal(command)
        client=self.action_clients[command['kind']]
        if not client.server_is_ready():raise RuntimeError('Action server not ready')
        self.active=command['id'];self.goal_handle=None;self.cancel_requested=False
        self.deadline=time.monotonic()+120
        command_id=self.active
        future=client.send_goal_async(goal,feedback_callback=lambda msg:self.on_feedback(command_id,msg))
        future.add_done_callback(lambda result:self.accepted(command_id,result))

    def on_feedback(self,command_id,message):
        if command_id!=self.active:return
        feedback=message.feedback
        self.feedback={field:getattr(feedback,field) for field in ['distance_to_goal','speed','angular_distance_traveled'] if hasattr(feedback,field)}

    def accepted(self,command_id,future):
        try:
            handle=future.result()
            if not handle.accepted:
                self.finish(command_id,False);return
            self.goal_handle=handle
            # Cancellation before delayed goal acceptance must still cancel it.
            if self.cancel_requested:handle.cancel_goal_async()
            handle.get_result_async().add_done_callback(lambda result:self.completed(command_id,result))
        except Exception as error:
            self.last_error=str(error);self.finish(command_id,False)

    def completed(self,command_id,future):
        try:
            response=future.result()
            success=response.status==GoalStatus.STATUS_SUCCEEDED and response.result.error_code==0
            if not success:
                self.last_error=f'Nav2 status={response.status}, code={response.result.error_code}: {response.result.error_msg}'
                self.get_logger().error(self.last_error)
            self.finish(command_id,success)
        except Exception as error:
            self.last_error=str(error);self.finish(command_id,False)

    def finish(self,command_id,success):
        if command_id!=self.active:return
        self.active=None;self.goal_handle=None
        self.coordinator.result(self.robot,command_id,success)

    def cancel(self):
        self.cancel_requested=True
        if self.goal_handle is not None:self.goal_handle.cancel_goal_async()

    def status(self,now):
        r=self.coordinator.robots[self.robot]
        age=None if not math.isfinite(r['received']) else now-r['received']
        return dict(robot=self.robot,follow_path=self.action_clients['FOLLOW_PATH'].server_is_ready(),
                    spin=self.action_clients['SPIN'].server_is_ready(),pose=r['pose'],pose_age_s=age,
                    odom_velocity=self.velocity,observation_fresh=age is not None and 0<=age<1.0,
                    actions_enabled=self.allow_actions,error=self.last_error,odom_messages=self.odom_count,
                    rejected_odom=self.reject_count,clock_minus_odom_s=self.last_clock_delta)

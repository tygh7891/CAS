"""Adapter checks without starting ROS nodes or sending any action goals."""
import ast
import inspect
import math
from concurrent.futures import Future
from types import SimpleNamespace
import unittest
from nav2_worker import Nav2Worker, make_goal, source_valid
from rclpy.node import Node
from action_msgs.msg import GoalStatus


class WorkerTests(unittest.TestCase):
    def test_worker_attributes_do_not_shadow_readonly_node_properties(self):
        tree=ast.parse(inspect.getsource(Nav2Worker))
        assigned={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)
                  and isinstance(n.ctx,ast.Store) and isinstance(n.value,ast.Name) and n.value.id=='self'}
        readonly={name for base in Node.__mro__ for name,value in vars(base).items()
                  if isinstance(value,property) and value.fset is None}
        self.assertFalse(assigned & readonly, assigned & readonly)

    def test_follow_path_preserves_points_and_tangent_yaw(self):
        points=[[.1,.2],[.2,.3],[.3,.4]]
        goal=make_goal(dict(kind='FOLLOW_PATH',target=points))
        self.assertEqual(goal.path.header.frame_id,'map')
        self.assertEqual([[p.pose.position.x,p.pose.position.y] for p in goal.path.poses],points)
        self.assertAlmostEqual(goal.path.poses[-1].pose.orientation.z,math.sin(math.pi/8))
        self.assertEqual(goal.controller_id,'FollowPath')
        hooked=[[0.0,0.0],[0.04,0.0],[0.045,0.005]]
        hook_goal=make_goal(dict(kind='FOLLOW_PATH',target=hooked))
        expected_yaw=math.atan2(0.005,0.045)
        self.assertAlmostEqual(hook_goal.path.poses[-1].pose.orientation.z,math.sin(expected_yaw/2))

    def test_wrong_robot_and_readonly_submission_are_rejected(self):
        fake=SimpleNamespace(robot='robot_1',allow_actions=False)
        with self.assertRaises(ValueError):Nav2Worker.submit(fake,dict(robot='robot_2',kind='SPIN'))
        with self.assertRaises(RuntimeError):Nav2Worker.submit(fake,dict(robot='robot_1',kind='SPIN'))

    def test_stale_replayed_and_future_source_stamps_rejected(self):
        self.assertTrue(source_valid(10,10.1,9))
        self.assertFalse(source_valid(9,10,9))
        self.assertFalse(source_valid(9.1,10,9))
        self.assertFalse(source_valid(11,10,9))

    def test_cancel_before_delayed_acceptance_cancels_accepted_goal(self):
        class Handle:
            accepted=True
            canceled=False
            def cancel_goal_async(self):self.canceled=True
            def get_result_async(self):return Future()
        handle=Handle();future=Future();future.set_result(handle)
        fake=SimpleNamespace(goal_handle=None,cancel_requested=True,
                             finish=lambda *a:self.fail('Unexpected finish'),completed=lambda *a:None)
        Nav2Worker.accepted(fake,7,future)
        self.assertTrue(handle.canceled)

    def test_abort_or_nonzero_error_is_not_success(self):
        for status,code,expected in [(GoalStatus.STATUS_SUCCEEDED,0,True),
                                      (GoalStatus.STATUS_ABORTED,0,False),
                                      (GoalStatus.STATUS_SUCCEEDED,106,False)]:
            values=[]
            fake=SimpleNamespace(finish=lambda *a:values.append(a),get_logger=lambda:SimpleNamespace(error=lambda message:None))
            future=Future();future.set_result(SimpleNamespace(status=status,result=SimpleNamespace(error_code=code,error_msg='test')))
            Nav2Worker.completed(fake,7,future)
            self.assertEqual(values,[(7,expected)])

    def test_invalid_path_or_spin_rejected(self):
        for command in [dict(kind='FOLLOW_PATH',target=[[0,0]]),
                        dict(kind='FOLLOW_PATH',target=[[0,0],[math.nan,0]]),
                        dict(kind='SPIN',target=math.inf)]:
            with self.assertRaises(ValueError):make_goal(command)


if __name__=='__main__':unittest.main(verbosity=2)

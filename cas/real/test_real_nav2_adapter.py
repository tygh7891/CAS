"""No ROS, network or physical motion: physical coordinator contract tests."""
import json
import math
from pathlib import Path
import time
import unittest

from real_nav2_adapter import RealNav2Adapter, ROBOTS, RADIUS, zone_distance
from service import AppService, RequestError


class PhysicalFlow(unittest.TestCase):
    def setUp(self):
        self.a = RealNav2Adapter(Path(__file__).with_name('real_config.json'), RequestError, start_workers=False)
        self.sent = []
        self.a.send = lambda n, c: self.sent.append((n,c))
        for n in ROBOTS:
            self.feed(n, self.a.points[n]['start'])

    def feed(self, n, pose, result=None, busy=None):
        self.a.telemetry[n] = dict(pose=list(pose), ready=True, velocity=[0,0], result=result, busy=busy)
        self.a.received[n] = time.monotonic()
        self.a.rows[n]['stop_since'] = time.monotonic()-1

    def complete(self, n, pose):
        cid = self.a.rows[n]['command']
        self.feed(n, pose, {'id':cid,'ok':True,'detail':'ok'})
        self.a.tick()

    def test_startup_sends_no_commands(self):
        self.a.tick()
        self.assertEqual(self.sent, [])
        self.assertTrue(all(r['task_state']=='IDLE' for r in self.a.snapshot()['simulation']['robots']))

    def test_waits_allow_body_and_nav2_goal_tolerance(self):
        for pose in self.a.waits.values():
            self.assertGreater(zone_distance(pose,self.a.zone)-RADIUS, .03)
            self.assertAlmostEqual(zone_distance(pose,self.a.zone), .16, places=6)

    def test_simultaneous_requests_grant_one_and_release_while_moving(self):
        self.a.start(list(ROBOTS),'s')
        for n in ROBOTS:
            cid=self.a.rows[n]['command']
            self.feed(n,self.a.waits[n],{'id':cid,'ok':True,'detail':'ok'})
        self.a.tick()
        self.assertEqual(self.a.owner,'robot_1')
        self.assertEqual(self.a.rows['robot_2']['phase'],'WAITING_ZONE')
        self.feed('robot_1',[-.81,-.62,0])
        self.a.tick()
        self.feed('robot_1',[-1.10,-.82,0])
        self.a.telemetry['robot_1']['velocity']=[.05,0]
        self.a.tick()
        self.assertEqual(self.a.rows['robot_1']['phase'],'TO_GOAL')
        self.assertEqual(self.a.owner,'robot_2')
        self.assertFalse(any(c['kind']=='CANCEL' for _,c in self.sent))

    def test_success_requires_spin_and_stop(self):
        self.a.start(['robot_1'],'s')
        self.complete('robot_1',self.a.waits['robot_1'])
        self.feed('robot_1',[-.81,-.62,0]);self.a.tick()
        self.feed('robot_1',[-1.1,-.82,0]);self.a.tick()
        goal=[*self.a.points['robot_1']['goal'],0]
        self.complete('robot_1',goal)
        self.assertEqual(self.a.rows['robot_1']['phase'],'SPINNING')
        self.assertEqual(self.a.rows['robot_1']['task_state'],'RUNNING')
        self.complete('robot_1',goal)
        self.assertEqual(self.a.rows['robot_1']['task_state'],'SUCCEEDED')

    def test_return_cancels_and_waits_before_motion(self):
        self.a.start(['robot_1'],'s')
        old=self.a.rows['robot_1']['command']
        self.a.telemetry['robot_1']['busy']=old
        self.a.return_home()
        count=len(self.sent)
        self.a.tick()
        self.assertEqual(len(self.sent),count)
        self.assertTrue(self.a.pending_returns)
        self.a.telemetry['robot_1']['busy']=None
        self.a.tick()
        self.assertEqual(self.sent[-1][1]['target'],self.a.points['robot_1']['start'])
        self.assertEqual(self.a.rows['robot_2']['task_state'],'IDLE')

    def test_return_occupant_first_and_then_both_initial_yaws(self):
        self.feed('robot_2',[-.81,-.62,0])
        self.a.return_home();self.a.tick()
        self.assertEqual(self.a.owner,'robot_2')
        self.complete('robot_2',self.a.points['robot_2']['start'])
        self.assertEqual(self.a.owner,'robot_1')
        self.assertEqual(self.sent[-1][1]['target'][2],-2.944)
        self.complete('robot_1',self.a.points['robot_1']['start'])
        self.assertFalse(self.a.returning)
        self.assertFalse(self.a.started)
        self.assertIsNone(self.a.owner)

    def test_stale_pose_cancels_active_goals(self):
        self.a.start(['robot_1'],'s')
        self.a.received['robot_1']=time.monotonic()-3
        self.a.tick()
        self.assertTrue(self.a.blocked)
        self.assertEqual(sum(c['kind']=='CANCEL' for _,c in self.sent),2)

    def test_old_results_do_not_advance_new_goals(self):
        self.a.start(['robot_1'],'s')
        self.a.telemetry['robot_1']['result']={'id':'old','ok':True}
        self.a.tick()
        self.assertEqual(self.a.rows['robot_1']['phase'],'TO_WAIT')

    def test_cancel_pending_return_prevents_restart(self):
        self.a.return_home()
        self.a.cancel('all')
        self.a.tick()
        self.assertFalse(self.a.pending_returns)
        self.assertFalse(any(c['kind']=='NAVIGATE' for _,c in self.sent))

    def test_failed_return_can_be_requested_again(self):
        self.a.return_home(); self.a.tick()
        self.a.halt('test failure')
        self.a.return_home()
        self.assertTrue(self.a.pending_returns)

    def test_service_routes_real_mode_return_without_sim_reset(self):
        service=AppService(adapter=self.a)
        request=dict(request_id='r',session_id=service.session,mode='REAL_NAV2')
        self.assertEqual(service.mode,'REAL_NAV2')
        service.command('/api/v1/return-home',request)
        self.assertTrue(self.a.pending_returns)
        with self.assertRaises(RequestError):
            service.command('/api/v1/reset',dict(request,request_id='x',confirm=True))
        service.close()


if __name__=='__main__':
    unittest.main()

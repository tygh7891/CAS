"""Real adapter methods with fake Workers; no ROS nodes, relays or motor output."""
import math
from types import SimpleNamespace
import unittest
from sim_nav2_adapter import SimNav2Adapter, ROBOTS, drain_callbacks
from unittest.mock import patch
from zone_coordinator import MissionCoordinator
from service import RequestError


class FakeWorker:
    def __init__(self,name,coordinator):
        self.name=name;self.coordinator=coordinator;self.active=None;self.goal_handle=None
        self.cancel_requested=False;self.source=1.;self.velocity=[0.,0.]
        self.overrides={};self.sent=[]
    def status(self,now):
        r=self.coordinator.robots[self.name]
        return dict(pose=r['pose'],observation_fresh=True,pose_age_s=now-r['received'],
                    odom_velocity=list(self.velocity),**self.overrides)
    def submit(self,command):
        self.sent.append(command)
        if command['kind']=='CANCEL':self.cancel_requested=True
        else:self.active=command['id'];self.goal_handle=object()


class AdapterControlTests(unittest.TestCase):
    def setUp(self):
        a=object.__new__(SimNav2Adapter);self.a=a
        a.mission={}
        for name,y in [('robot_1',.05),('robot_2',-.65)]:
            start,wait,exit,goal=[-.6,y],[-.4,y],[.4,y],[.6,y]
            a.mission[name]=dict(start=start,wait=wait,exit=exit,goal=goal,
                segments=[dict(path=[start,wait]),dict(path=[wait,exit]),dict(path=[exit,goal])])
        a.polygon=[[-.15,-.15],[.15,-.15],[.15,.15],[-.15,.15]];a.radius=.1
        a.coordinator=MissionCoordinator(a.mission,a.polygon)
        for name in ROBOTS:a.coordinator.observation(name,a.mission[name]['start'],1.,10.,0.,0.)
        a.workers={name:FakeWorker(name,a.coordinator) for name in ROBOTS}
        a.closed=False;a.command_index=0;a.started=set();a.events=[];a.coord_event_index=0
        a.last_phases={name:'IDLE' for name in ROBOTS};a.last_lease=0.;a.preflight_ready=False
        a.relay=SimpleNamespace(poll=lambda:None);a.relay_state=dict(received=10.5,blocked=None)
        a.external_actions={};a.request_error_cls=RequestError
        a._spin_once=lambda:10.5;a._evaluate_preflight=lambda now:(True,'test')
        a._sync_events=lambda:None
        self.permits=[];a._heartbeat=lambda permits:self.permits.append(permits)

    def test_callback_batch_drains_multiple_stream_events_without_nodes(self):
        events=list(range(20));processed=[]
        def spin_once(timeout_sec):
            self.assertEqual(timeout_sec,0.)
            if events:processed.append(events.pop(0))
        with patch('sim_nav2_adapter.time.monotonic',return_value=100.):
            self.assertEqual(drain_callbacks(SimpleNamespace(spin_once=spin_once),limit=25),25)
        self.assertEqual(processed,list(range(20)))

    def test_callback_batch_respects_time_budget(self):
        clock=[100.];calls=[]
        def spin_once(timeout_sec):calls.append(True);clock[0]+=.015
        with patch('sim_nav2_adapter.time.monotonic',side_effect=lambda:clock[0]):
            self.assertEqual(drain_callbacks(SimpleNamespace(spin_once=spin_once),budget=.02),2)
        self.assertEqual(len(calls),2)

    def test_halted_robots_still_dispatch_pending_cancel(self):
        a=self.a;a.coordinator.start();a.command_index=len(a.coordinator.commands)
        for name in ROBOTS:
            a.workers[name].active=a.coordinator.robots[name]['pending'];a.workers[name].goal_handle=object()
        a.coordinator.halt('Action failed')
        a.tick()
        for worker in a.workers.values():
            self.assertEqual([command['kind'] for command in worker.sent],['CANCEL'])
        self.assertEqual(a.command_index,len(a.coordinator.commands))
        self.assertEqual(self.permits[-1],{})
        a.tick()
        self.assertTrue(all(len(w.sent)==1 for w in a.workers.values()))

    def test_dispatch_failure_delivers_cancels_in_same_drain(self):
        a=self.a;a.coordinator.start()
        original=a.workers['robot_1'].submit
        def submit(command):
            if command['kind']=='FOLLOW_PATH':raise RuntimeError('server unavailable')
            original(command)
        a.workers['robot_1'].submit=submit
        a._dispatch_commands()
        self.assertIsNotNone(a.coordinator.blocked)
        for worker in a.workers.values():
            self.assertEqual([c['kind'] for c in worker.sent],['CANCEL'])

    def test_cancel_does_not_drop_other_robot_pending_command(self):
        a=self.a;a.coordinator.start();a.cancel('robot_1')
        self.assertEqual([c['kind'] for c in a.workers['robot_1'].sent],['CANCEL'])
        self.assertEqual([c['kind'] for c in a.workers['robot_2'].sent],['FOLLOW_PATH'])

    def test_reset_rejects_pending_acceptance_or_result(self):
        for active,handle in [(7,None),(None,object())]:
            with self.subTest(active=active,handle=handle):
                old=self.a.coordinator;worker=self.a.workers['robot_1']
                worker.active=active;worker.goal_handle=handle
                with self.assertRaises(RequestError):self.a.reset()
                self.assertIs(self.a.coordinator,old)
                self.assertEqual(worker.active,active)
                self.assertIs(worker.goal_handle,handle)

    def test_reset_rejects_stale_moving_or_insufficient_stop_dwell(self):
        for kind in ['stale','moving','recent_stop','running','relay_blocked','external_action']:
            self.setUp();a=self.a;old=a.coordinator
            if kind=='stale':old.robots['robot_1']['received']=8.
            elif kind=='moving':a.workers['robot_1'].velocity=[.02,0.]
            elif kind=='recent_stop':old.robots['robot_1']['stopped_since']=10.4
            elif kind=='running':old.start(['robot_1'])
            elif kind=='relay_blocked':a.relay_state['blocked']='expired'
            else:a.external_actions['follow_path']=True
            with self.subTest(kind=kind),self.assertRaises(RequestError):a.reset()
            self.assertIs(a.coordinator,old)
            if kind=='running':self.assertTrue(all(not worker.sent for worker in a.workers.values()))

    def test_reset_preserves_observation_age_and_monotonic_command_ids(self):
        a=self.a;a.coordinator.sequence=50;old=a.coordinator
        old.robots['robot_2']['received']=10.1
        a.reset()
        self.assertIsNot(a.coordinator,old)
        self.assertEqual(a.coordinator.robots['robot_2']['received'],10.1)
        for name in ROBOTS:
            self.assertEqual(a.coordinator.robots[name]['pose'],a.mission[name]['start'])
            self.assertEqual(a.workers[name].source,1.)
        a.coordinator.start(['robot_1'])
        self.assertGreater(a.coordinator.commands[-1]['id'],50)
        self.assertFalse(a.coordinator.result('robot_1',1,True))


if __name__=='__main__':unittest.main(verbosity=2)

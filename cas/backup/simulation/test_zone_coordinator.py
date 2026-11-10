import copy
import unittest
from zone_coordinator import MissionCoordinator

POLYGON=[[-.15,-.15],[.15,-.15],[.15,.15],[-.15,.15]]
ROUTES={name:dict(wait=[-.4,y],exit=[.4,y],goal=[.8,y]) for name,y in [('robot_1',-.05),('robot_2',.05)]}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        route_data=copy.deepcopy(ROUTES)
        for route in route_data.values():
            route['segments']=[dict(path=[route['wait']]),dict(path=[route['wait'],route['exit']]),dict(path=[route['exit'],route['goal']])]
        self.c=MissionCoordinator(route_data,POLYGON)
        self.now=0.0
        self.c.start()

    def observe(self,positions=None,moving=False):
        self.now+=.1
        for name,r in self.c.robots.items():
            position=(positions or {}).get(name, r['pose'] or ROUTES[name]['wait'])
            self.c.observation(name,position,self.now,self.now,.05 if moving else 0,0)
        self.c.tick(self.now)

    def ready(self):
        for name,r in self.c.robots.items():self.c.result(name,r['pending'],True)
        for _ in range(6):self.observe()

    def test_wait_requires_result_and_new_stop_observations(self):
        for _ in range(6):self.observe()
        self.assertIsNone(self.c.owner)
        self.ready()
        self.assertEqual(self.c.owner,'robot_1')
        self.assertEqual(self.c.queue,['robot_2'])

    def test_exit_success_inside_does_not_release(self):
        self.ready()
        self.observe({'robot_1':[0,0]},moving=True)
        self.c.result('robot_1',self.c.robots['robot_1']['pending'],True)
        for _ in range(6):self.observe({'robot_1':[0,0]})
        self.assertEqual(self.c.owner,'robot_1')

    def test_moving_exit_releases_without_new_goal_or_stop(self):
        self.ready()
        r=self.c.robots['robot_1'];command_id=r['pending']
        path=self.c.commands[-1]['target']
        self.assertEqual(path[-1],ROUTES['robot_1']['goal'])
        self.observe({'robot_1':[0,0]},moving=True)
        before=len(self.c.commands)
        self.observe({'robot_1':[.30,-.05]},moving=True)
        self.assertEqual(r['phase'],'TO_GOAL')
        self.assertEqual(self.c.owner,'robot_2')
        self.assertEqual(r['pending'],command_id)
        self.assertEqual(len(self.c.commands),before+1) # only robot2 gets a new crossing command
        self.observe({'robot_1':[.8,-.05]},moving=True)
        self.c.result('robot_1',command_id,True)
        for _ in range(6):self.observe()
        self.assertEqual(r['phase'],'SPINNING')
        self.c.result('robot_1',r['pending'],True)
        self.assertNotEqual(r['phase'],'DONE')
        for _ in range(6):self.observe()
        self.assertEqual(r['phase'],'DONE')

    def test_backing_out_on_entry_side_does_not_release(self):
        self.ready()
        self.observe({'robot_1':[0,0]},moving=True)
        self.observe({'robot_1':[-.3,-.05]},moving=True)
        self.assertEqual(self.c.owner,'robot_1')

    def test_stale_pose_holds_owner_and_cancels_both(self):
        self.ready()
        self.c.tick(self.now+1.1)
        self.assertIsNotNone(self.c.blocked)
        self.assertEqual(self.c.owner,'robot_1')
        self.assertEqual([c['kind'] for c in self.c.commands[-2:]],['CANCEL','CANCEL'])

    def test_replayed_observation_and_wrong_result_rejected(self):
        self.ready()
        name='robot_1';r=self.c.robots[name]
        self.assertFalse(self.c.observation(name,[0,0],r['source'],self.now+.5,0,0))
        self.assertFalse(self.c.result(name,-1,True))
        self.assertEqual(r['phase'],'CROSSING')

    def test_stop_shorter_than_old_4cm_tolerance_cannot_grant(self):
        for name,r in self.c.robots.items():self.c.result(name,r['pending'],True)
        for _ in range(6):
            self.observe({'robot_1':[-.435,-.05]})  # 3.5cm short: not a valid handoff
        self.assertIsNotNone(self.c.blocked)
        self.assertIsNone(self.c.owner)

    def test_unpermitted_entry_blocks_everything(self):
        self.ready()
        self.observe({'robot_2':[0,0]})
        self.assertIsNotNone(self.c.blocked)
        self.assertEqual(self.c.owner,'robot_1')


if __name__=='__main__':unittest.main(verbosity=2)

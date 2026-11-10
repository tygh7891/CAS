import copy
import unittest
from zone_coordinator import MissionCoordinator

POLYGON=[[-.15,-.15],[.15,-.15],[.15,.15],[-.15,.15]]
ROUTES={name:dict(wait=[-.4,y],exit=[.4,y],goal=[.8,y]) for name,y in [('robot_1',-.05),('robot_2',.05)]}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.c=MissionCoordinator(copy.deepcopy(ROUTES),POLYGON)
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

    def test_confirmed_exit_hands_off_then_completion_requires_stop(self):
        self.ready()
        self.observe({'robot_1':[0,0]},moving=True)
        self.observe({'robot_1':[.4,-.05]},moving=True)
        r=self.c.robots['robot_1']
        self.c.result('robot_1',r['pending'],True)
        for _ in range(6):self.observe()
        self.assertEqual(self.c.owner,'robot_2')
        self.assertEqual(r['phase'],'TO_GOAL')
        self.observe({'robot_1':[.8,-.05]},moving=True)
        self.c.result('robot_1',r['pending'],True)
        for _ in range(6):self.observe()
        self.assertEqual(r['phase'],'SPINNING')
        self.c.result('robot_1',r['pending'],True)
        self.assertNotEqual(r['phase'],'DONE')
        for _ in range(6):self.observe()
        self.assertEqual(r['phase'],'DONE')

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

    def test_unpermitted_entry_blocks_everything(self):
        self.ready()
        self.observe({'robot_2':[0,0]})
        self.assertIsNotNone(self.c.blocked)
        self.assertEqual(self.c.owner,'robot_1')


if __name__=='__main__':unittest.main(verbosity=2)

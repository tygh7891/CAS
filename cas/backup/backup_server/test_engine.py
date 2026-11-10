import json
from pathlib import Path
import unittest
from engine import Coordinator

CONFIG=json.loads(Path(__file__).with_name('scenario.mock.json').read_text())
class FlowTests(unittest.TestCase):
    def test_two_tasks_complete_with_exclusive_zone(self):
        c=Coordinator(CONFIG)
        for _ in range(1000):
            c.tick(0.05)
            inside=[r['id'] for r in c.robots.values() if c.overlaps(r['position'])]
            self.assertLessEqual(len(inside),1)
            if inside:self.assertEqual(inside,[c.owner])
            if c.finished:break
        self.assertTrue(all(r['task_state']=='SUCCEEDED' for r in c.robots.values()))
        self.assertIsNone(c.owner)
        self.assertEqual([r['position'] for r in c.robots.values()],[r['goal'] for r in c.robots.values()])
        events=c.events
        grants=[i for i,e in enumerate(events) if e['event']=='ZONE_GRANTED']
        releases=[i for i,e in enumerate(events) if e['event']=='ZONE_RELEASED']
        self.assertEqual(len(grants),2)
        self.assertLess(releases[0],grants[1])
        self.assertTrue(any(e['phase']=='WAITING_ZONE' and e['robot_id']=='robot_2' for e in events))
    def test_cancellation_in_zone_retains_owner_and_freezes(self):
        c=Coordinator(CONFIG)
        for _ in range(200):
            c.tick(0.05)
            if any(c.overlaps(r['position']) for r in c.robots.values()):break
        owner=c.owner;self.assertIsNotNone(owner)
        positions=[list(r['position']) for r in c.robots.values()]
        c.cancel_all();c.tick(0.05)
        self.assertEqual(c.owner,owner)
        self.assertEqual(positions,[r['position'] for r in c.robots.values()])
        self.assertTrue(all(r['task_state']=='CANCELED' for r in c.robots.values()))
    def test_failure_keeps_lock(self):
        c=Coordinator(CONFIG)
        for _ in range(200):
            c.tick(0.05)
            if c.owner:break
        owner=c.owner;c.fail_all('Injected mock failure')
        self.assertEqual(c.owner,owner)
        self.assertTrue(all(r['task_state']=='FAILED' for r in c.robots.values()))
    def test_refuse_real_mode(self):
        with self.assertRaises(ValueError):Coordinator(dict(CONFIG,mode='real'))
    def test_large_timestep_rejected(self):
        c=Coordinator(CONFIG)
        with self.assertRaises(ValueError):c.tick(1.0)
    def test_contact_counts_as_occupied(self):
        c=Coordinator(CONFIG)
        self.assertTrue(c.overlaps([0.24,0]))
        self.assertFalse(c.overlaps([0.26,0]))

if __name__=='__main__':unittest.main(verbosity=2)

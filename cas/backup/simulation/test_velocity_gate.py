import unittest
from velocity_gate import VelocityGate


class GateTests(unittest.TestCase):
    def setUp(self):self.gate=VelocityGate('test')
    def lease(self,sequence=1,now=1.0,permits=None):
        return self.gate.lease(dict(session='test',sequence=sequence,expires=now+.25,
                                   permits={'robot_1':7} if permits is None else permits),now)
    def test_no_lease_or_wrong_robot_means_zero(self):
        self.gate.velocity('robot_1',.08,.4,1)
        self.assertEqual(self.gate.output('robot_1',1),(0,0))
        self.lease();self.gate.velocity('robot_2',.08,.4,1.01)
        self.assertEqual(self.gate.output('robot_2',1.02),(0,0))
    def test_current_command_and_fresh_velocity_pass_with_caps(self):
        self.lease();self.gate.velocity('robot_1',.3,2,1.01)
        self.assertEqual(self.gate.output('robot_1',1.02),(.08,.4))
    def test_old_velocity_not_reused_on_new_goal(self):
        self.lease();self.gate.velocity('robot_1',.08,.4,1.01)
        self.lease(2,1.02,{'robot_1':8})
        self.assertEqual(self.gate.output('robot_1',1.03),(0,0))
    def test_stale_velocity_stops_even_with_live_lease(self):
        self.lease();self.gate.velocity('robot_1',.08,.4,1.01)
        self.lease(2,1.15)
        self.assertEqual(self.gate.output('robot_1',1.2),(0,0))
    def test_deadman_latches_and_cannot_resume(self):
        self.lease();self.gate.velocity('robot_1',.08,.4,1.01)
        self.assertEqual(self.gate.output('robot_1',1.3),(0,0))
        self.assertFalse(self.lease(2,1.31))
        self.assertIsNotNone(self.gate.blocked)
    def test_delayed_lease_cannot_extend_expired_authority(self):
        self.lease()
        self.assertFalse(self.lease(2,1.3))
        self.assertIsNotNone(self.gate.blocked)
    def test_replay_or_other_session_does_not_refresh(self):
        self.lease()
        self.assertFalse(self.lease(1,1.1))
        self.assertFalse(self.gate.lease(dict(session='other',sequence=2,expires=1.3,permits={}),1.1))
        self.assertEqual(self.gate.deadline,1.25)
    def test_empty_lease_revokes_immediately(self):
        self.lease();self.gate.velocity('robot_1',.08,.4,1.01)
        self.lease(2,1.02,{})
        self.assertEqual(self.gate.output('robot_1',1.03),(0,0))


if __name__=='__main__':unittest.main(verbosity=2)

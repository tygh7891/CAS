import unittest
from lease_pump import LeasePump
from velocity_gate import VelocityGate


class PumpTests(unittest.TestCase):
    def test_sender_cannot_renew_when_main_loop_stalls(self):
        pump=LeasePump('test');gate=VelocityGate('test')
        pump.touch({'robot_1':7},1)
        self.assertTrue(gate.lease(pump.packet(1.01),1.01))
        self.assertIsNone(pump.packet(1.2))
        self.assertEqual(gate.output('robot_1',1.3),(0,0))
        self.assertIsNotNone(gate.blocked)

    def test_new_packets_increase_sequence_and_copy_permits(self):
        pump=LeasePump('test');permits={'robot_1':7};pump.touch(permits,1)
        permits['robot_1']=8
        first,second=pump.packet(1.01),pump.packet(1.02)
        self.assertEqual(first['permits']['robot_1'],7)
        self.assertGreater(second['sequence'],first['sequence'])
        pump.touch({},1.03)
        self.assertEqual(pump.packet(1.04)['permits'],{})


if __name__=='__main__':unittest.main()

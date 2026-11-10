"""Exercise actual proposed callbacks with fake time and motors; no ROS/network."""
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

source = Path(__file__).with_name('bringup.proposed.py').read_text()
tree = ast.parse(source)
methods = [m for c in tree.body if isinstance(c, ast.ClassDef) and c.name == 'Pinky' for m in c.body if isinstance(m, ast.FunctionDef) and m.name in ('twist_callback', 'check_cmd_timeout')]
clock = SimpleNamespace(monotonic=Mock(return_value=100.0))
ns = dict(math=math, time=clock, Twist=object)
exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), '<proposed callbacks>', 'exec'), ns)

class TimeoutTests(unittest.TestCase):
    def setUp(self):
        clock.monotonic.return_value = 100.0
        self.node = SimpleNamespace(is_initialized=True, cmd_watchdog_armed=False,
            last_cmd_monotonic=None, cmd_vel_timeout=0.5, wheel_radius=0.027,
            wheel_separation=0.0961, driver=Mock(), get_logger=Mock(return_value=Mock()))
        self.node.driver.set_double_rpm.return_value = True
        self.node.check_cmd_timeout = lambda: ns['check_cmd_timeout'](self.node)
    def command(self, v=0.02, w=0.0):
        ns['twist_callback'](self.node, SimpleNamespace(linear=SimpleNamespace(x=v), angular=SimpleNamespace(z=w)))
    def test_no_command_no_motor_write(self):
        self.node.check_cmd_timeout()
        self.node.driver.set_double_rpm.assert_not_called()
    def test_timeout_boundary_and_single_stop(self):
        self.command()
        self.node.driver.set_double_rpm.reset_mock()
        clock.monotonic.return_value = 100.49
        self.node.check_cmd_timeout()
        self.node.driver.set_double_rpm.assert_not_called()
        clock.monotonic.return_value = 100.5
        self.node.check_cmd_timeout()
        self.node.driver.set_double_rpm.assert_called_once_with(0, 0)
        self.node.check_cmd_timeout()
        self.assertEqual(self.node.driver.set_double_rpm.call_count, 1)
    def test_new_command_refreshes_deadline(self):
        self.command()
        clock.monotonic.return_value = 100.4
        self.command()
        self.node.driver.set_double_rpm.reset_mock()
        clock.monotonic.return_value = 100.7
        self.node.check_cmd_timeout()
        self.node.driver.set_double_rpm.assert_not_called()
    def test_failed_stop_retries(self):
        self.command()
        clock.monotonic.return_value = 101.0
        self.node.driver.set_double_rpm.side_effect = [False, True]
        self.node.check_cmd_timeout()
        self.assertTrue(self.node.cmd_watchdog_armed)
        self.node.check_cmd_timeout()
        self.assertFalse(self.node.cmd_watchdog_armed)
    def test_invalid_command_stops(self):
        for v, w in [(float('nan'), 0), (0, float('inf'))]:
            self.node.driver.set_double_rpm.reset_mock()
            self.command(v, w)
            self.node.driver.set_double_rpm.assert_called_once_with(0, 0)
    def test_new_command_after_timeout(self):
        self.command()
        clock.monotonic.return_value = 101.0
        self.node.check_cmd_timeout()
        self.command()
        self.assertTrue(self.node.cmd_watchdog_armed)
        self.assertNotEqual(self.node.driver.set_double_rpm.call_args.args, (0, 0))
    def test_uninitialized_no_write(self):
        self.node.is_initialized = False
        self.node.cmd_watchdog_armed = True
        self.node.check_cmd_timeout()
        self.node.driver.set_double_rpm.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)

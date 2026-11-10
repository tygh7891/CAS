"""Check constructor-sensitive Nav2 configuration without starting ROS nodes."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('preview', Path(__file__).with_name('nav2_preview.launch.py'))
PREVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREVIEW)


class PreviewConfiguration(unittest.TestCase):
    def test_costmap_integer_dimensions_and_robot_isolation(self):
        folder = Path.home() / 'CAS_sim_ws/generated_map'
        for robot in ['robot_1', 'robot_2']:
            data = PREVIEW.configuration(folder, robot)
            local = data[f'/{robot}/local_costmap/local_costmap']['ros__parameters']
            for key in ['width', 'height']:
                self.assertIs(type(local[key]), int, key)
            self.assertEqual(local['robot_base_frame'], f'{robot}/base_footprint')
            self.assertEqual(local['obstacle_layer']['scan']['topic'], f'/{robot}/scan')
            self.assertIn('keepout_filter', local['filters'])


if __name__ == '__main__':
    unittest.main()

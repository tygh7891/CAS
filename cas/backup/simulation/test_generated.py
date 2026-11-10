"""Static validation only; no ROS node or simulator startup."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import yaml
from prepare import bridge_config,ROBOTS,WORLD_NAME

ROOT=Path.home()/'CAS_sim_ws/generated'
class GeneratedTests(unittest.TestCase):
    def test_world_contains_exactly_two_robots(self):
        world=ET.parse(ROOT/'connection_test.sdf').getroot().find('world')
        self.assertEqual(world.get('name'),WORLD_NAME)
        self.assertEqual([m.get('name') for m in world.findall('model') if m.get('name') in ROBOTS],list(ROBOTS))
        poses=[m.findtext('pose') for m in world.findall('model') if m.get('name') in ROBOTS]
        self.assertEqual(len(set(poses)),2)
    def test_urdf_frames_and_joints_are_disjoint(self):
        sets=[]
        for robot in ROBOTS:
            root=ET.parse(ROOT/(robot+'.urdf')).getroot()
            names={e.get('name') for e in root if e.tag in ('link','joint')}
            self.assertTrue(all(name.startswith(robot+'/') for name in names));sets.append(names)
            for joint in root.findall('joint'):
                for tag in ['parent','child']:self.assertIn(joint.find(tag).get('link'),names)
            for e in root.findall('.//gazebo'):
                if e.get('reference'):self.assertIn(e.get('reference'),names)
        self.assertFalse(sets[0]&sets[1])
    def test_gazebo_lidar_and_drive_topics_are_unique(self):
        for robot in ROBOTS:
            model=next(m for m in ET.parse(ROOT/'connection_test.sdf').getroot().findall('.//model') if m.get('name')==robot)
            lidar=model.find('.//sensor')
            self.assertIsNotNone(lidar);self.assertEqual(lidar.findtext('topic'),'/'+robot+'/scan')
            drive=next(p for p in model.findall('plugin') if 'diff-drive' in p.get('filename',''))
            self.assertEqual(drive.findtext('topic'),'/'+robot+'/cmd_vel')
            self.assertEqual(drive.findtext('tf_topic'),'/'+robot+'/tf')
            self.assertEqual(drive.findtext('frame_id'),robot+'/odom')
    def test_bridge_is_directional_and_has_single_clock(self):
        config=yaml.safe_load((ROOT/'bridge.yaml').read_text())
        self.assertEqual(config,bridge_config())
        self.assertEqual(sum(x['ros_topic_name']=='/clock' for x in config),1)
        self.assertEqual(len({x['ros_topic_name'] for x in config}),len(config))
        commands=[x for x in config if x['direction']=='ROS_TO_GZ']
        self.assertEqual([x['ros_topic_name'] for x in commands],['/robot_1/cmd_vel','/robot_2/cmd_vel'])

if __name__=='__main__':unittest.main(verbosity=2)

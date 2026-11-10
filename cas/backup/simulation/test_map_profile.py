"""Geometry/policy tests; does not start Gazebo, ROS, or physical robots."""
from pathlib import Path
import json
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
import yaml
from prepare_map import rectangles,arrays,RADIUS,GOAL_CLEARANCE,GOAL_WALL_CLEARANCE

ROOT=Path.home()/'CAS_sim_ws/generated_map'
REPO=Path(__file__).resolve().parents[3]

class MapProfileTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((ROOT/'map_profile_report.json').read_text())
        self.spec,self.occupied,self.allowed=arrays(self.report['source_map'],self.report['source_allowed_mask'])
        self.candidates=json.loads((ROOT/'scenario.candidates.json').read_text())
    def test_exact_rectangle_compression_without_dilation(self):
        rebuilt=np.zeros_like(self.occupied,dtype=int)
        for x0,x1,y0,y1 in rectangles(self.occupied):rebuilt[y0:y1,x0:x1]+=1
        self.assertTrue(np.array_equal(rebuilt,self.occupied.astype(int)))
    def test_physical_collisions_only_match_occupied_pixels(self):
        world=ET.parse(ROOT/'connection_test.sdf').getroot().find('world')
        wall=next(m for m in world.findall('model') if m.get('name')=='map_occupied_cells')
        self.assertEqual(len(wall.findall('.//collision')),len(rectangles(self.occupied)))
        area=sum(np.prod([float(v) for v in c.findtext('geometry/box/size').split()][:2]) for c in wall.findall('.//collision'))
        self.assertAlmostEqual(area,int(self.occupied.sum())*self.spec.resolution**2)
        for name in ['allowed_lane_visual_only','shared_zone_candidate_visual_only']:
            model=next(m for m in world.findall('model') if m.get('name')==name)
            self.assertFalse(model.findall('.//collision'))
    def test_keepout_white_allowed_black_blocked(self):
        draft=np.array(Image.open(ROOT/'nav2_keepout_draft.pgm'))
        self.assertTrue(np.all(draft[self.allowed]==255));self.assertTrue(np.all(draft[~self.allowed]==0))
        meta=yaml.safe_load((ROOT/'nav2_keepout_draft.yaml').read_text())
        self.assertEqual(meta['negate'],0);self.assertEqual(meta['origin'],list(self.spec.origin))
        self.assertFalse(self.report['nav2_keepout_applied'])
    def test_candidates_are_unapproved_and_footprint_clear(self):
        self.assertIs(self.candidates['coordinates_confirmed'],False)
        self.assertEqual(self.candidates['map_sha256'],self.spec.digest)
        clearance=distance_transform_edt(np.pad(self.allowed,1))[1:-1,1:-1]*self.spec.resolution
        wall_clearance=distance_transform_edt(~self.occupied)*self.spec.resolution
        center=np.array(self.candidates['shared_zone']['center'])
        for name,point in self.candidates['points'].items():
            start=np.array([point['x'],point['y']])
            if name in ('A','B'):
                col,row=point['pixel']
                self.assertGreaterEqual(clearance[row,col],GOAL_CLEARANCE)
                self.assertGreaterEqual(wall_clearance[row,col],GOAL_WALL_CLEARANCE)
            for t in np.linspace(0,1,2001):
                u,v=self.spec.world_to_image(*(start+(center-start)*t));col,row=int(u),int(v)
                self.assertGreaterEqual(clearance[row,col],RADIUS)
    def test_waiting_footprint_outside_candidate_zone(self):
        center=np.array(self.candidates['shared_zone']['center']);yaw=self.spec.origin[2]
        import math
        rotate=np.array([[math.cos(yaw),math.sin(yaw)],[-math.sin(yaw),math.cos(yaw)]])
        for point in self.candidates['waiting'].values():
            p=rotate@(np.array([point['x'],point['y']])-center)
            distance=math.hypot(max(abs(p[0])-.15,0),max(abs(p[1])-.15,0))
            self.assertGreater(distance,RADIUS+.02)
    def test_starts_on_left_short_edge_work_on_right(self):
        points=self.candidates['points']
        pixels={name:self.spec.world_to_image(p['x'],p['y']) for name,p in points.items()}
        for name in ['1','2']:
            self.assertLess(pixels[name][0],self.spec.width/2)
        for name in ['A','B']:
            self.assertGreater(pixels[name][0],self.spec.width/2)
        self.assertLess(pixels['1'][1],pixels['2'][1])
        self.assertLess(pixels['A'][1],pixels['B'][1])
        world=ET.parse(ROOT/'connection_test.sdf').getroot().find('world')
        import math
        for robot,start,target in [('robot_1','1','B'),('robot_2','2','A')]:
            pose=list(map(float,world.find(f"model[@name='{robot}']/pose").text.split()))
            a,b=points[start],points[target]
            self.assertAlmostEqual(pose[5],math.atan2(b['y']-a['y'],b['x']-a['x']))

    def test_world_robot_spawn_matches_candidate_starts(self):
        world=ET.parse(ROOT/'connection_test.sdf').getroot().find('world')
        for name,label in [('robot_1','1'),('robot_2','2')]:
            model=next(m for m in world.findall('model') if m.get('name')==name)
            x,y,*_=map(float,model.findtext('pose').split())
            self.assertAlmostEqual(x,self.candidates['points'][label]['x']);self.assertAlmostEqual(y,self.candidates['points'][label]['y'])

if __name__=='__main__':unittest.main(verbosity=2)

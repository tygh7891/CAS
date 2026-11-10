import json
import math
from pathlib import Path
import tempfile
import unittest
import yaml
from map_geometry import load_map,review_maps
from service import AppService,RequestError

class MapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'base.pgm').write_bytes(b'P5\n# sample\n2 3\n255\n'+bytes([0,254,205,254,254,0]))
        self.data=dict(image='base.pgm',resolution=.5,origin=[10,20,0],negate=0,occupied_thresh=.65,free_thresh=.196)
        self.path=self.root/'base.yaml';self.write()
    def write(self):self.path.write_text(yaml.safe_dump(self.data))
    def tearDown(self):self.tmp.cleanup()
    def test_pixel_centers_and_y_flip(self):
        m=load_map(self.path)
        self.assertEqual(m.pixel_center(0,0),(10.25,21.25))
        self.assertEqual(m.pixel_center(1,2),(10.75,20.25))
        self.assertEqual(m.image_to_world(0,3),(10,20))
    def test_round_trip_with_rotated_origin(self):
        self.data['origin']=[10,20,math.pi/2];self.write();m=load_map(self.path)
        x,y=m.pixel_center(0,0);self.assertAlmostEqual(x,8.75);self.assertAlmostEqual(y,20.25)
        for u,v in [(0,0),(2,3),(.5,.5),(1.5,2.5)]:
            actual=m.world_to_image(*m.image_to_world(u,v))
            self.assertAlmostEqual(actual[0],u);self.assertAlmostEqual(actual[1],v)
    def test_mask_alignment_required(self):
        other=self.root/'mask.yaml';other.write_text(yaml.safe_dump(dict(self.data,origin=[11,20,0])))
        with self.assertRaises(ValueError):review_maps(self.path,other)
    def test_invalid_resolution_and_pixel_rejected(self):
        self.data['resolution']=float('nan');self.write()
        with self.assertRaises(ValueError):load_map(self.path)
        self.data['resolution']=.5;self.write()
        with self.assertRaises(ValueError):load_map(self.path).pixel_center(2,0)
    def test_review_locks_all_commands_on_server(self):
        review=review_maps(self.path,self.path);service=AppService(map_review=review)
        try:
            state=service.snapshot();self.assertTrue(state['commands_locked']);self.assertEqual(state['mode'],'MAP_REVIEW')
            for path,extra in [('/api/v1/tasks',dict(mission='scenario')),('/api/v1/cancel',dict(target='all')),('/api/v1/reset',dict(confirm=True))]:
                with self.assertRaises(RequestError) as cm:
                    service.command(path,dict(request_id=path,session_id=service.session,**extra))
                self.assertEqual(cm.exception.status,409)
            self.assertFalse(service.snapshot()['active'])
        finally:service.close()
    def test_source_files_not_modified(self):
        before={p:p.read_bytes() for p in self.root.iterdir()};review_maps(self.path,self.path)
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.iterdir()})

if __name__=='__main__':unittest.main(verbosity=2)

import unittest
import numpy as np
from path_geometry import audit


class Spec:
    resolution = .01
    def world_to_image(self, x, y):
        return x/.01, y/.01


class PathGeometryTests(unittest.TestCase):
    def test_whole_segments_checked_between_sparse_vertices(self):
        allowed = np.ones((100,100), dtype=bool)
        allowed[:,49:51] = False
        result = audit([(.2,.5),(.8,.5)], Spec(), allowed, [[.4,.4],[.6,.4],[.6,.6],[.4,.6]], .10)
        self.assertFalse(result['center_in_allowed_lane'])
        self.assertFalse(result['footprint_clear'])
        self.assertTrue(result['shared_zone_crossed'])

    def test_center_clear_but_body_touches_blocked_region(self):
        allowed = np.ones((100,100), dtype=bool)
        allowed[:45] = False
        result = audit([(.2,.5),(.8,.5)], Spec(), allowed, [[.4,.4],[.6,.4],[.6,.6],[.4,.6]], .10)
        self.assertTrue(result['center_in_allowed_lane'])
        self.assertFalse(result['footprint_clear'])

    def test_exact_cell_edge_distance_preserves_required_margin(self):
        allowed = np.ones((100,100), dtype=bool)
        allowed[:40] = False  # blocked region ends exactly at y=.40
        polygon = [[.4,.4],[.6,.4],[.6,.6],[.4,.6]]
        safe = audit([(.3,.511),(.7,.511)], Spec(), allowed, polygon, .10)
        self.assertAlmostEqual(safe['min_sample_clearance_m'], .111)
        self.assertTrue(safe['footprint_clear'])
        touching = audit([(.3,.50),(.7,.50)], Spec(), allowed, polygon, .10)
        self.assertFalse(touching['footprint_clear'])

    def test_safe_route_and_zone_bypass_are_distinguished(self):
        allowed = np.ones((100,100), dtype=bool)
        zone = [[.4,.4],[.6,.4],[.6,.6],[.4,.6]]
        result = audit([(.2,.5),(.8,.5)], Spec(), allowed, zone, .10)
        self.assertTrue(result['footprint_clear'])
        self.assertTrue(result['shared_zone_crossed'])
        bypass = audit([(.2,.2),(.8,.2)], Spec(), allowed, zone, .10)
        self.assertTrue(bypass['footprint_clear'])
        self.assertFalse(bypass['shared_zone_crossed'])


if __name__ == '__main__':
    unittest.main()

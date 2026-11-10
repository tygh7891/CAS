import unittest
from mission_routes import routes, zone_distance


class RouteTests(unittest.TestCase):
    def test_slices_preserve_the_entire_verified_route(self):
        points={label:dict(x=x,y=y) for label,x,y in [('1',-1,.5),('2',-1,-.5),('A',1,.5),('B',1,-.5)]}
        scenario=dict(points=points,robot_radius_with_margin_m=.1,
                      shared_zone=dict(polygon=[[-.15,-.15],[.15,-.15],[.15,.15],[-.15,.15]]))
        reference={name:[[x/100,sign*x/200] for x in range(-100,101)] for name,sign in [('robot_1',-1),('robot_2',1)]}
        for name,route in routes(scenario,reference).items():
            a,b,c=route['segments']
            self.assertEqual(a['path']+b['path'][1:]+c['path'][1:],reference[name])
            self.assertEqual(a['path'][-1],b['path'][0])
            self.assertEqual(b['path'][-1],c['path'][0])
            for key in ['wait','exit']:
                self.assertGreaterEqual(zone_distance(route[key],scenario['shared_zone']['polygon']),.18)
            self.assertTrue(b['requires_permission'])
            self.assertFalse(a['requires_permission'])
            self.assertFalse(c['requires_permission'])


if __name__=='__main__':unittest.main()

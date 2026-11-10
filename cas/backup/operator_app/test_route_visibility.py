import copy
import unittest
from map_view import visible_routes


class RouteVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.state=dict(mode='SIM_NAV2',started=[],layout=dict(routes={'robot_1':[[[0,0],[1,1]]],'robot_2':[[[0,1],[1,0]]]}),
                        simulation=dict(robots=[dict(id='robot_1',task_state='IDLE'),dict(id='robot_2',task_state='IDLE')]))
    def test_unrequested_cached_paths_are_hidden(self):
        before=copy.deepcopy(self.state)
        self.assertEqual(visible_routes(self.state),{})
        self.assertEqual(self.state,before)
    def test_only_requested_robot_path_is_visible(self):
        self.state['started']=['robot_1']
        self.state['simulation']['robots'][0]['task_state']='RUNNING'
        self.assertEqual(set(visible_routes(self.state)),{'robot_1'})
    def test_terminal_paths_are_hidden(self):
        self.state['started']=['robot_1','robot_2']
        for terminal in ['SUCCEEDED','FAILED','CANCELED']:
            self.state['simulation']['robots'][0]['task_state']=terminal
            self.assertEqual(visible_routes(self.state),{})
    def test_running_without_current_session_assignment_is_hidden(self):
        self.state['simulation']['robots'][0]['task_state']='RUNNING'
        self.assertEqual(visible_routes(self.state),{})
    def test_other_modes_do_not_show_navigation_routes(self):
        self.state['mode']='MAP_REVIEW'
        self.state['started']=['robot_1']
        self.state['simulation']['robots'][0]['task_state']='RUNNING'
        self.assertEqual(visible_routes(self.state),{})


if __name__=='__main__':unittest.main()

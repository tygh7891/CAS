"""A5 application and real loopback HTTP tests. No ROS or robot connections."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from service import AppService,RequestError,create_http

class ServiceTests(unittest.TestCase):
    def setUp(self):self.s=AppService()
    def tearDown(self):self.s.close()
    def command(self,path='/api/v1/tasks',**extra):
        data=dict(request_id='request-'+str(len(self.s.cache)),session_id=self.s.session,**extra)
        return self.s.command(path,data)
    def finish(self):
        for _ in range(500):
            self.s.tick()
            if not self.s.snapshot()['active']:return
        self.fail('Did not finish')
    def test_idle_until_operator_requests(self):
        self.s.tick()
        self.assertFalse(self.s.snapshot()['active'])
        self.assertTrue(all(r['task_state']=='IDLE' for r in self.s.snapshot()['simulation']['robots']))
    def test_full_scenario_and_exclusive_zone(self):
        self.command(mission='scenario')
        for _ in range(300):
            self.s.tick();s=self.s.snapshot()
            self.assertLessEqual(len(s['zone']['occupants']),1)
            if s['zone']['occupants']:self.assertEqual(s['zone']['occupants'],[s['zone']['owner']])
            if not s['active']:break
        self.assertTrue(all(r['task_state']=='SUCCEEDED' and r['stopped_confirmed'] for r in s['simulation']['robots']))
    def test_individual_missions_can_start_separately(self):
        self.command(mission='work_B');self.finish()
        self.assertEqual(self.s.snapshot()['simulation']['robots'][1]['task_state'],'IDLE')
        self.command(mission='work_A');self.finish()
        self.assertTrue(all(r['task_state']=='SUCCEEDED' for r in self.s.snapshot()['simulation']['robots']))
    def test_request_replay_is_idempotent(self):
        data=dict(request_id='same',session_id=self.s.session,mission='scenario')
        self.s.command('/api/v1/tasks',data);count=len(self.s.events)
        self.assertTrue(self.s.command('/api/v1/tasks',data)['replayed'])
        self.assertEqual(len(self.s.events),count)
        with self.assertRaises(RequestError):self.s.command('/api/v1/tasks',dict(data,mission='work_A'))
    def test_atomic_duplicate_scenario_rejected(self):
        self.command(mission='work_B')
        with self.assertRaises(RequestError):self.command(mission='scenario')
        self.assertEqual(self.s.snapshot()['started'],['robot_1'])
    def test_reset_requires_no_active_task_and_confirmation(self):
        self.command(mission='scenario')
        with self.assertRaises(RequestError):self.command('/api/v1/reset',confirm=True)
        self.command('/api/v1/cancel',target='all')
        with self.assertRaises(RequestError):self.command('/api/v1/reset',confirm=False)
        old=self.s.session;self.command('/api/v1/reset',confirm=True)
        self.assertNotEqual(old,self.s.session)
        self.assertEqual(self.s.snapshot()['started'],[])
    def test_real_mode_and_old_session_rejected(self):
        with self.assertRaises(RequestError):self.command(mission='scenario',mode='REAL_NAV2')
        with self.assertRaises(RequestError):self.s.command('/api/v1/tasks',dict(request_id='old',session_id='obsolete',mission='scenario'))
        self.assertFalse(self.s.snapshot()['active'])
    def test_occupied_cancel_preserves_owner(self):
        self.command(mission='scenario')
        for _ in range(100):
            self.s.tick()
            if 'robot_1' in self.s.snapshot()['zone']['occupants']:break
        self.command('/api/v1/cancel',target='robot_1')
        self.assertEqual(self.s.snapshot()['zone']['owner'],'robot_1')
        self.assertIsNotNone(self.s.snapshot()['zone']['blocked_reason'])
    def test_close_cancels_mock_tasks(self):
        self.command(mission='scenario');self.s.close()
        self.assertFalse(self.s.snapshot()['active'])

class HttpTests(unittest.TestCase):
    def test_http_auth_json_command_and_state(self):
        service=AppService();server,token=create_http(service,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        def call(path,body=None,valid=True):
            headers={'X-CAS-Token':token if valid else 'wrong'}
            if body is not None:headers['Content-Type']='application/json'
            req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
            with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:call('/api/v1/state',valid=False)
            self.assertEqual(cm.exception.code,403)
            state=call('/api/v1/state')
            result=call('/api/v1/tasks',dict(request_id='http-test',session_id=state['session_id'],mission='scenario'))
            self.assertEqual(result['status'],'ACCEPTED')
            self.assertTrue(call('/api/v1/state')['active'])
            with self.assertRaises(urllib.error.HTTPError) as cm:call('/api/v1/tasks',[])
            self.assertEqual(cm.exception.code,400)
        finally:
            server.shutdown();server.server_close();thread.join();service.close()

if __name__=='__main__':unittest.main(verbosity=2)

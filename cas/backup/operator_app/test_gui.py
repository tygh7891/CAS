"""Offscreen Qt/HTTP integration. Does not open the user's desktop or connect ROS."""
import os
import copy
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import threading
import time
import unittest
from PyQt5.QtWidgets import QApplication
from gui import Dashboard
from service import AppService,create_http

class GuiTests(unittest.TestCase):
    def test_operator_request_status_completion_and_disconnect(self):
        app=QApplication.instance() or QApplication([])
        service=AppService();server,token=create_http(service,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        window=Dashboard(f'http://127.0.0.1:{server.server_port}',token)
        window.show()
        def pump_until(predicate,timeout=4):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                app.processEvents();time.sleep(0.01)
                if predicate():return
            self.fail('GUI/HTTP state did not arrive')
        try:
            pump_until(lambda:window.connected)
            self.assertTrue(window.task_buttons['scenario'].isEnabled())
            ready=copy.deepcopy(window.state)
            missing=copy.deepcopy(ready)
            missing.update(preflight_ready=False,commands_locked=True,
                           preflight_reason='robot_1 위치 수신 대기 중 (Lookup would require extrapolation into the future)')
            missing['simulation']['robots'][0].update(position=None,pose_valid=False,pose_age_s=None,
                                                       connection='SIM_NAV2_WAIT',stopped_confirmed=False)
            height=window.notice.height()
            window.render(missing);app.processEvents()
            self.assertEqual(window.notice.height(),height)
            self.assertNotIn('Lookup',window.notice.text())
            self.assertIn('Lookup',window.notice.toolTip())
            self.assertIn('위치: 미수신',window.cards['robot_1'].text())
            self.assertIn('정지: 미확인',window.cards['robot_1'].text())
            window.render(ready);app.processEvents()
            window.task_buttons['scenario'].click()
            pump_until(lambda:service.snapshot()['active'])
            # Fast forward mock state to waiting/crossing then render real HTTP snapshot.
            for _ in range(45):service.tick()
            pump_until(lambda:window.state['zone']['owner']=='robot_1')
            self.assertIn('대기',window.cards['robot_2'].text())
            self.assertFalse(window.task_buttons['scenario'].isEnabled())
            path=Path('/tmp/cas_a5_crossing.png');self.assertTrue(window.grab().save(str(path)))
            for _ in range(250):service.tick()
            pump_until(lambda:all(r['task_state']=='SUCCEEDED' for r in window.state['simulation']['robots']))
            self.assertIn('완료',window.cards['robot_1'].text())
            self.assertTrue(window.reset.isEnabled())
            # Observe server loss; controls must disable while last map remains visible.
            server.shutdown();server.server_close();thread.join()
            pump_until(lambda:not window.connected)
            self.assertFalse(window.task_buttons['scenario'].isEnabled())
            self.assertFalse(window.cancel_all.isEnabled())
            print('Screenshot:',path)
        finally:
            window.timer.stop();window.close();app.processEvents()
            if thread.is_alive():server.shutdown();server.server_close();thread.join()
            service.close()

    def test_sim_nav2_gui_renders_real_map_routes_and_dispatches_mode(self):
        app=QApplication.instance() or QApplication([])
        folder=Path.home()/'CAS_sim_ws/generated_map'
        if not (folder/'scenario.candidates.json').exists():self.skipTest('generated_map not present')
        from map_geometry import review_maps
        import json
        report=json.loads((folder/'map_profile_report.json').read_text())
        review=review_maps(report['source_map'],report['source_allowed_mask'],'allowed',folder/'scenario.candidates.json')
        class FakeSimAdapter:
            def __init__(self):
                self.started=set();self.events=[];self.active=False
            def start(self,ids,session):
                self.started.update(ids);self.active=True
                for r in ids:self.events.append(dict(event='TASK_ACCEPTED',robot_id=r,reason='SIM_NAV2',phase='TO_WAIT',owner=None))
            def tick(self,dt):pass
            def cancel(self,target):self.active=False
            def reset(self):self.started.clear()
            def snapshot(self):
                return dict(mode='SIM_NAV2',map_review=review,commands_locked=False,preflight_ready=True,
                            preflight_reason='Gazebo · Nav2 · Relay 프리플라이트 정상',available_modes=['SIM_NAV2'],locked_modes=['REAL_NAV2'],
                            active=self.active,zone=dict(id='z',owner='robot_2' if self.active else None,waiting=['robot_1'] if self.active else [],blocked_reason=None,occupants=['robot_2'] if self.active else []),
                            simulation=dict(robots=[dict(id='robot_1',destination='B',task_state='RUNNING' if self.active else 'IDLE',
                                                         phase='WAITING_ZONE' if self.active else 'IDLE',position=[-0.046,-0.195],yaw=-0.5,
                                                         pose_age_s=0.01,connection='SIM_NAV2_OK',battery_percent=None,stopped_confirmed=True),
                                                    dict(id='robot_2',destination='A',task_state='RUNNING' if self.active else 'IDLE',
                                                         phase='CROSSING' if self.active else 'IDLE',position=[0.227,-0.346],yaw=0.6,
                                                         pose_age_s=0.01,connection='SIM_NAV2_OK',battery_percent=None,stopped_confirmed=False)]),
                            layout=dict(zone=dict(id='z',xmin=0.077,xmax=0.377,ymin=-0.496,ymax=-0.196),robots=[],
                                        routes={'robot_1':[[[-0.553,0.084],[-0.046,-0.195]],[[-0.046,-0.195],[0.847,-0.696]]],
                                                'robot_2':[[[-0.513,-0.826],[-0.043,-0.521]],[[-0.043,-0.521],[0.807,0.034]]]}),
                            started=sorted(self.started))
            def close(self):pass
        service=AppService(adapter=FakeSimAdapter());server,token=create_http(service,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        window=Dashboard(f'http://127.0.0.1:{server.server_port}',token)
        window.show()
        def pump_until(predicate,timeout=4):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                app.processEvents();time.sleep(0.01)
                if predicate():return
            self.fail('SIM_NAV2 GUI state did not arrive')
        try:
            pump_until(lambda:window.connected and window.state and window.state.get('mode')=='SIM_NAV2')
            self.assertTrue(window.task_buttons['scenario'].isEnabled())
            window.task_buttons['scenario'].click()
            pump_until(lambda:service.snapshot()['active'])
            pump_until(lambda:window.state['zone']['owner']=='robot_2')
            self.assertIn('Gazebo',window.cards['robot_1'].text())
            path=Path('/tmp/cas_b5_sim_nav2_gui.png');self.assertTrue(window.grab().save(str(path)))
        finally:
            window.timer.stop();window.close();app.processEvents()
            if thread.is_alive():server.shutdown();server.server_close();thread.join()
            service.close()

if __name__=='__main__':unittest.main(verbosity=2)

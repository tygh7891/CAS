"""Offscreen Qt/HTTP integration. Does not open the user's desktop or connect ROS."""
import os
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

if __name__=='__main__':unittest.main(verbosity=2)

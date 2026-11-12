"""Physical GUI smoke test with injected telemetry; no ROS nodes or HTTP requests."""
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from gui import Dashboard
from service import AppService, RequestError
from real_nav2_adapter import RealNav2Adapter, ROBOTS


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_physical_map_cards_and_home_button(self):
        adapter = RealNav2Adapter(Path(__file__).with_name('real_config.json'), RequestError, start_workers=False)
        for n in ROBOTS:
            adapter.telemetry[n] = dict(pose=adapter.points[n]['start'], velocity=[0,0], ready=True, busy=None)
            adapter.received[n] = time.monotonic()
        service = AppService(adapter=adapter)
        with patch.object(Dashboard, 'poll'):
            window = Dashboard('http://127.0.0.1:1', 'test')
            window.timer.stop()
            window.render(service.snapshot())
            self.assertEqual(window.reset.text(), '출발점 복귀')
            self.assertTrue(window.task_buttons['scenario'].isEnabled())
            self.assertFalse(window.mask_toggle.isChecked())
            self.assertTrue(all('실물 Nav2 정상' in label.text() for label in window.cards.values()))
            calls=[]
            window.post=lambda path, fields:calls.append((path,fields))
            window.reset_session()
            self.assertEqual(calls,[('/api/v1/return-home',{})])
            window.show()
            self.app.processEvents()
            window.grab().save('/tmp/cas_real_release.png')
            state=service.snapshot()
            state['live_map']=dict(width=2,height=2,resolution=.01,origin=[-1.798,-1.325,0],data=[0,100,-1,50])
            window.render(state)
            self.assertEqual(window.map.spec.width,2)
            self.assertEqual(window.map.image.pixelColor(0,1).lightness(),254)
            self.assertEqual(window.map.image.pixelColor(1,1).lightness(),0)
            self.assertEqual(window.map.image.pixelColor(0,0).lightness(),205)
            window.close()
        service.close()


if __name__ == '__main__':
    unittest.main()

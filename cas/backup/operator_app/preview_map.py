"""Offscreen rendering and read-only coordinate-click verification; no desktop operation."""
import argparse
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import threading
import time
from PyQt5.QtCore import Qt,QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui import Dashboard
from map_geometry import review_maps
from service import AppService,create_http

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--map',required=True);parser.add_argument('--mask');args=parser.parse_args()
    review=review_maps(args.map,args.mask);app=QApplication([])
    service=AppService(map_review=review);server,token=create_http(service,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    window=Dashboard(f'http://127.0.0.1:{server.server_port}',token);window.show()
    try:
        end=time.monotonic()+4
        while time.monotonic()<end and (window.state is None or not hasattr(window.map,'spec')):
            app.processEvents();time.sleep(.01)
        assert window.connected and window.map.spec is not None
        assert not any(b.isEnabled() for b in window.task_buttons.values())
        rect=window.map.image_rect()
        QTest.mouseClick(window.map,Qt.LeftButton,pos=QPoint(int(rect.center().x()),int(rect.center().y())))
        assert window.map.selected is not None and 'map:' in window.point_info.text()
        app.processEvents();window.grab().save('/tmp/cas_b1_base.png')
        if args.mask:
            window.mask_toggle.setChecked(True);app.processEvents()
            assert window.map.show_mask
            window.grab().save('/tmp/cas_b1_overlay.png')
        print('PASS: received map display, read-only coordinate selection, mask layer, GUI command lock')
        print('Point:',window.point_info.text())
    finally:
        window.timer.stop();window.close();server.shutdown();server.server_close();thread.join();service.close();app.processEvents()

if __name__=='__main__':main()

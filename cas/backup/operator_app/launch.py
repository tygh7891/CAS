#!/usr/bin/env python3
"""PC terminal: start MOCK-only HTTP service and PyQt dashboard together."""
import argparse
from pathlib import Path
import sys
import threading
from service import AppService,create_http

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be 1–65535')
    service=AppService(Path(__file__).resolve().parent/'logs')
    try:server,token=create_http(service,args.port)
    except OSError as exc:
        service.close();print(f'서버 시작 실패: {exc}. 다른 포트는 --port 8766 으로 지정하세요.');return 1
    http=threading.Thread(target=server.serve_forever,daemon=True);http.start()
    ticker=threading.Thread(target=service.run,daemon=True);ticker.start()
    try:
        from PyQt5.QtWidgets import QApplication
        from gui import Dashboard
        app=QApplication(sys.argv[:1]);window=Dashboard(f'http://127.0.0.1:{server.server_port}',token)
        print(f'CAS MOCK 관제 준비: http://127.0.0.1:{server.server_port} | 실물 명령 없음',flush=True)
        window.show();return app.exec_()
    finally:
        service.stop_event.set();ticker.join(timeout=2)
        server.shutdown();server.server_close();http.join(timeout=2);service.close()

if __name__=='__main__':raise SystemExit(main())

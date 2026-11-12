"""PC: physical CAS server and GUI. Startup does not send motion goals."""
import argparse
from pathlib import Path
import sys
import threading
from service import AppService, RequestError, create_http


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--config', default=str(Path(__file__).with_name('real_config.json')))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Invalid port')
    from PyQt5.QtWidgets import QApplication
    from gui import Dashboard
    from real_nav2_adapter import RealNav2Adapter
    adapter = RealNav2Adapter(args.config, RequestError)
    service = AppService(Path(__file__).parent/'logs', adapter)
    try:
        server, token = create_http(service, args.port)
    except Exception:
        service.close()
        raise
    http = threading.Thread(target=server.serve_forever, daemon=True)
    ticker = threading.Thread(target=service.run, daemon=True)
    http.start()
    ticker.start()
    try:
        app = QApplication(sys.argv[:1])
        window = Dashboard(f'http://127.0.0.1:{server.server_port}', token)
        print(f'CAS 실물 관제: http://127.0.0.1:{server.server_port} | 버튼 요청 시 실물 이동', flush=True)
        window.show()
        return app.exec_()
    finally:
        service.stop_event.set()
        ticker.join(timeout=2)
        server.shutdown()
        server.server_close()
        http.join(timeout=2)
        service.close()


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""PC terminal: start MOCK-only HTTP service and PyQt dashboard together."""
import argparse
from pathlib import Path
import sys
import threading
from service import AppService,RequestError,create_http

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--sim-nav2',action='store_true',help='Gazebo SIM_NAV2 관제 모드 (도메인 84 전용)')
    parser.add_argument('--generated-dir',help='Gazebo generated_map 경로 (기본: ~/CAS_sim_ws/generated_map)')
    parser.add_argument('--map',dest='map_path',help='지도 YAML: 보기·좌표 확인 전용')
    parser.add_argument('--mask',dest='mask_path',help='선택 마스크 YAML: 보기 전용')
    parser.add_argument('--mask-role',choices=['display','allowed'],default='display')
    parser.add_argument('--candidates',help='미승인 좌표 후보 JSON, 보기 전용')
    args=parser.parse_args()
    if args.sim_nav2 and args.map_path:parser.error('--sim-nav2 cannot be combined with --map')
    if args.mask_path and not args.map_path:parser.error('--mask requires --map')
    if args.candidates and not args.map_path:parser.error('--candidates requires --map')
    if not 1<=args.port<=65535:parser.error('port must be 1–65535')
    try:
        from PyQt5.QtWidgets import QApplication
        from gui import Dashboard
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith('PyQt5'):
            print(f'현재 Python에 PyQt5가 없습니다: {sys.executable}')
            print('이 PC에서는 다음 명령을 사용하세요:')
            print(f'/usr/bin/python3 {Path(__file__).resolve()}')
            return 1
        raise
    review=None
    adapter=None
    if args.sim_nav2:
        try:
            from sim_nav2_adapter import SimNav2Adapter
            adapter=SimNav2Adapter(generated_dir=args.generated_dir,request_error_cls=RequestError)
        except Exception as exc:
            print(f'SIM_NAV2 초기화 실패: {exc}');return 1
    elif args.map_path:
        try:
            from map_geometry import review_maps
            review=review_maps(args.map_path,args.mask_path,args.mask_role,args.candidates)
        except (OSError,ValueError,KeyError,ImportError) as exc:
            print(f'지도 읽기 실패: {exc}');return 1
    service=AppService(Path(__file__).resolve().parent/'logs',map_review=review,adapter=adapter)
    try:server,token=create_http(service,args.port)
    except OSError as exc:
        service.close();print(f'서버 시작 실패: {exc}. 다른 포트는 --port 8766 으로 지정하세요.');return 1
    http=threading.Thread(target=server.serve_forever,daemon=True);http.start()
    ticker=threading.Thread(target=service.run,daemon=True);ticker.start()
    try:
        app=QApplication(sys.argv[:1]);window=Dashboard(f'http://127.0.0.1:{server.server_port}',token)
        mode_label='SIM_NAV2' if args.sim_nav2 else ('MAP_REVIEW' if review else 'MOCK')
        print(f'CAS {mode_label} 관제 준비: http://127.0.0.1:{server.server_port} | 실물 명령 없음',flush=True)
        window.show();return app.exec_()
    finally:
        service.stop_event.set();ticker.join(timeout=2)
        server.shutdown();server.server_close();http.join(timeout=2);service.close()

if __name__=='__main__':raise SystemExit(main())

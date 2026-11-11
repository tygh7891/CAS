"""Run from CAS root: python -m fms_server.main --config fms_server/config.yaml"""
import argparse
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core import FMS, Settings


class EnqueueRequest(BaseModel):
    robot_id: str
    spin_count: int


class Server:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        raw = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        self.raw = raw
        self.error = None
        self.manager = None
        try:
            self.manager = FMS(Settings.from_yaml_data(raw))
        except (ValueError, KeyError, TypeError) as exc:
            self.error = str(exc)

    def app(self) -> FastAPI:
        api = FastAPI(title='CAS FMS (central controller)', version='0.1')

        @api.get('/api/state')
        def status():
            if self.manager is None:
                return {'configured': False, 'configuration_error': self.error,
                        'robots': {}, 'routes': {}, 'zone': {'owner': None, 'waiting': [],
                                                              'blocked': 'Configuration incomplete'},
                        'events': [], 'history': [],
                        'settings': {'next_job_delay_s': 3.0}}
            return self.manager.status()

        @api.post('/api/jobs', status_code=202)
        def enqueue(req: EnqueueRequest):
            if self.manager is None:
                raise HTTPException(409, f'Configure fms_server/config.yaml first: {self.error}')
            try:
                return self.manager.enqueue(req.robot_id, req.spin_count)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

        @api.post('/api/workers/{robot_id}/poll')
        def poll(robot_id: str, report: dict):
            if self.manager is None:
                raise HTTPException(409, f'Configuration incomplete: {self.error}')
            try:
                return self.manager.worker_poll(robot_id, report)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

        return api


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='fms_server/config.yaml')
    args = ap.parse_args()
    server = Server(Path(args.config))
    host = server.raw['server'].get('host', '127.0.0.1')
    port = int(server.raw['server'].get('port', 8765))
    print('FMS configuration:', 'READY' if not server.error else f'INCOMPLETE: {server.error}')
    print(f'FMS HTTP bind: {host}:{port}; remote clients must use this PC\'s actual LAN IP')
    uvicorn.run(server.app(), host=host, port=port)


if __name__ == '__main__':
    main()

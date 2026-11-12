"""Regression check for the approved Wi-Fi/LAN server deployment default."""
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from fms_server.main import Server


def test_lan_bind_default_keeps_status_reachable_with_current_coordinates():
    config = Path(__file__).resolve().parents[1] / 'config.yaml'
    settings = yaml.safe_load(config.read_text(encoding='utf-8'))
    assert settings['server']['host'] == '0.0.0.0'
    assert settings['server']['port'] == 8765
    # Reachability does not depend on whether the deployment has filled routes.
    response = TestClient(Server(config).app()).get('/api/state')
    assert response.status_code == 200
    assert isinstance(response.json()['configured'], bool)
    assert 'robots' in response.json()

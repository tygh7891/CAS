"""Regression check for the approved Wi-Fi/LAN server deployment default."""
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from fms_server.main import Server


def test_lan_bind_default_keeps_status_reachable_before_coordinates_are_filled():
    config = Path(__file__).resolve().parents[1] / 'config.yaml'
    settings = yaml.safe_load(config.read_text(encoding='utf-8'))
    assert settings['server']['host'] == '0.0.0.0'
    assert settings['server']['port'] == 8765
    # The public status endpoint must answer even before real-map coordinates exist.
    response = TestClient(Server(config).app()).get('/api/state')
    assert response.status_code == 200
    assert response.json()['configured'] is False

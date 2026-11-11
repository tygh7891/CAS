"""Configured participation: solo modes never depend on the inactive robot.

Test coordinates are synthetic and must not be used on a real track.
"""
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from fms_server.core import FMS
from fms_server.main import Server
from fms_server.models import Settings
from fms_server.tests.test_core import Clock, config, p


def solo_settings(robot_id: str):
    data = config()
    data['server']['active_robots'] = [robot_id]
    inactive = 'robot_2' if robot_id == 'robot_1' else 'robot_1'
    # An inactive robot needs neither real coordinates nor fresh Worker reports.
    for name in ('endpoint_a', 'endpoint_b', 'wait_a', 'wait_b'):
        data['robots'][inactive][name] = {'x': None, 'y': None, 'yaw': None}
    return data


@pytest.mark.parametrize('rid,start,end', [
    ('robot_1', p(-1., -1.), p(1., 1.)),
    ('robot_2', p(-1., 1.), p(1., -1.)),
])
def test_single_robot_reserves_and_releases_for_both_legs_without_other_worker(rid, start, end):
    clock = Clock()
    fms = FMS(Settings.from_yaml_data(solo_settings(rid)), clock)
    assert list(fms.robots) == [rid]
    assert fms.status()['settings']['active_robots'] == [rid]
    with pytest.raises(ValueError, match='Unknown robot'):
        fms.enqueue('robot_2' if rid == 'robot_1' else 'robot_1', 1)
    session = 'test_session_single'
    seq = 0
    pose = start

    def poll(result=None, command_id=None):
        nonlocal seq
        seq += 1
        return fms.worker_poll(rid, {
            'session_id': session, 'seq': seq, 'ready': True,
            'pose': pose, 'pose_age_s': 0.,
            'result': result, 'result_command_id': command_id,
        })

    def move(new_pose):
        nonlocal pose
        pose = new_pose
        poll()

    def finish_action():
        cmd = fms.robots[rid].command
        assert cmd is not None
        poll('SUCCEEDED', cmd['command_id'])

    poll()
    fms.enqueue(rid, 1)
    assert fms.zone.owner == rid
    assert fms.robots[rid].command['target'] == end
    assert not fms.zone.waiting
    move(p(0., 0.))
    assert fms.zone.owner == rid and fms.zone.entered
    move(end)
    assert fms.zone.owner is None
    finish_action()
    assert fms.robots[rid].command['kind'] == 'SPIN'
    finish_action()
    assert fms.zone.owner == rid
    assert fms.robots[rid].command['target'] == start
    move(p(0., 0.))
    assert fms.zone.owner == rid
    move(start)
    assert fms.zone.owner is None
    finish_action()
    assert fms.history[0]['status'] == 'COMPLETED'
    assert not fms.zone.waiting


def test_single_robot_no_other_report_needed_for_second_queued_job_and_cooldown():
    clock = Clock()
    fms = FMS(Settings.from_yaml_data(solo_settings('robot_1')), clock)
    fms.worker_poll('robot_1', {'session_id': 'long_session_1', 'seq': 1, 'ready': True,
                                'pose': p(-1., -1.), 'pose_age_s': 0.})
    fms.enqueue('robot_1', 0)
    fms.enqueue('robot_1', 2)
    assert fms.zone.owner == 'robot_1'
    assert len(fms.jobs.pending('robot_1')) == 1
    assert 'robot_2' not in fms.status()['robots']
    assert 'robot_2' not in fms.status()['routes']


def test_dual_mode_still_requires_both_robot_reports():
    clock = Clock()
    data = config()
    data['server']['active_robots'] = ['robot_1', 'robot_2']
    fms = FMS(Settings.from_yaml_data(data), clock)
    fms.worker_poll('robot_1', {'session_id': 'long_session_1', 'seq': 1, 'ready': True,
                                'pose': p(-1., -1.), 'pose_age_s': 0.})
    fms.enqueue('robot_1', 1)
    assert fms.zone.owner is None
    assert fms.robots['robot_1'].command is None
    fms.worker_poll('robot_2', {'session_id': 'long_session_2', 'seq': 1, 'ready': True,
                                'pose': p(-1., 1.), 'pose_age_s': 0.})
    assert fms.zone.owner == 'robot_1'


@pytest.mark.parametrize('active', [[], ['robot_1','robot_1'], ['robot_3'],
                                     ['robot_1','robot_2','robot_3'], 'robot_1', None])
def test_invalid_active_robots_configuration_rejected(active):
    data = config()
    data['server']['active_robots'] = active
    with pytest.raises(ValueError, match='active_robots'):
        Settings.from_yaml_data(data)


def test_single_mode_http_status_and_inactive_worker_rejected(tmp_path: Path):
    file = tmp_path / 'fms.yaml'
    file.write_text(yaml.safe_dump(solo_settings('robot_2')), encoding='utf-8')
    client = TestClient(Server(file).app())
    state = client.get('/api/state').json()
    assert state['configured'] is True
    assert state['settings']['active_robots'] == ['robot_2']
    assert list(state['robots']) == ['robot_2']
    assert client.post('/api/jobs', json={'robot_id':'robot_1','spin_count':2}).status_code == 400
    assert client.post('/api/workers/robot_1/poll', json={}).status_code == 400
    assert client.post('/api/jobs', json={'robot_id':'robot_2','spin_count':2}).status_code == 202
    assert len(client.get('/api/state').json()['robots']['robot_2']['pending']) == 1

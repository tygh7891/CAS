"""Independent components and public state contracts, without ROS2."""
from fms_server.job_manager import JobManager
from fms_server.robot_manager import RobotManager
from fms_server.zone_manager import ZoneManager
from fms_server.core import FMS, Point, Settings

from test_core import config, p, Run


def test_job_manager_owns_job_queue_and_cooldown_without_zone_or_robot():
    jobs = JobManager(['robot_1', 'robot_2'], cooldown_s=3.0)
    first = jobs.enqueue('robot_1', 2)
    second = jobs.enqueue('robot_1', 4)
    assert jobs.can_start('robot_1', 1.0)
    running = jobs.start('robot_1')
    assert running is first and running.leg == 'outbound'
    jobs.set_phase('robot_1', 'WORKING')
    assert jobs.spin_completed('robot_1')
    assert not jobs.spin_completed('robot_1')
    jobs.set_leg('robot_1', 'return')
    jobs.finish('robot_1', 'COMPLETED', 'done', 10.0)
    assert jobs.active('robot_1') is None
    assert not jobs.can_start('robot_1', 12.9)
    assert jobs.can_start('robot_1', 13.0)
    assert jobs.start('robot_1') is second
    assert jobs.history[0]['status'] == 'COMPLETED'


def test_zone_manager_owns_fifo_and_physical_entry_exit_separately():
    zone = ZoneManager(Settings.from_yaml_data(config()))
    assert zone.available()
    assert zone.request('robot_2')
    assert zone.request('robot_1')
    assert not zone.request('robot_1')
    assert not zone.available()
    try:
        zone.grant('robot_1')
    except RuntimeError:
        pass
    else:
        raise AssertionError('FIFO bypass allowed')
    zone.grant('robot_2')
    assert zone.owner == 'robot_2'
    assert zone.waiting[0] == 'robot_1'
    # Observed physical occupancy is not the same as reservation ownership.
    zone.observe('robot_2', Point(0, 0, 0), exited_on_destination_side=False)
    assert zone.entered
    zone.observe('robot_2', Point(-1, 1, 0), exited_on_destination_side=False)
    assert zone.owner == 'robot_2'
    assert zone.observe('robot_2', Point(1, -1, 0), exited_on_destination_side=True) == 'RELEASED'
    assert zone.owner is None
    zone.grant('robot_1')
    assert zone.owner == 'robot_1'


def test_robot_manager_only_tracks_action_and_observation_not_jobs():
    robots = RobotManager(['robot_1'], telemetry_timeout_s=2.)
    t = 10.
    payload = {'session_id': 'worker_session_one', 'seq': 1, 'ready': True,
               'pose': p(0, 1), 'pose_age_s': 0.1, 'feedback': {'distance_remaining_m': .8}}
    assert robots.report('robot_1', payload, t) == (False, True)
    assert robots.live('robot_1', 10.5)
    assert not robots.live('robot_1', 12.1)
    cmd = robots.issue('robot_1', 'job-id', 'NAVIGATE', Point(1, 2, 0))
    try:
        robots.issue('robot_1', 'job-id', 'NAVIGATE', Point(3, 4, 0))
    except RuntimeError:
        pass
    else:
        raise AssertionError('Navigation goal silently overwritten')
    result = {'result_command_id': cmd['command_id'], 'result': 'SUCCEEDED'}
    assert robots.accept_result('robot_1', result)[0] == cmd
    assert robots.accept_result('robot_1', result) is None


def test_public_job_and_robot_states_remain_distinct():
    run = Run()
    run.fms.enqueue('robot_1', 2)
    view = run.fms.status()
    job = view['robots']['robot_1']['active']
    bot = view['robots']['robot_1']
    assert job['phase'] == 'OUTBOUND'       # Work-stage
    assert bot['phase'] == 'NAVIGATE'       # Current Action
    assert bot['leg'] == 'outbound'         # Work direction
    assert 'leg' not in job                 # Existing HTTP Job schema preserved
    assert run.fms.jobs.active('robot_1').phase == 'OUTBOUND'
    # Job manager has no robot TF, while robot manager has no job queue.
    assert not hasattr(run.fms.jobs, 'robots')
    assert not hasattr(run.fms.robots_runtime, 'queues')
    assert not hasattr(run.fms.zone, 'job_queue')


def test_two_robot_competing_jobs_complete_without_preemption():
    run = Run()
    run.fms.enqueue('robot_1', 0)
    run.fms.enqueue('robot_2', 1)
    # R2 waits; R1 receives its single direct destination Action.
    assert run.current('robot_1')['target'] == p(1, 1)
    assert run.current('robot_2')['target'] == p(-.5, .5)
    run.move('robot_2', -.5, .5)
    run.succeed('robot_2')
    r1_outbound_command = run.current('robot_1')['command_id']
    run.cross('robot_1', p(1, 1))
    assert run.fms.zone.owner == 'robot_1'
    assert run.current('robot_1')['command_id'] == r1_outbound_command
    run.succeed('robot_1')  # R1's 0 spins => directly request return leg
    assert run.fms.zone.owner == 'robot_2'
    assert run.current('robot_1')['target'] == p(.5, .5)
    run.move('robot_1', .5, .5)
    run.succeed('robot_1')
    # R2 crosses and is now free to work while R1 goes home.
    run.cross('robot_2', p(1, -1))
    assert run.fms.zone.owner == 'robot_2'
    run.succeed('robot_2')
    assert run.fms.zone.owner == 'robot_1'
    assert run.current('robot_2')['kind'] == 'SPIN'
    run.succeed('robot_2')
    assert run.current('robot_2')['target'] == p(.5, -.5)
    run.move('robot_2', .5, -.5)
    run.succeed('robot_2')
    run.cross('robot_1', p(-1, -1))
    assert run.fms.zone.owner == 'robot_1'
    run.succeed('robot_1')
    assert run.fms.zone.owner == 'robot_2'
    run.cross('robot_2', p(-1, 1))
    run.succeed('robot_2')
    assert len(run.fms.history) == 2
    assert [item['status'] for item in run.fms.history] == ['COMPLETED', 'COMPLETED']
    assert run.fms.zone.owner is None
    assert run.fms.status()['robots']['robot_1']['phase'] == 'IDLE'
    assert run.fms.status()['robots']['robot_2']['phase'] == 'IDLE'

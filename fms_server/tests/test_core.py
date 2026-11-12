"""Pure controller tests, no ROS2 or mock worker service required.

Coordinates below are TEST FIXTURES ONLY, never used for real robot goals.
"""
from fms_server.core import FMS, Settings, Point


class Clock:
    def __init__(self):
        self.value = 10.

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def p(x,y):
    return {'x':x,'y':y,'yaw':0.}


def config():
    return {'server':{'next_job_delay_s':3,'telemetry_timeout_s':2.,'start_tolerance_m':.12},
            'zone':{'x_min':-.2,'y_min':-.2,'x_max':.2,'y_max':.2,
                    'robot_clearance_radius_m':.08},
            'robots':{
                'robot_1':{'endpoint_a':p(-1.,-1.),'endpoint_b':p(1.,1.),
                           'wait_a':p(-.5,-.5),'wait_b':p(.5,.5)},
                'robot_2':{'endpoint_a':p(-1.,1.),'endpoint_b':p(1.,-1.),
                           'wait_a':p(-.5,.5),'wait_b':p(.5,-.5)},
            }}


class Run:
    def __init__(self):
        self.clock=Clock()
        self.fms=FMS(Settings.from_yaml_data(config()),self.clock)
        self.pos={'robot_1':p(-1,-1),'robot_2':p(-1,1)}
        self.seqs={'robot_1':0,'robot_2':0}
        self.sessions={'robot_1':'sessionR1','robot_2':'sessionR2'}
        self.poll('robot_1'); self.poll('robot_2'); self.poll('robot_1')

    def poll(self,rid,result=None,command_id=None):
        self.seqs[rid]+=1
        return self.fms.worker_poll(rid,{'session_id':self.sessions[rid],
                        'seq':self.seqs[rid], 'ready':True, 'pose':self.pos[rid],
                        'pose_age_s':0., 'result':result,
                        'result_command_id':command_id})

    def move(self,rid,x,y):
        self.pos[rid]=p(x,y)
        return self.poll(rid)

    def current(self,rid):
        return self.fms.robots[rid].command

    def succeed(self,rid):
        command=self.current(rid)
        assert command is not None
        return self.poll(rid,'SUCCEEDED',command['command_id'])

    def cross(self,rid,end):
        self.move(rid,0.,0.)
        assert self.fms.zone_owner == rid
        self.move(rid,end['x'],end['y'])
        assert self.fms.zone_owner == rid  # Held until the Nav2 leg succeeds.
        assert self.fms.blocked is None


def test_zone_grant_direct_and_wait_then_transfer_after_navigation_result():
    t=Run()
    t.fms.enqueue('robot_1',2)
    assert t.fms.zone_owner == 'robot_1'
    assert t.current('robot_1')['target'] == p(1.,1.)
    t.fms.enqueue('robot_2',1)
    assert t.current('robot_2')['target'] == p(-.5,.5)
    assert list(t.fms.zone_queue)==['robot_2']
    t.move('robot_2',-.5,.5)
    t.succeed('robot_2')
    assert t.fms.status()['robots']['robot_2']['phase'] == 'WAITING_ZONE'
    assert t.fms.zone_owner == 'robot_1'
    t.cross('robot_1',p(1.,1.))
    # A temporary exit and re-entry must not turn the reservation into a block.
    t.move('robot_1',0.,0.)
    assert t.fms.zone_owner == 'robot_1'
    assert t.fms.blocked is None
    t.move('robot_1',1.,1.)
    assert t.current('robot_1')['kind'] == 'NAVIGATE'
    t.succeed('robot_1')
    assert t.fms.zone_owner == 'robot_2'
    assert t.current('robot_2')['target'] == p(1.,-1.)
    assert not t.fms.zone_queue


def test_one_job_contains_outbound_n_spins_and_return_then_3s_delay():
    t=Run()
    job1=t.fms.enqueue('robot_1',2)
    t.cross('robot_1',p(1.,1.))
    t.succeed('robot_1')
    assert t.current('robot_1')['kind'] == 'SPIN'
    first=t.current('robot_1')['command_id']
    t.succeed('robot_1')
    assert t.current('robot_1')['kind'] == 'SPIN'
    assert t.current('robot_1')['command_id'] != first
    t.succeed('robot_1')
    assert t.current('robot_1')['kind'] == 'NAVIGATE'
    assert t.current('robot_1')['target'] == p(-1.,-1.)
    t.cross('robot_1',p(-1.,-1.))
    t.succeed('robot_1')
    assert t.fms.jobs.active('robot_1') is None
    assert t.fms.history[0]['status']=='COMPLETED'
    assert t.fms.history[0]['job_id']==job1['job_id']
    t.fms.enqueue('robot_1',1)
    assert t.fms.jobs.active('robot_1') is None
    t.clock.advance(2.9)
    t.poll('robot_1');t.poll('robot_2')
    assert t.fms.jobs.active('robot_1') is None
    t.clock.advance(.11)
    t.poll('robot_1');t.poll('robot_2')
    assert t.fms.jobs.active('robot_1') is not None
    assert t.current('robot_1')['kind'] == 'NAVIGATE'


def test_waiting_ahead_prevents_reacquisition_even_if_free():
    t=Run()
    t.fms.enqueue('robot_1',0)
    t.fms.enqueue('robot_2',0)
    # R2 is not at the waiting point, so it keeps queue priority after release.
    t.cross('robot_1',p(1.,1.))
    assert t.fms.zone_owner == 'robot_1'
    t.succeed('robot_1')
    assert t.fms.zone_owner is None
    assert t.current('robot_1')['kind'] == 'NAVIGATE'
    assert t.current('robot_1')['target'] == p(.5,.5)
    assert list(t.fms.zone_queue)==['robot_2','robot_1']
    t.move('robot_2',-.5,.5)
    t.succeed('robot_2')
    assert t.fms.zone_owner == 'robot_2'
    assert list(t.fms.zone_queue)==['robot_1']


def test_no_release_without_observed_zone_entry_and_no_auto_recovery():
    t=Run()
    t.fms.enqueue('robot_1',1)
    t.move('robot_1',1.,1.)  # teleport over zone with no reported overlap
    assert t.fms.zone_owner == 'robot_1'
    t.succeed('robot_1')
    assert t.fms.jobs.queues['robot_1'].halted
    assert t.fms.history[0]['status']=='FAILED'
    assert t.fms.zone_owner == 'robot_1'  # fail closed, do not invent a release
    t.fms.enqueue('robot_1',1)
    t.clock.advance(5)
    t.poll('robot_1')
    assert t.fms.jobs.active('robot_1') is None


def test_unreserved_zone_entry_sends_other_robot_to_wait_and_holds_crossing():
    t=Run()
    t.move('robot_2',0.,0.)
    assert t.fms.blocked is None
    assert t.fms.zone.snapshot()['occupants'] == ['robot_2']
    t.fms.enqueue('robot_1',1)
    assert t.current('robot_1')['target'] == p(-.5,-.5)
    t.move('robot_1',-.5,-.5)
    t.succeed('robot_1')
    assert t.fms.status()['robots']['robot_1']['phase'] == 'WAITING_ZONE'
    assert t.fms.zone_owner is None
    t.move('robot_2',-1.,1.)
    assert t.fms.zone_owner == 'robot_1'
    assert t.current('robot_1')['target'] == p(1.,1.)


def test_stale_pose_prevents_start_and_second_robot_telemetry_required():
    t=Run()
    t.clock.advance(3.)
    t.fms.enqueue('robot_1',1)
    assert t.current('robot_1') is None
    t.poll('robot_1')
    assert t.current('robot_1') is None
    t.poll('robot_2')
    assert t.current('robot_1') is not None


def test_invalid_config_cannot_be_used_for_motion():
    cfg=config();cfg['robots']['robot_1']['wait_a']['x']=None
    try:
        Settings.from_yaml_data(cfg)
    except ValueError:
        pass
    else:
        assert False, 'unset coordinates must fail validation'


def test_worker_restart_during_action_blocks():
    t=Run()
    t.fms.enqueue('robot_1',1)
    t.sessions['robot_1']='newworker1'
    t.poll('robot_1')
    assert t.fms.blocked is not None
    assert t.fms.zone_owner == 'robot_1'


def test_retreat_to_entry_side_does_not_release_zone():
    t=Run()
    t.fms.enqueue('robot_1',1)
    t.move('robot_1',0.,0.)
    t.move('robot_1',-1.,-1.)
    assert t.fms.zone_owner == 'robot_1'
    assert t.fms.zone_entered


def test_other_robot_can_receive_waiting_point_goal_while_owner_inside_zone():
    t=Run()
    t.fms.enqueue('robot_1',1)
    t.move('robot_1',0.,0.)
    t.fms.enqueue('robot_2',1)
    assert t.current('robot_2')['target'] == p(-.5,.5)
    assert t.fms.zone_owner == 'robot_1'


def test_http_unconfigured_and_configured(tmp_path):
    from fastapi.testclient import TestClient
    import yaml
    from fms_server.main import Server
    source = tmp_path/'case.yaml'
    broken = config()
    broken['robots']['robot_1']['endpoint_a']['x'] = None
    source.write_text(yaml.safe_dump(broken))
    incomplete = TestClient(Server(source).app())
    assert incomplete.get('/api/state').json()['configured'] is False
    assert incomplete.post('/api/jobs',json={'robot_id':'robot_1','spin_count':2}).status_code==409

    source.write_text(yaml.safe_dump(config()))
    valid = TestClient(Server(source).app())
    assert valid.get('/api/state').json()['configured'] is True
    answer = valid.post('/api/jobs',json={'robot_id':'robot_1','spin_count':2})
    assert answer.status_code==202
    status=valid.get('/api/state').json()
    assert len(status['robots']['robot_1']['pending'])==1
    # No worker has connected; registration must not launch a Nav2 goal.
    assert status['zone']['owner'] is None

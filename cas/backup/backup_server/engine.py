"""Pure simulated A3/A4 state machine: no ROS, socket, or physical commands."""
import math

TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELED'}

class Coordinator:
    def __init__(self, config):
        if config.get('mode') != 'simulation_only':
            raise ValueError('Only simulation_only is supported')
        self.config = config
        self.speed = float(config['speed_m_s'])
        self.spin_duration = float(config['spin_duration_s'])
        self.radius = float(config['robot_radius_with_margin_m'])
        if not all(math.isfinite(v) and v > 0 for v in [self.speed, self.spin_duration, self.radius]):
            raise ValueError('Invalid simulation parameters')
        self.zone = config['zone']
        for key in ['xmin', 'xmax', 'ymin', 'ymax']:
            if not math.isfinite(self.zone[key]):
                raise ValueError('Invalid zone')
        if self.zone['xmin'] >= self.zone['xmax'] or self.zone['ymin'] >= self.zone['ymax']:
            raise ValueError('Invalid zone bounds')
        self.time = 0.0
        self.owner = None
        self.waiting = []
        self.events = []
        self.canceled = False
        self.pose_timeout = float(config.get('pose_timeout_s', 1.0))
        if not math.isfinite(self.pose_timeout) or self.pose_timeout <= 0:
            raise ValueError('Invalid pose timeout')
        self.blocked_reason = None
        self.robots = {}
        for r in sorted(config['robots'], key=lambda item: item['id']):
            if r['id'] in self.robots:
                raise ValueError('Duplicate robot ID')
            for k in ['start', 'wait', 'exit', 'goal']:
                if len(r[k]) != 2 or not all(math.isfinite(v) for v in r[k]):
                    raise ValueError('Invalid waypoint')
                if self.overlaps(r[k]):
                    raise ValueError('Mock waypoint must be outside expanded zone')
            self.robots[r['id']] = dict(r, position=list(r['start']), phase='TO_WAIT',
                task_state='RUNNING', entered=False, yaw=0.0, spin_elapsed=0.0,
                observed_position=list(r['start']), pose_time=0.0, feedback_enabled=True)
            self.emit('TASK_ACCEPTED', r['id'], 'TO_WAIT', 'MOCK: move to waiting point')

    def emit(self, event, robot, phase, reason):
        self.events.append(dict(sim_time=round(self.time, 3), event=event, robot_id=robot,
            phase=phase, owner=self.owner, reason=reason, mode='SIMULATION'))

    def overlaps(self, position):
        x,y = position
        z = self.zone
        dx = max(z['xmin']-x, 0.0, x-z['xmax'])
        dy = max(z['ymin']-y, 0.0, y-z['ymax'])
        return math.hypot(dx,dy) <= self.radius

    def phase(self, r, name, reason):
        r['phase'] = name
        self.emit('PHASE_CHANGED', r['id'], name, reason)

    def fresh(self, r):
        return self.time - r['pose_time'] < self.pose_timeout

    def report_pose(self, robot_id, position, source_time):
        # Source timestamp must advance. Replaying cached data cannot refresh it.
        r = self.robots[robot_id]
        if (len(position) != 2 or not all(math.isfinite(v) for v in position)
                or not math.isfinite(source_time) or source_time > self.time
                or source_time <= r['pose_time']):
            return False
        r['observed_position'] = list(position)
        r['pose_time'] = source_time
        return True

    def set_feedback(self, robot_id, enabled):
        self.robots[robot_id]['feedback_enabled'] = bool(enabled)
        self.emit('MOCK_FEEDBACK_SWITCH', robot_id, self.robots[robot_id]['phase'],
                  'enabled' if enabled else 'disabled; physical simulation may continue until guard trips')

    def request_zone(self, robot_id):
        r = self.robots[robot_id]
        if self.canceled or r['task_state'] != 'RUNNING' or r['phase'] != 'WAITING_ZONE':
            return False
        if robot_id == self.owner or robot_id in self.waiting:
            return False
        self.waiting.append(robot_id)
        self.emit('ZONE_REQUESTED', robot_id, r['phase'], 'Queued once per active task')
        return True

    def cancel_robot(self, robot_id):
        r = self.robots[robot_id]
        if r['task_state'] in TERMINAL:
            return
        # In this internal mock cancellation is acknowledged immediately and freezes motion.
        r['task_state'] = 'CANCELED'
        self.waiting = [name for name in self.waiting if name != robot_id]
        self.phase(r, 'HALTED', 'Mock cancellation acknowledged; simulated motion frozen')
        if self.owner == robot_id:
            if self.fresh(r) and not self.overlaps(r['observed_position']) and not self.overlaps(r['position']):
                self.owner = None
                self.emit('ZONE_RELEASED', robot_id, r['phase'], 'Cancellation acknowledged and fresh outside pose verified')
            else:
                self.blocked_reason = 'Canceled owner may occupy zone'
                self.emit('ZONE_BLOCKED', robot_id, r['phase'], self.blocked_reason)

    def move(self, r, point, dt):
        x,y = r['position']; dx,dy = point[0]-x,point[1]-y
        distance = math.hypot(dx,dy)
        if distance <= self.speed*dt:
            r['position'] = list(point)
            if r['feedback_enabled']:self.report_pose(r['id'], r['position'], self.time)
            return True
        r['position'] = [x+dx/distance*self.speed*dt, y+dy/distance*self.speed*dt]
        if r['feedback_enabled']:self.report_pose(r['id'], r['position'], self.time)
        return False

    def tick(self, dt):
        if not math.isfinite(dt) or not 0 < dt <= 0.1:
            raise ValueError('Use simulation steps in (0, 0.1]')
        if self.canceled:
            return
        self.time += dt
        # Refresh only simulated streams that actually produced a new report.
        for r in self.robots.values():
            if r['feedback_enabled']:
                self.report_pose(r['id'], r['position'], self.time)
        stale = [r['id'] for r in self.robots.values()
                 if (r['task_state'] not in TERMINAL or r['id'] == self.owner) and not self.fresh(r)]
        if stale:
            self.fail_all('Pose stale: ' + ','.join(stale)); return
        # Stable robot order is the deterministic tie breaker.
        for r in self.robots.values():
            if r['task_state'] in TERMINAL:
                continue
            p = r['phase']
            if p == 'TO_WAIT':
                arrived = self.move(r, r['wait'], dt)
                if self.overlaps(r['position']):
                    self.fail_all('Unpermitted approach entered mock zone'); return
                if arrived:
                    self.phase(r, 'WAITING_ZONE', 'Waiting for exclusive permission')
                    self.request_zone(r['id'])
            elif p == 'CROSSING':
                if self.owner != r['id']:
                    self.fail_all('Missing crossing permission'); return
                arrived = self.move(r, r['exit'], dt)
                if self.overlaps(r['observed_position']):
                    if not r['entered']:
                        self.emit('ZONE_ENTERED', r['id'], p, 'Mock footprint overlaps zone')
                    r['entered'] = True
                if arrived:
                    if not self.fresh(r) or self.overlaps(r['observed_position']):
                        continue
                    if not r['entered']:
                        self.fail_all('Crossing entry not observed'); return
                    self.emit('ZONE_EXIT_VERIFIED', r['id'], p, 'Mock footprint fully outside zone')
                    self.owner = None
                    self.emit('ZONE_RELEASED', r['id'], p, 'Next permission may now be granted')
                    self.phase(r, 'TO_GOAL', 'Move to destination '+r['destination'])
            elif p == 'TO_GOAL':
                if self.overlaps(r['position']):
                    self.fail_all('Unexpected zone reentry'); return
                if self.move(r, r['goal'], dt):
                    self.phase(r, 'SPINNING', 'Destination reached; start mock rotation')
            elif p == 'SPINNING':
                r['spin_elapsed'] = min(self.spin_duration, r['spin_elapsed']+dt)
                r['yaw'] = self.config['spin_angle_rad']*r['spin_elapsed']/self.spin_duration
                if r['spin_elapsed'] >= self.spin_duration:
                    r['task_state'] = 'SUCCEEDED'
                    self.phase(r, 'DONE', 'Rotation completed; remain at destination; no return')
        if self.owner is None and self.waiting and not self.blocked_reason:
            self.owner = self.waiting.pop(0)
            r = self.robots[self.owner]
            self.emit('ZONE_GRANTED', r['id'], 'CROSSING', 'First request; stable ID order for ties')
            self.phase(r, 'CROSSING', 'Exclusive mock crossing permission')
        occupied = [r['id'] for r in self.robots.values() if self.overlaps(r['position'])]
        if len(occupied)>1 or any(name != self.owner for name in occupied):
            self.fail_all('Mock zone mutual-exclusion violation')

    def fail_all(self, reason):
        self.canceled = True
        self.blocked_reason = reason
        self.waiting.clear()
        for r in self.robots.values():
            if r['task_state'] not in TERMINAL:
                r['task_state'] = 'FAILED'
                self.phase(r, 'HALTED', reason)
        self.emit('HALTED', None, None, reason+'; reservation retained for inspection')

    def cancel_all(self):
        self.canceled = True
        self.waiting.clear()
        for r in self.robots.values():
            if r['task_state'] not in TERMINAL:
                r['task_state'] = 'CANCELED'
                self.phase(r, 'HALTED', 'Simulation canceled; no physical command')
        if self.owner is not None:self.blocked_reason = 'All tasks canceled; owner retained until reset'
        self.emit('CANCELED', None, None, 'Simulated motion frozen; reservation retained until reset')

    @property
    def finished(self):
        return all(r['task_state'] in TERMINAL for r in self.robots.values())

    def snapshot(self):
        return dict(mode='SIMULATION', map_id=self.config['map_id'], sim_time=round(self.time,2),
            owner=self.owner, waiting=list(self.waiting), blocked_reason=self.blocked_reason, robots=[dict(id=r['id'],task_id=r['task_id'],
            destination=r['destination'],task_state=r['task_state'],phase=r['phase'],
            position=[round(v,3) for v in r['position']], observed_position=list(r['observed_position']),
            pose_age_s=round(self.time-r['pose_time'],3), yaw=round(r['yaw'],3)) for r in self.robots.values()])

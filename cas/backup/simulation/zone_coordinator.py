"""Event-driven mission core. Produces command intents; has no ROS/network I/O.

This is separate from the A4 mock integrator: positions must come from a worker.
Caller must use a monotonic wall clock for receipt/tick and source stamps for pose.
"""
import math
from mission_routes import zone_distance


class MissionCoordinator:
    def __init__(self, routes, polygon, radius=.10, timeout=1.0):
        self.routes, self.polygon, self.radius, self.timeout = routes, polygon, radius, timeout
        self.owner, self.queue, self.blocked = None, [], None
        self.commands, self.events, self.sequence = [], [], 0
        self.robots = {name:dict(phase='IDLE',pose=None,source=-math.inf,received=-math.inf,
                                 stopped_since=None,pending=None,entered=False) for name in sorted(routes)}

    def emit(self, name, event):
        self.events.append(dict(robot=name,event=event,owner=self.owner))

    def command(self, name, kind, target=None):
        self.sequence += 1
        command = dict(id=self.sequence,robot=name,kind=kind,target=target)
        self.commands.append(command)
        self.robots[name]['pending'] = command['id']
        self.emit(name,kind)

    def start(self):
        if any(r['phase']!='IDLE' for r in self.robots.values()):
            raise ValueError('Mission already started')
        for name,r in self.robots.items():
            r['phase']='TO_WAIT'
            self.command(name,'FOLLOW_PATH',self.routes[name]['segments'][0]['path'])

    def observation(self,name,position,source,received,linear,angular):
        r=self.robots[name]
        if not all(math.isfinite(v) for v in [*position,source,received,linear,angular]) or len(position)!=2:
            return False
        if source<=r['source'] or received<r['received']:
            return False
        r.update(pose=list(position),source=source,received=received)
        if abs(linear)<=.005 and abs(angular)<=.03:
            if r['stopped_since'] is None:r['stopped_since']=received
        else:r['stopped_since']=None
        return True

    def halt(self,reason):
        if self.blocked:return
        self.blocked=reason
        self.queue.clear()
        for name,r in self.robots.items():
            if r['phase'] not in ['DONE','IDLE']:
                r['phase']='HALTED'
                self.command(name,'CANCEL')
        # No release on cancellation, stale pose or failure.

    def result(self,name,command_id,success):
        r=self.robots[name]
        if self.blocked or command_id!=r['pending']:return False
        r['pending']=None
        r['stopped_since']=None
        if not success:
            self.halt('Action failed: '+name);return True
        following={'TO_WAIT':'VERIFY_WAIT','CROSSING':'VERIFY_EXIT','TO_GOAL':'VERIFY_GOAL','SPINNING':'VERIFY_DONE'}
        if r['phase'] in following:r['phase']=following[r['phase']]
        return True

    def tick(self,now):
        if self.blocked:return
        for name,r in self.robots.items():
            if r['phase'] in ['IDLE','DONE']:continue
            if r['pose'] is None or not 0<=now-r['received']<self.timeout:
                self.halt('Missing/stale observation: '+name);return
            overlap=zone_distance(r['pose'],self.polygon)<=self.radius
            if overlap and self.owner!=name:
                self.halt('Unpermitted zone entry: '+name);return
            if overlap:r['entered']=True
            stopped=r['stopped_since'] is not None and now-r['stopped_since']>=.3
            phase=r['phase']
            if phase=='VERIFY_WAIT' and stopped:
                if math.dist(r['pose'],self.routes[name]['wait'])>.02 or overlap:
                    self.halt('Invalid waiting position: '+name);return
                r['phase']='WAITING'
                if name not in self.queue:self.queue.append(name)
                self.emit(name,'ZONE_REQUESTED')
            elif phase=='VERIFY_EXIT' and stopped:
                if overlap or not r['entered']:continue
                if math.dist(r['pose'],self.routes[name]['exit'])>.02:
                    self.halt('Invalid exit position: '+name);return
                self.owner=None
                self.emit(name,'ZONE_RELEASED')
                r['phase']='TO_GOAL'
                self.command(name,'FOLLOW_PATH',self.routes[name]['segments'][2]['path'])
            elif phase=='VERIFY_GOAL' and stopped:
                if math.dist(r['pose'],self.routes[name]['goal'])>.02:
                    self.halt('Invalid destination: '+name);return
                r['phase']='SPINNING'
                self.command(name,'SPIN',2*math.pi)
            elif phase=='VERIFY_DONE' and stopped:
                r['phase']='DONE'
                self.emit(name,'TASK_COMPLETED_STOP_CONFIRMED')
        if self.owner is None and self.queue and not self.blocked:
            self.owner=self.queue.pop(0)
            r=self.robots[self.owner]
            r['phase']='CROSSING'
            r['entered']=False
            self.emit(self.owner,'ZONE_GRANTED')
            self.command(self.owner,'FOLLOW_PATH',self.routes[self.owner]['segments'][1]['path'])

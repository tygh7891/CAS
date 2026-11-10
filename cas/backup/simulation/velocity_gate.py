"""Pure monotonic lease gate for Gazebo velocity relay; never used for hardware."""
import math

ROBOTS=('robot_1','robot_2')


class VelocityGate:
    def __init__(self,session):
        self.session=session;self.sequence=-1;self.deadline=None;self.blocked=None
        self.permits={};self.changed={};self.velocities={}

    def lease(self,data,now):
        if self.blocked:return False
        if self.deadline is not None and now>self.deadline:
            self.blocked='Controller lease expired';return False
        try:
            if data['session']!=self.session or type(data['sequence']) is not int or data['sequence']<=self.sequence:return False
            expires=float(data['expires'])
            if not math.isfinite(expires) or not 0<expires-now<=.35:return False
            permits=data['permits']
            if not isinstance(permits,dict) or any(k not in ROBOTS or type(v) is not int for k,v in permits.items()):return False
        except (KeyError,TypeError,ValueError):return False
        for robot in ROBOTS:
            if permits.get(robot)!=self.permits.get(robot):
                self.changed[robot]=now;self.velocities.pop(robot,None)
        self.permits=dict(permits);self.sequence=data['sequence'];self.deadline=expires
        return True

    def velocity(self,robot,linear,angular,now):
        if robot not in ROBOTS or not all(math.isfinite(v) for v in [linear,angular,now]):return
        self.velocities[robot]=(linear,angular,now)

    def output(self,robot,now):
        if self.deadline is not None and now>self.deadline:self.blocked='Controller lease expired'
        if self.blocked or self.deadline is None or robot not in self.permits:return (0.0,0.0)
        velocity=self.velocities.get(robot)
        if velocity is None:return (0.0,0.0)
        linear,angular,received=velocity
        if not 0<=now-received<.15 or received<self.changed.get(robot,now):return (0.0,0.0)
        return max(-.08,min(.08,linear)),max(-.4,min(.4,angular))

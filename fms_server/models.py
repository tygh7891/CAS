"""Shared immutable geometry and validated FMS settings.

No queues, ROS2 operations, or workflow decisions live here.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Any

@dataclass(frozen=True)
class Point:
    x: float
    y: float
    yaw: float

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> 'Point':
        if not isinstance(raw, dict):
            raise ValueError('Point must be a map with x, y, yaw')
        vals = [raw.get(k) for k in ('x', 'y', 'yaw')]
        if any(type(v) not in (int, float) or not isfinite(v) for v in vals):
            raise ValueError('Point has unset or invalid x/y/yaw')
        return cls(*(float(v) for v in vals))

    def near(self, other: 'Point', distance: float) -> bool:
        return hypot(self.x - other.x, self.y - other.y) <= distance

    def as_json(self) -> dict:
        return {'x': self.x, 'y': self.y, 'yaw': self.yaw}


@dataclass(frozen=True)
class Route:
    endpoint_a: Point
    endpoint_b: Point
    wait_a: Point
    wait_b: Point


@dataclass(frozen=True)
class Settings:
    routes: dict[str, Route]
    zone: tuple[float, float, float, float]  # xmin ymin xmax ymax
    clearance: float
    cooldown: float
    ttl: float
    home_tolerance: float

    @classmethod
    def from_yaml_data(cls, data: dict) -> 'Settings':
        if not isinstance(data, dict):
            raise ValueError('Expected YAML object')
        zone = data['zone']
        bounds = [zone[k] for k in ('x_min', 'y_min', 'x_max', 'y_max')]
        if any(type(v) not in (int, float) or not isfinite(v) for v in bounds):
            raise ValueError('Set all zone bounds in fms_server/config.yaml')
        xmin, ymin, xmax, ymax = [float(v) for v in bounds]
        if xmin >= xmax or ymin >= ymax:
            raise ValueError('Zone min must be smaller than max')
        radius = zone['robot_clearance_radius_m']
        if type(radius) not in (int, float) or not isfinite(radius) or radius <= 0:
            raise ValueError('Set a positive robot_clearance_radius_m in YAML')
        server = data['server']
        try:
            cooldown = float(server['next_job_delay_s'])
            ttl = float(server['telemetry_timeout_s'])
            tolerance = float(server['start_tolerance_m'])
        except (ValueError, TypeError) as exc:
            raise ValueError('Set server telemetry_timeout_s and start_tolerance_m in YAML') from exc
        if not (isfinite(cooldown) and cooldown >= 0 and isfinite(ttl) and ttl > 0
                and isfinite(tolerance) and tolerance > 0):
            raise ValueError('Invalid server thresholds')
        # Only selected robots participate in scheduling and shared-zone checks.
        # Keeping two as the default preserves the original two-robot deployment.
        active = server.get('active_robots', ['robot_1', 'robot_2'])
        allowed = {'robot_1', 'robot_2'}
        if (not isinstance(active, list) or not 1 <= len(active) <= 2
                or any(not isinstance(rid, str) or rid not in allowed for rid in active)
                or len(set(active)) != len(active)):
            raise ValueError('server.active_robots must be [robot_1], [robot_2], or [robot_1, robot_2]')
        raw_robots = data['robots']
        if not isinstance(raw_robots, dict) or not all(rid in raw_robots for rid in active):
            raise ValueError('Each active robot needs its route in robots')
        # An inactive robot's coordinates may remain null or be omitted.
        routes = {rid: Route(*(Point.parse(raw_robots[rid][k]) for k in
                   ('endpoint_a', 'endpoint_b', 'wait_a', 'wait_b')))
                  for rid in active}
        settings = cls(routes, (xmin, ymin, xmax, ymax), float(radius), cooldown, ttl, tolerance)
        for rid, route in routes.items():
            for name in ('endpoint_a', 'endpoint_b', 'wait_a', 'wait_b'):
                if settings.overlap(getattr(route, name)):
                    raise ValueError(f'{rid}.{name} lies inside the expanded shared zone')
        return settings

    def overlap(self, p: Point) -> bool:
        x1, y1, x2, y2 = self.zone
        dx = max(x1 - p.x, 0., p.x - x2)
        dy = max(y1 - p.y, 0., p.y - y2)
        return hypot(dx, dy) <= self.clearance




@dataclass
class Job:
    """One logical round trip; its phase is not the robot's Action status."""
    job_id: str
    robot_id: str
    spin_count: int
    status: str = 'QUEUED'
    phase: str = 'QUEUED'
    spins_done: int = 0
    message: str = ''
    leg: str = ''  # empty until start, then outbound / return

    def to_dict(self) -> dict:
        # Preserve existing public Job JSON; `leg` is exposed by robot status instead.
        return {key: value for key, value in vars(self).items() if key != 'leg'}

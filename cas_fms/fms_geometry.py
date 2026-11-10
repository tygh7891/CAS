from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Pose:
    x_m: float
    y_m: float
    yaw_rad: float

    def distance_to(self, other: "Pose") -> float:
        return hypot(self.x_m - other.x_m, self.y_m - other.y_m)


@dataclass(frozen=True)
class ZoneBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def overlaps(self, pose: Pose, radius_m: float) -> bool:
        return (
            self.min_x - radius_m <= pose.x_m <= self.max_x + radius_m
            and self.min_y - radius_m <= pose.y_m <= self.max_y + radius_m
        )

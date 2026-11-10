from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path

import yaml

from fms_geometry import Pose, ZoneBounds

DEFAULT_SCENARIO = Path(__file__).with_name("scenario.yaml")


class DemoPreset(StrEnum):
    NORMAL = "normal"
    DROPOUT = "dropout"
    CANCEL = "cancel"


DEMO_TITLES = {
    DemoPreset.NORMAL: "정상 순차 통과",
    DemoPreset.DROPOUT: "위치 보고 중단·복구",
    DemoPreset.CANCEL: "교차로 내 작업 취소",
}


def require_verified_layout(path: Path) -> None:
    metadata = yaml.safe_load(path.read_text())
    if (
        not isinstance(metadata, dict)
        or metadata.get("physical_layout_verified") is not True
    ):
        raise ValueError(
            "Set physical_layout_verified only after validating the real site"
        )


@dataclass(frozen=True)
class Route:
    start_label: str
    goal_label: str
    start: Pose
    wait: Pose
    exit: Pose
    goal: Pose


@dataclass(frozen=True)
class MapLayer:
    image: Path
    resolution: float
    origin: tuple[float, float, float]


@dataclass(frozen=True)
class Scenario:
    map_id: str
    world: MapLayer
    keepout: MapLayer
    zone: ZoneBounds
    robot_radius_m: float
    stale_after_s: float
    routes: dict[str, Route]


def _numbers(values: object, count: int) -> tuple[float, ...]:
    if not isinstance(values, list) or len(values) != count:
        raise ValueError(f"Expected {count} numeric values")
    result = tuple(float(value) for value in values)
    if not all(isfinite(value) for value in result):
        raise ValueError("Scenario values must be finite")
    return result


def _map_layer(path: Path) -> MapLayer:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    x, y, yaw = _numbers(data["origin"], 3)
    resolution = float(data["resolution"])
    image = path.parent / data["image"]
    if not isfinite(resolution) or resolution <= 0 or yaw != 0:
        raise ValueError("Demo maps need a positive resolution and zero origin yaw")
    if not image.is_file():
        raise ValueError(f"Missing map image: {image}")
    return MapLayer(image, resolution, (x, y, yaw))


def load_scenario(path: Path = DEFAULT_SCENARIO) -> Scenario:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    world = _map_layer(path.parent / data["map"])
    keepout = _map_layer(path.parent / data["keepout"])
    if (world.resolution, world.origin) != (keepout.resolution, keepout.origin):
        raise ValueError("World map and keepout mask must use the same grid")
    bounds = ZoneBounds(*_numbers(data["zone"], 4))
    radius = float(data["robot_radius_m"])
    stale = float(data["stale_after_s"])
    if bounds.min_x >= bounds.max_x or bounds.min_y >= bounds.max_y:
        raise ValueError("Zone bounds must be ordered")
    if not all(isfinite(value) and value > 0 for value in (radius, stale)):
        raise ValueError("Robot radius and stale limit must be positive")
    if set(data["routes"]) != {"robot_1", "robot_2"}:
        raise ValueError("The A1 demo needs robot_1 and robot_2")
    routes = {}
    for robot_id, route in data["routes"].items():
        start, wait, exit_pose, goal = (
            Pose(*_numbers(route[name], 3))
            for name in ("start", "wait", "exit", "goal")
        )
        if any(
            bounds.overlaps(pose, radius) for pose in (start, wait, exit_pose, goal)
        ):
            raise ValueError(f"{robot_id} waypoints must be outside the shared Zone")
        routes[robot_id] = Route(
            str(route["start_label"]),
            str(route["goal_label"]),
            start,
            wait,
            exit_pose,
            goal,
        )
    return Scenario(data["map_id"], world, keepout, bounds, radius, stale, routes)

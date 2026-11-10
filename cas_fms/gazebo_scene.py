from collections.abc import Iterator
from itertools import groupby
from math import cos, sin
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml
from PyQt5.QtGui import QImage

from fms_geometry import Pose

WORLD_NAME = "cas_fleet"
DEFAULT_GUI_CONFIG = Path("/usr/share/gz/gz-sim8/gui/gui.config")
MAP_COLORS = {
    "wall": "0.20 0.26 0.34 1",
    "unknown": "0.55 0.60 0.66 1",
    "keepout": "0.28 0.38 0.51 1",
    "free": "0.92 0.93 0.90 1",
}


def world_from_map(map_yaml: Path, keepout_yaml: Path, output: Path) -> None:
    """Reproduce the shared grid and draw the keepout mask on its floor."""
    metadata = yaml.safe_load(map_yaml.read_text())
    keepout_metadata = yaml.safe_load(keepout_yaml.read_text())
    image = QImage(str(map_yaml.with_name(metadata["image"]))).convertToFormat(
        QImage.Format_Grayscale8
    )
    keepout = QImage(
        str(keepout_yaml.with_name(keepout_metadata["image"]))
    ).convertToFormat(QImage.Format_Grayscale8)
    if (
        image.isNull()
        or keepout.isNull()
        or image.size() != keepout.size()
        or metadata["origin"] != keepout_metadata["origin"]
        or metadata["resolution"] != keepout_metadata["resolution"]
        or metadata["origin"][2] != 0
        or metadata.get("negate") != 0
        or keepout_metadata.get("negate") != 0
    ):
        raise ValueError("Gazebo needs aligned, non-negated occupancy and keepout maps")
    scale = metadata["resolution"]
    origin_x, origin_y, _ = metadata["origin"]
    occupied = 255 * (1 - metadata["occupied_thresh"])
    free = 255 * (1 - metadata["free_thresh"])
    restricted = 255 * (1 - keepout_metadata["occupied_thresh"])

    sdf = ET.Element("sdf", version="1.9")
    world = ET.SubElement(sdf, "world", name=WORLD_NAME)
    scene = ET.SubElement(world, "scene")
    ET.SubElement(scene, "ambient").text = "0.65 0.65 0.65 1"
    ET.SubElement(scene, "background").text = "0.84 0.87 0.90 1"
    ET.SubElement(scene, "grid").text = "false"
    physics = ET.SubElement(world, "physics", name="fast", type="ignored")
    ET.SubElement(physics, "max_step_size").text = "0.002"
    ET.SubElement(physics, "real_time_factor").text = "1"
    for plugin in ("Physics", "UserCommands", "SceneBroadcaster", "Sensors"):
        filename = {
            "Physics": "physics",
            "UserCommands": "user-commands",
            "SceneBroadcaster": "scene-broadcaster",
            "Sensors": "sensors",
        }[plugin]
        system = ET.SubElement(
            world,
            "plugin",
            filename=f"gz-sim-{filename}-system",
            name=f"gz::sim::systems::{plugin}",
        )
        if plugin == "Sensors":
            ET.SubElement(system, "render_engine").text = "ogre2"
    light = ET.SubElement(world, "light", name="sun", type="directional")
    ET.SubElement(light, "direction").text = "-0.4 0.2 -1"
    ET.SubElement(light, "diffuse").text = "0.9 0.9 0.9 1"
    ET.SubElement(light, "specular").text = "0.2 0.2 0.2 1"

    layout = ET.SubElement(world, "model", name="fleet_world_new")
    ET.SubElement(layout, "static").text = "true"
    link = ET.SubElement(layout, "link", name="layout")
    _box(link, "floor", (0, 0, -0.025), (6, 6, 0.05), "0.68 0.72 0.76 1")

    def cell(x: int, row: int) -> str:
        intensity = image.pixelColor(x, row).red()
        if intensity <= occupied:
            return "wall"
        if intensity < free:
            return "unknown"
        if keepout.pixelColor(x, row).red() <= restricted:
            return "keepout"
        return "free"

    rows = ([cell(x, y) for x in range(image.width())] for y in range(image.height()))
    for x0, x1, y0, y1, kind in _rectangles(rows):
        wall = kind == "wall"
        _box(
            link,
            f"{kind}_{x0}_{y0}",
            (
                origin_x + scale * (x0 + x1) / 2,
                origin_y + scale * (image.height() - (y0 + y1) / 2),
                0.15 if wall else 0.0005,
            ),
            (scale * (x1 - x0), scale * (y1 - y0), 0.30 if wall else 0.001),
            MAP_COLORS[kind],
            collision=wall,
        )
    ET.indent(sdf)
    ET.ElementTree(sdf).write(output, encoding="unicode")


def _rectangles(rows: Iterator[list[str]]) -> Iterator[tuple[int, int, int, int, str]]:
    """Merge adjacent equal runs without moving the grid boundaries."""
    active: dict[tuple[int, int, str], int] = {}
    height = 0
    for y, row in enumerate(rows):
        runs = set()
        x = 0
        for kind, cells in groupby(row):
            end = x + sum(1 for _ in cells)
            runs.add((x, end, kind))
            x = end
        for x0, x1, kind in sorted(active.keys() - runs):
            yield x0, x1, active.pop((x0, x1, kind)), y, kind
        for run in runs:
            active.setdefault(run, y)
        height = y + 1
    for (x0, x1, kind), y0 in sorted(active.items()):
        yield x0, x1, y0, height, kind


def map_view_config(map_yaml: Path, output: Path) -> None:
    metadata = yaml.safe_load(map_yaml.read_text())
    image = QImage(str(map_yaml.with_name(metadata["image"])))
    width, height = (
        pixels * metadata["resolution"] for pixels in (image.width(), image.height())
    )
    origin_x, origin_y, _ = metadata["origin"]
    altitude = max(width, height) * 0.86
    x = origin_x + width / 2
    y = origin_y + height / 2 - altitude * 0.17
    default = DEFAULT_GUI_CONFIG.read_text().partition("?>")[2]
    config = ET.fromstring(f"<gui>{default}</gui>")
    view = config.find("plugin[@filename='MinimalScene']")
    view.find("camera_pose").text = f"{x:.5f} {y:.5f} {altitude:.5f} 0 1.40 1.5708"
    view.find("ambient_light").text = "0.65 0.65 0.65"
    view.find("background_color").text = "0.84 0.87 0.90"
    dialog = config.find("dialog[@name='quick_start']")
    if dialog is not None:
        dialog.set("show_again", "false")
    output.write_text(
        "\n".join(ET.tostring(element, encoding="unicode") for element in config)
    )


def _box(
    link: ET.Element,
    name: str,
    position: tuple[float, float, float],
    size: tuple[float, float, float],
    color: str,
    *,
    collision: bool = True,
) -> None:
    for element in ("collision", "visual") if collision else ("visual",):
        shape = ET.SubElement(link, element, name=name)
        ET.SubElement(shape, "pose").text = " ".join(map(str, position)) + " 0 0 0"
        box = ET.SubElement(ET.SubElement(shape, "geometry"), "box")
        ET.SubElement(box, "size").text = " ".join(map(str, size))
        if element == "visual":
            material = ET.SubElement(shape, "material")
            ET.SubElement(material, "ambient").text = color
            ET.SubElement(material, "diffuse").text = color


def robot_description(urdf: str, robot_id: str) -> str:
    """Separate Gazebo topics while keeping standard ROS frames in each domain."""
    robot = ET.fromstring(urdf)
    robot.set("name", robot_id)
    for tag in ("topic", "odom_topic", "tf_topic"):
        for topic in robot.iter(tag):
            topic.text = f"/{robot_id}/{topic.text.strip('/')}"
    for gazebo in robot.findall("gazebo"):
        for sensor in gazebo.findall("sensor"):
            if sensor.get("type") in {"camera", "imu"}:
                gazebo.remove(sensor)
            elif sensor.get("type") == "gpu_lidar":
                sensor.find("lidar/noise/stddev").text = "0.005"
        for plugin in gazebo.findall("plugin"):
            if plugin.get("name") == "pinky_gz_sim::LampControlPlugin":
                gazebo.remove(plugin)
    return ET.tostring(robot, encoding="unicode")


def gazebo_pose_request(robot_id: str, pose: Pose) -> str:
    return (
        f'name: "{robot_id}", position: {{x: {pose.x_m}, y: {pose.y_m}, z: 0.005}}, '
        f"orientation: {{z: {sin(pose.yaw_rad / 2)}, w: {cos(pose.yaw_rad / 2)}}}"
    )

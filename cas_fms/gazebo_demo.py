import argparse
import os
import signal
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import yaml
from ament_index_python.packages import get_package_share_directory

from fms_settings import load_scenario
from gazebo_nav_config import bridge_config, nav2_config
from gazebo_scene import WORLD_NAME, map_view_config, robot_description, world_from_map
from local_demo import run_demo

SIM_DOMAINS = {"robot_1": "114", "robot_2": "130"}
GAZEBO_SCENARIO = Path(__file__).with_name("gazebo_scenario.yaml")


def run_gazebo(scenario_path: Path, port: int, headless: bool) -> int:
    scenario = load_scenario(scenario_path)
    metadata = yaml.safe_load(scenario_path.read_text())
    world_map = scenario_path.parent / metadata["map"]
    keepout_map = scenario_path.parent / metadata["keepout"]
    description = Path(get_package_share_directory("pinky_description"))
    navigation = Path(get_package_share_directory("pinky_navigation"))
    urdf = subprocess.check_output(
        ["xacro", str(description / "urdf/robot.urdf.xacro"), "is_sim:=true"],
        text=True,
        timeout=10,
    )
    env = dict(
        os.environ,
        GZ_PARTITION=f"cas_fleet_{uuid4().hex}",
        GZ_SIM_RESOURCE_PATH=str(description.parent),
        ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST",
        ROS_STATIC_PEERS="",
    )
    env.pop("ROS_LOCALHOST_ONLY", None)
    worker_envs = {}
    processes: list[subprocess.Popen[bytes]] = []

    def launch(args: list[str], process_env: dict[str, str]) -> None:
        processes.append(
            subprocess.Popen(args, env=process_env, start_new_session=True)
        )

    with TemporaryDirectory(prefix="cas-gazebo-") as temp:
        workdir = Path(temp)
        world = workdir / "fleet.sdf"
        world_from_map(world_map, keepout_map, world)
        try:
            launch(["gz", "sim", "-s", "-r", "--headless-rendering", str(world)], env)
            for robot_id, route in scenario.routes.items():
                robot_env = dict(env, ROS_DOMAIN_ID=SIM_DOMAINS[robot_id])
                worker_envs[robot_id] = robot_env
                model = workdir / f"{robot_id}.urdf"
                robot_urdf = robot_description(urdf, robot_id)
                model.write_text(robot_urdf)
                start = route.start
                subprocess.run(
                    [
                        "ros2",
                        "run",
                        "ros_gz_sim",
                        "create",
                        "-world",
                        WORLD_NAME,
                        "-name",
                        robot_id,
                        "-file",
                        str(model),
                        "-x",
                        str(start.x_m),
                        "-y",
                        str(start.y_m),
                        "-z",
                        "0.01",
                        "-Y",
                        str(start.yaw_rad),
                    ],
                    env=robot_env,
                    timeout=25,
                    check=True,
                )
                bridge = workdir / f"{robot_id}_bridge.yaml"
                params = workdir / f"{robot_id}_nav.yaml"
                state_params = workdir / f"{robot_id}_state.yaml"
                bridge_config(robot_id, bridge)
                nav2_config(navigation / "params/nav2_params.yaml", start, params)
                state_params.write_text(
                    yaml.safe_dump(
                        {
                            "robot_state_publisher": {
                                "ros__parameters": {
                                    "robot_description": robot_urdf,
                                    "use_sim_time": True,
                                }
                            },
                        }
                    )
                )
                launch(
                    [
                        "ros2",
                        "run",
                        "robot_state_publisher",
                        "robot_state_publisher",
                        "--ros-args",
                        "--params-file",
                        str(state_params),
                    ],
                    robot_env,
                )
                launch(
                    [
                        "ros2",
                        "run",
                        "ros_gz_bridge",
                        "parameter_bridge",
                        "--ros-args",
                        "-p",
                        f"config_file:={bridge}",
                    ],
                    robot_env,
                )
                _launch_keepout(launch, robot_env, keepout_map)
                launch(
                    [
                        "ros2",
                        "launch",
                        "pinky_navigation",
                        "gz_bringup_launch.xml",
                        f"map:={world_map}",
                        f"params_file:={params}",
                        "lifecycle_nodes_local:=['map_server', 'amcl', 'keepout_mask', 'keepout_info']",
                        "log_level:=warn",
                    ],
                    robot_env,
                )
            dependencies = tuple(processes)
            if not headless:
                gui_config = workdir / "gui.config"
                map_view_config(world_map, gui_config)
                launch(["gz", "sim", "-g", "--gui-config", str(gui_config)], env)
            return run_demo(
                scenario_path,
                port,
                worker_envs=worker_envs,
                dependencies=dependencies,
                headless=headless,
            )
        finally:
            for process in reversed(processes):
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
            for process in reversed(processes):
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def _launch_keepout(
    launch: Callable[[list[str], dict[str, str]], None], env: dict[str, str], mask: Path
) -> None:
    launch(
        [
            "ros2",
            "run",
            "nav2_map_server",
            "map_server",
            "--ros-args",
            "-r",
            "__node:=keepout_mask",
            "-p",
            "topic_name:=/keepout_filter_mask",
            "-p",
            "use_sim_time:=true",
            "-p",
            f"yaml_filename:={mask}",
        ],
        env,
    )
    launch(
        [
            "ros2",
            "run",
            "nav2_map_server",
            "costmap_filter_info_server",
            "--ros-args",
            "-r",
            "__node:=keepout_info",
            "-p",
            "type:=0",
            "-p",
            "use_sim_time:=true",
            "-p",
            "filter_info_topic:=/keepout_filter_info",
            "-p",
            "mask_topic:=/keepout_filter_mask",
            "-p",
            "base:=0.0",
            "-p",
            "multiplier:=1.0",
        ],
        env,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the CAS FMS two-Pinky Gazebo demo"
    )
    parser.add_argument("--scenario", type=Path, default=GAZEBO_SCENARIO)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run_gazebo(args.scenario.resolve(), args.port, args.headless))
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()

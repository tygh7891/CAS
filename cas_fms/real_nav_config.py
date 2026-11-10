import argparse
from pathlib import Path
from typing import Any

import yaml

BASE_PARAMS = (
    Path(__file__).resolve().parent.parent / "pinky_navigation/params/nav2_params.yaml"
)


def enable_keepout_filters(config: dict[str, Any]) -> None:
    for name in ("global_costmap", "local_costmap"):
        params = config[name][name]["ros__parameters"]
        if "keepout_filter" not in params.setdefault("filters", []):
            params["filters"].append("keepout_filter")
        params["keepout_filter"] = {
            "plugin": "nav2_costmap_2d::KeepoutFilter",
            "enabled": True,
            "filter_info_topic": "/keepout_filter_info",
        }


def write_real_nav_params(base: Path, output: Path) -> None:
    config = yaml.safe_load(base.read_text())
    enable_keepout_filters(config)
    config["amcl"]["ros__parameters"]["set_initial_pose"] = False
    for name in ("controller_server", "behavior_server", "velocity_smoother"):
        config[name]["ros__parameters"]["enable_stamped_cmd_vel"] = False
    controller = config["controller_server"]["ros__parameters"]
    controller["FollowPath"]["desired_linear_vel"] = 0.10
    controller["general_goal_checker"]["xy_goal_tolerance"] = 0.015
    controller["progress_checker"]["required_movement_radius"] = 0.05
    config["behavior_server"]["ros__parameters"]["max_rotational_vel"] = 0.60
    config["velocity_smoother"]["ros__parameters"].update(
        velocity_timeout=0.5,
        max_velocity=[0.10, 0.0, 0.60],
        min_velocity=[-0.10, 0.0, -0.60],
    )
    output.write_text(yaml.safe_dump(config))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the robot's FMS Nav2 settings"
    )
    parser.add_argument("--base", type=Path, default=BASE_PARAMS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_real_nav_params(args.base, args.output)


if __name__ == "__main__":
    main()

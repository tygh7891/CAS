from pathlib import Path

import yaml

from fms_geometry import Pose
from real_nav_config import enable_keepout_filters


def nav2_config(base: Path, start: Pose, output: Path) -> None:
    """Adapt the existing Pinky Nav2 settings to the shared centimetre-scale map."""
    config = yaml.safe_load(base.read_text())
    enable_keepout_filters(config)
    amcl = config["amcl"]["ros__parameters"]
    amcl.update(
        initial_pose={"x": start.x_m, "y": start.y_m, "z": 0.0, "yaw": start.yaw_rad},
        update_min_d=0.02,
        update_min_a=0.08,
        sigma_hit=0.035,
        laser_min_range=0.09,
        alpha1=0.003,
        alpha2=0.003,
        alpha3=0.003,
        alpha4=0.003,
    )
    controller = config["controller_server"]["ros__parameters"]
    controller["general_goal_checker"].update(
        xy_goal_tolerance=0.012, yaw_goal_tolerance=0.065
    )
    controller["progress_checker"].update(required_movement_radius=0.035)
    controller["FollowPath"].update(
        desired_linear_vel=0.16,
        lookahead_dist=0.15,
        min_lookahead_dist=0.08,
        max_lookahead_dist=0.20,
        approach_velocity_scaling_dist=0.18,
        cost_scaling_dist=0.10,
    )
    for name in ("global_costmap", "local_costmap"):
        costmap = config[name][name]["ros__parameters"]
        costmap.update(resolution=0.01, footprint_padding=0.0)
        costmap["inflation_layer"]["inflation_radius"] = 0.10
    local = config["local_costmap"]["local_costmap"]["ros__parameters"]
    local.update(width=2, height=2, plugins=["static_layer", *local["plugins"]])
    local["voxel_layer"]["publish_voxel_map"] = False
    local["voxel_layer"]["scan"]["obstacle_min_range"] = 0.09
    global_map = config["global_costmap"]["global_costmap"]["ros__parameters"]
    global_map["obstacle_layer"]["scan"]["obstacle_min_range"] = 0.09
    config["planner_server"]["ros__parameters"]["GridBased"].update(
        tolerance=0.01, allow_unknown=False
    )
    output.write_text(yaml.safe_dump(config))


def bridge_config(robot_id: str, output: Path) -> None:
    topics = (
        ("clock", "/clock", "rosgraph_msgs/msg/Clock", "Clock"),
        ("tf", f"/{robot_id}/tf", "tf2_msgs/msg/TFMessage", "Pose_V"),
        ("scan", f"/{robot_id}/scan", "sensor_msgs/msg/LaserScan", "LaserScan"),
        ("odom", f"/{robot_id}/odom", "nav_msgs/msg/Odometry", "Odometry"),
        (
            "joint_states",
            f"/{robot_id}/joint_states",
            "sensor_msgs/msg/JointState",
            "Model",
        ),
        ("fms_cmd_vel", f"/{robot_id}/cmd_vel", "geometry_msgs/msg/Twist", "Twist"),
    )
    bridges = [
        {
            "ros_topic_name": f"/{ros_topic}",
            "gz_topic_name": gz_topic,
            "ros_type_name": ros_type,
            "gz_type_name": f"gz.msgs.{gz_type}",
            "direction": "ROS_TO_GZ" if ros_topic == "fms_cmd_vel" else "GZ_TO_ROS",
        }
        for ros_topic, gz_topic, ros_type, gz_type in topics
    ]
    output.write_text(yaml.safe_dump(bridges))

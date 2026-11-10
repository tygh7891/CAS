#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OPERATOR_DIR="$(cd -- "$SCRIPT_DIR/../operator_app" && pwd)"
export ROS_DOMAIN_ID=84 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp SKIP_DEFAULT_XML=1
unset ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_AUTOMATIC_DISCOVERY_RANGE FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
CAS_SIM_WS="${CAS_SIM_WS:-$HOME/CAS_sim_ws}"
export ROS_LOG_DIR="$CAS_SIM_WS/ros_logs"
mkdir -p "$ROS_LOG_DIR"
set +u
source /opt/ros/jazzy/setup.bash
set -u
exec /usr/bin/python3 "$OPERATOR_DIR/launch.py" --sim-nav2 --generated-dir "$CAS_SIM_WS/generated_map" "$@"

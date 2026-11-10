#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAS_SIM_WS="${CAS_SIM_WS:-$HOME/CAS_sim_ws}"
export ROS_DOMAIN_ID=84 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp SKIP_DEFAULT_XML=1
unset ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_AUTOMATIC_DISCOVERY_RANGE FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export ROS_LOG_DIR="$CAS_SIM_WS/ros_logs"
mkdir -p "$ROS_LOG_DIR"
set +u
source /opt/ros/jazzy/setup.bash
source "$CAS_SIM_WS/install/local_setup.bash"
set -u
exec /usr/bin/python3 "$SCRIPT_DIR/check_sim.py"

#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Only this subprocess changes discovery range; user's terminal settings are unchanged.
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
set +u
source /opt/ros/jazzy/setup.bash
set -u
/usr/bin/python3 -u "$SCRIPT_DIR/probe.py" --robot robot_1 --domain 14
/usr/bin/python3 -u "$SCRIPT_DIR/probe.py" --robot robot_2 --domain 30

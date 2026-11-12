#!/usr/bin/env bash
set -euo pipefail
CAS_APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
set +u
source /opt/ros/jazzy/setup.bash
set -u
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
exec /usr/bin/python3 "$CAS_APP_DIR/launch.py" "$@"

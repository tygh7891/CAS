#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CAS_SIM_WS="${CAS_SIM_WS:-$HOME/CAS_sim_ws}"
# Subprocess-local settings: never changes the user's other terminals.
export ROS_DOMAIN_ID=84
export ROS_LOCALHOST_ONLY=1
unset ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_AUTOMATIC_DISCOVERY_RANGE
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export SKIP_DEFAULT_XML=1
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export GZ_PARTITION=cas_independent_b2
export GZ_IP=127.0.0.1
export GZ_SIM_RESOURCE_PATH="$CAS_SIM_WS/install/pinky_description/share:$CAS_SIM_WS/install/pinky_gz_sim/share"
export ROS_LOG_DIR="$CAS_SIM_WS/ros_logs"
mkdir -p "$ROS_LOG_DIR"
set +u
source /opt/ros/jazzy/setup.bash
if [[ ! -f "$CAS_SIM_WS/install/local_setup.bash" ]]; then
  echo "시뮬레이션 빌드 결과가 없습니다: $CAS_SIM_WS/install/local_setup.bash"; exit 1
fi
source "$CAS_SIM_WS/install/local_setup.bash"
set -u
CAS_GENERATED_DIR="$CAS_SIM_WS/generated"
if [[ -n "${CAS_MAP_YAML:-}" ]]; then
  : "${CAS_MASK_YAML:?CAS_MASK_YAML must specify the allowed-lane YAML}"
  CAS_GENERATED_DIR="$CAS_SIM_WS/generated_map"
  /usr/bin/python3 "$SCRIPT_DIR/prepare_map.py" --output "$CAS_GENERATED_DIR" --map "$CAS_MAP_YAML" --mask "$CAS_MASK_YAML"
else
  /usr/bin/python3 "$SCRIPT_DIR/prepare.py" --output "$CAS_GENERATED_DIR"
fi
echo 'CAS B2: Gazebo 시험 공간 · 도메인 84 · 실물 14/30과 분리 · 이동 명령 없음'
exec /opt/ros/jazzy/bin/ros2 launch "$SCRIPT_DIR/two_robots.launch.py" generated_dir:="$CAS_GENERATED_DIR" "$@"

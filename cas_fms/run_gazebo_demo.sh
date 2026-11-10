#!/usr/bin/env bash
set -eo pipefail

demo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=${CAS_GAZEBO_BUILD_DIR:-"$demo_dir/.gazebo_build"}

source /opt/ros/jazzy/setup.bash
colcon --log-base "$build_dir/log" build \
    --base-paths "$demo_dir/../pinky_description" "$demo_dir/../pinky_navigation" \
    --build-base "$build_dir/build" --install-base "$build_dir/install" --symlink-install
source "$build_dir/install/local_setup.bash"

cd -- "$demo_dir"
exec /usr/bin/python3 -m gazebo_demo "$@"

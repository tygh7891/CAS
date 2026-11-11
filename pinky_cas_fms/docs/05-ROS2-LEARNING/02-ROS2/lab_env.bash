#!/usr/bin/env bash
# Bash에서 도메인 번호를 인수로 주고 source한다. 같은 컴퓨터의 실습용이다.
case "${1-}" in
    51|52) ;;
    *) printf '실습 도메인은 51 또는 52를 지정하세요.\n' >&2; return 2 ;;
esac
source /opt/ros/jazzy/setup.bash || return
unset ROS_LOCALHOST_ONLY
export ROS_STATIC_PEERS=''
export ROS_DOMAIN_ID="$1"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST

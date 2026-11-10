"""PC-only mock ROS settings; call before importing/initializing rclpy."""
import os

ROBOTS = {'robot_1': 14, 'robot_2': 30}
PREFIX = '/cas_mock'

def configure(robot):
    if robot not in ROBOTS:
        raise ValueError('Unknown mock robot')
    os.environ['ROS_DOMAIN_ID'] = str(ROBOTS[robot])
    os.environ['ROS_LOCALHOST_ONLY'] = '1'
    os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    os.environ['RMW_IMPLEMENTATION'] = 'rmw_fastrtps_cpp'
    for key in ('ROS_STATIC_PEERS', 'ROS_DISCOVERY_SERVER', 'FASTDDS_DEFAULT_PROFILES_FILE',
                'FASTRTPS_DEFAULT_PROFILES_FILE', 'CYCLONEDDS_URI'):
        os.environ.pop(key, None)
    os.environ['SKIP_DEFAULT_XML'] = '1'
    return ROBOTS[robot]

"""B3 localization / Nav2 readiness only. Velocity output cannot reach Gazebo."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def configuration(folder, robot):
    report = json.loads((folder / 'map_profile_report.json').read_text())
    world = ET.parse(folder / 'connection_test.sdf')
    pose = [float(v) for v in world.find(f".//world/model[@name='{robot}']/pose").text.split()]
    defaults = Path(get_package_share_directory('nav2_bringup')) / 'params/nav2_params.yaml'
    data = yaml.safe_load(defaults.read_text())
    names = ['amcl', 'bt_navigator', 'controller_server', 'planner_server',
             'behavior_server', 'smoother_server', 'velocity_smoother']
    out = {}
    for name in names:
        params = copy.deepcopy(data[name]['ros__parameters'])
        params['use_sim_time'] = True
        out[f'/{robot}/{name}'] = {'ros__parameters': params}
    def p(name):
        return out[f'/{robot}/{name}']['ros__parameters']
    p('amcl').update(base_frame_id=f'{robot}/base_footprint', odom_frame_id=f'{robot}/odom',
                     global_frame_id='map', scan_topic=f'/{robot}/scan', set_initial_pose=True,
                     initial_pose={'x': pose[0], 'y': pose[1], 'z': 0.0, 'yaw': pose[5]},
                     update_min_d=0.02, update_min_a=0.05, sigma_hit=0.03)
    p('bt_navigator').update(robot_base_frame=f'{robot}/base_footprint', odom_topic=f'/{robot}/odom')
    c = p('controller_server')
    c.update(odom_topic=f'/{robot}/odom', controller_frequency=10.0,
             controller_plugins=['FollowPath'])
    c['progress_checker'].update(required_movement_radius=0.03, movement_time_allowance=15.0)
    c['general_goal_checker'].update(xy_goal_tolerance=0.04, yaw_goal_tolerance=0.15)
    c['FollowPath'] = dict(plugin='nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController',
                          desired_linear_vel=0.08, lookahead_dist=0.15, min_lookahead_dist=0.10,
                          max_lookahead_dist=0.25, rotate_to_heading_angular_vel=0.4,
                          use_velocity_scaled_lookahead_dist=False, use_collision_detection=True,
                          max_allowed_time_to_collision_up_to_carrot=1.0,
                          regulated_linear_scaling_min_radius=0.2,
                          regulated_linear_scaling_min_speed=0.03,
                          cost_scaling_dist=0.10, inflation_cost_scaling_factor=15.0)
    p('planner_server').update(planner_plugins=['GridBased'])
    p('planner_server')['GridBased'] = dict(plugin='nav2_navfn_planner::NavfnPlanner', tolerance=0.03,
                                           use_astar=False, allow_unknown=False)
    p('behavior_server').update(local_frame=f'{robot}/odom', robot_base_frame=f'{robot}/base_footprint',
                                max_rotational_vel=0.4, min_rotational_vel=0.1,
                                behavior_plugins=['spin', 'backup', 'drive_on_heading', 'wait'])
    p('velocity_smoother').update(odom_topic=f'/{robot}/odom', max_velocity=[0.08, 0.0, 0.4],
                                  min_velocity=[-0.08, 0.0, -0.4], enable_stamped_cmd_vel=False)
    for scope in ['local', 'global']:
        cost = dict(use_sim_time=True, global_frame='map' if scope == 'global' else f'{robot}/odom',
                    robot_base_frame=f'{robot}/base_footprint', resolution=0.01, robot_radius=0.10,
                    update_frequency=5.0, publish_frequency=2.0, transform_tolerance=0.5,
                    plugins=['static_layer', 'obstacle_layer', 'inflation_layer'],
                    filters=['keepout_filter', 'keepout_inflation'], always_send_full_costmap=True,
                    static_layer=dict(plugin='nav2_costmap_2d::StaticLayer', map_subscribe_transient_local=True,
                                      map_topic=f'/{robot}/map'),
                    obstacle_layer=dict(plugin='nav2_costmap_2d::ObstacleLayer', observation_sources='scan',
                                        scan=dict(topic=f'/{robot}/scan', data_type='LaserScan', clearing=True,
                                                  marking=True, raytrace_max_range=3.0, obstacle_max_range=2.5)),
                    inflation_layer=dict(plugin='nav2_costmap_2d::InflationLayer', inflation_radius=0.12,
                                         cost_scaling_factor=15.0),
                    keepout_filter=dict(plugin='nav2_costmap_2d::KeepoutFilter', enabled=True,
                                        filter_info_topic=f'/{robot}/costmap_filter_info'),
                    keepout_inflation=dict(plugin='nav2_costmap_2d::InflationLayer', inflation_radius=0.12,
                                           cost_scaling_factor=15.0))
        if scope == 'local':
            cost.update(rolling_window=True, width=1, height=1)
        else:
            cost.update(track_unknown_space=True)
        out[f'/{robot}/{scope}_costmap/{scope}_costmap'] = {'ros__parameters': cost}
    for name, file, topic in [('map_server', report['source_map'], 'map'),
                               ('keepout_mask_server', str(folder / 'nav2_keepout_draft.yaml'), 'keepout_mask')]:
        out[f'/{robot}/{name}'] = {'ros__parameters': dict(use_sim_time=True, yaml_filename=file,
                                                          topic_name=topic, frame_id='map')}
    out[f'/{robot}/costmap_filter_info_server'] = {'ros__parameters': dict(use_sim_time=True, type=0,
        filter_info_topic=f'/{robot}/costmap_filter_info', mask_topic=f'/{robot}/keepout_mask', base=0.0, multiplier=1.0)}
    return out


def setup(context):
    folder = Path(LaunchConfiguration('generated_dir').perform(context)).expanduser().resolve()
    actions = []
    executables = dict(map_server=('nav2_map_server', 'map_server'),
                       keepout_mask_server=('nav2_map_server', 'map_server'),
                       costmap_filter_info_server=('nav2_map_server', 'costmap_filter_info_server'),
                       amcl=('nav2_amcl', 'amcl'), planner_server=('nav2_planner', 'planner_server'),
                       controller_server=('nav2_controller', 'controller_server'),
                       smoother_server=('nav2_smoother', 'smoother_server'),
                       behavior_server=('nav2_behaviors', 'behavior_server'),
                       bt_navigator=('nav2_bt_navigator', 'bt_navigator'),
                       velocity_smoother=('nav2_velocity_smoother', 'velocity_smoother'))
    for robot in ['robot_1', 'robot_2']:
        params = folder / f'{robot}.nav2_preview.yaml'
        params.write_text(yaml.safe_dump(configuration(folder, robot), sort_keys=False))
        tf = [('/tf', f'/{robot}/tf'), ('/tf_static', f'/{robot}/tf_static')]
        for name, (package, executable) in executables.items():
            remaps = list(tf)
            if name in ['controller_server', 'behavior_server']:
                remaps += [('cmd_vel', f'/{robot}/cmd_vel_nav')]
            if name == 'velocity_smoother':
                remaps += [('cmd_vel', f'/{robot}/cmd_vel_nav'),
                           ('cmd_vel_smoothed', f'/{robot}/nav2_preview_cmd_vel')]
            actions.append(Node(package=package, executable=executable, namespace=robot,
                                name=name, parameters=[str(params)], remappings=remaps, output='screen'))
        actions.append(Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                            namespace=robot, name='lifecycle_manager_preview', output='screen',
                            parameters=[dict(use_sim_time=True, autostart=True, node_names=list(executables))]))
    print('CAS B3: PREVIEW ONLY. Velocity output disconnected from Gazebo. No goals sent.')
    return actions


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('generated_dir'), OpaqueFunction(function=setup)])

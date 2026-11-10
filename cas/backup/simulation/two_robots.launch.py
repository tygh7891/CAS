"""One shared Gazebo world, two isolated robot namespaces. No motion commands."""
from pathlib import Path
import xml.etree.ElementTree as ET
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,ExecuteProcess,OpaqueFunction,RegisterEventHandler,EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

def setup(context):
    output=Path(LaunchConfiguration('generated_dir').perform(context)).expanduser().resolve()
    world=output/'connection_test.sdf';bridge=output/'bridge.yaml'
    for p in [world,bridge,output/'robot_1.urdf',output/'robot_2.urdf']:
        if not p.is_file():raise FileNotFoundError(f'Run prepare.py first: {p}')
    gui=LaunchConfiguration('gui').perform(context).lower()=='true'
    simulation=ExecuteProcess(cmd=['gz','sim','-r',* ([] if gui else ['-s']),'-v','3',str(world)],output='screen')
    actions=[simulation,RegisterEventHandler(OnProcessExit(target_action=simulation,on_exit=[EmitEvent(event=Shutdown(reason='Gazebo process exited'))]))]
    actions.append(Node(package='ros_gz_bridge',executable='parameter_bridge',name='cas_gazebo_bridge',
                        parameters=[{'config_file':str(bridge),'use_sim_time':True}],output='screen'))
    for name in ['robot_1','robot_2']:
        urdf=(output/f'{name}.urdf').read_text()
        actions.append(Node(package='robot_state_publisher',executable='robot_state_publisher',
                            namespace=name,name='robot_state_publisher',
                            parameters=[{'robot_description':ParameterValue(urdf,value_type=str),'use_sim_time':True}],
                            remappings=[('/tf','tf'),('/tf_static','tf_static')],output='screen'))
    print('CAS simulation: domain 84; localhost; robot_1/* and robot_2/*; no Nav2, GUI control, or motion publisher')
    return actions

def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('generated_dir'),DeclareLaunchArgument('gui',default_value='true'),OpaqueFunction(function=setup)])

#!/usr/bin/env python3
"""Generate a two-robot Gazebo test world offline. Does not start simulation."""
import argparse
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import yaml

ROBOTS=('robot_1','robot_2')
WORLD_NAME='cas_connection_test'

def prefix_urdf(xml,name,description_share):
    root=ET.fromstring(xml);root.set('name',name)
    names={e.get('name'):name+'/'+e.get('name') for e in root if e.tag in ('link','joint')}
    for e in root:
        if e.tag in ('link','joint'):e.set('name',names[e.get('name')])
    for e in root.iter():
        if e.tag in ('parent','child') and 'link' in e.attrib:e.set('link',names[e.get('link')])
        if e.tag=='gazebo' and e.get('reference') in names:e.set('reference',names[e.get('reference')])
        if e.tag=='mesh' and e.get('filename','').startswith('package://pinky_description/'):
            relative=e.get('filename').removeprefix('package://pinky_description/')
            path=Path(description_share)/relative
            if not path.is_file():raise FileNotFoundError(path)
            e.set('filename',path.as_uri())
    # Only lidar is required for B2; no camera/IMU/lamp controller in this test.
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag=='sensor' and child.get('type')!='gpu_lidar':parent.remove(child)
            elif child.tag=='plugin' and 'lamp-control' in child.get('filename',''):parent.remove(child)
    for e in root.iter():
        if e.tag in ('left_joint','right_joint','joint_name') and e.text in names:e.text=names[e.text]
        if e.tag in ('frame_id','child_frame_id','gz_frame_id') and e.text:e.text=name+'/'+e.text.lstrip('/')
        if e.tag in ('topic','odom_topic','tf_topic') and e.text:e.text='/'+name+'/'+e.text.lstrip('/')
    links={e.get('name') for e in root.findall('link')}
    joints={e.get('name') for e in root.findall('joint')}
    for joint in root.findall('joint'):
        for tag in ('parent','child'):
            assert joint.find(tag).get('link') in links
    for e in root.findall('.//left_joint')+root.findall('.//right_joint'):
        assert e.text in joints
    return ET.tostring(root,encoding='unicode')

def bridge_config():
    result=[dict(ros_topic_name='/clock',gz_topic_name='/clock',ros_type_name='rosgraph_msgs/msg/Clock',gz_type_name='gz.msgs.Clock',direction='GZ_TO_ROS')]
    for robot in ROBOTS:
        for topic,ros,gz,direction in [
            ('cmd_vel','geometry_msgs/msg/Twist','gz.msgs.Twist','ROS_TO_GZ'),
            ('odom','nav_msgs/msg/Odometry','gz.msgs.Odometry','GZ_TO_ROS'),
            ('scan','sensor_msgs/msg/LaserScan','gz.msgs.LaserScan','GZ_TO_ROS'),
            ('joint_states','sensor_msgs/msg/JointState','gz.msgs.Model','GZ_TO_ROS'),
            ('tf','tf2_msgs/msg/TFMessage','gz.msgs.Pose_V','GZ_TO_ROS')]:
            result.append(dict(ros_topic_name=f'/{robot}/{topic}',gz_topic_name=f'/{robot}/{topic}',ros_type_name=ros,gz_type_name=gz,direction=direction))
    return result

def world_tree():
    root=ET.Element('sdf',version='1.9');world=ET.SubElement(root,'world',name=WORLD_NAME)
    for filename,name in [('physics','Physics'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster'),('sensors','Sensors')]:
        p=ET.SubElement(world,'plugin',filename=f'gz-sim-{filename}-system',name=f'gz::sim::systems::{name}')
        if name=='Sensors':ET.SubElement(p,'render_engine').text='ogre2'
    physics=ET.SubElement(world,'physics',name='1ms',type='ignored')
    ET.SubElement(physics,'max_step_size').text='0.001';ET.SubElement(physics,'real_time_factor').text='1'
    light=ET.SubElement(world,'light',name='sun',type='directional');ET.SubElement(light,'pose').text='0 0 4 0 0 0'
    ET.SubElement(light,'diffuse').text='0.9 0.9 0.9 1';ET.SubElement(light,'direction').text='-0.5 0.1 -0.9'
    def box(name,pose,size,color):
        model=ET.SubElement(world,'model',name=name);ET.SubElement(model,'static').text='true';ET.SubElement(model,'pose').text=pose
        link=ET.SubElement(model,'link',name='body')
        for kind in ['collision','visual']:
            e=ET.SubElement(link,kind,name=kind);geometry=ET.SubElement(e,'geometry');b=ET.SubElement(geometry,'box');ET.SubElement(b,'size').text=size
            if kind=='visual':
                material=ET.SubElement(e,'material');ET.SubElement(material,'ambient').text=color;ET.SubElement(material,'diffuse').text=color
    box('floor','0 0 -0.05 0 0 0','4 3 0.1','0.8 0.82 0.85 1')
    for name,pose,size in [('north','0 1.45 0.2 0 0 0','4 .1 .4'),('south','0 -1.45 .2 0 0 0','4 .1 .4'),('west','-1.95 0 .2 0 0 0','.1 3 .4'),('east','1.95 0 .2 0 0 0','.1 3 .4')]:box(name,pose,size,'0.45 0.5 0.6 1')
    scene=ET.SubElement(world,'scene');ET.SubElement(scene,'ambient').text='0.7 0.7 0.7 1';ET.SubElement(scene,'background').text='0.85 0.9 0.95 1'
    return root,world

def prepare(output, world_builder=None, spawn_poses=None):
    from ament_index_python.packages import get_package_share_directory
    import xacro
    output=Path(output).expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    description=Path(get_package_share_directory('pinky_description'))
    source=description/'urdf/robot.urdf.xacro'
    baseline=xacro.process_file(str(source),mappings={'namespace':'','is_sim':'True','cam_tilt_deg':'0'}).toxml()
    root,world=(world_builder or world_tree)()
    for name,pose in (spawn_poses or [('robot_1','-0.45 -0.45 0.02 0 0 0'),('robot_2','0.45 -0.45 0.02 0 0 0')]):
        urdf=prefix_urdf(baseline,name,description);path=output/f'{name}.urdf';path.write_text(urdf)
        result=subprocess.run(['gz','sdf','-p',str(path)],capture_output=True,text=True,timeout=30,check=True)
        sdf=ET.fromstring(result.stdout);model=sdf.find('model')
        if model is None:raise ValueError('URDF to SDF did not produce a model')
        model.set('name',name)
        existing=model.find('pose')
        if existing is None:existing=ET.SubElement(model,'pose')
        existing.text=pose
        world.append(model)
        if result.stderr.strip():print(f'[{name} conversion] {result.stderr.strip()}')
    ET.indent(root)
    ET.ElementTree(root).write(output/'connection_test.sdf',encoding='unicode',xml_declaration=True)
    (output/'bridge.yaml').write_text(yaml.safe_dump(bridge_config(),sort_keys=False))
    print('PREPARED',output)
    print('Offline generation only. No processes or robots started.')
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();prepare(args.output)

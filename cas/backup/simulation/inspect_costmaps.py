"""Read-only costmap samples along the start of verified approach paths."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.time import Time
from nav2_worker import Nav2Worker
from zone_coordinator import MissionCoordinator
from check_workers import load_bundle


def yaw(q):return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


def sample(grid,transform,point):
    a=yaw(transform.transform.rotation);t=transform.transform.translation
    x=t.x+math.cos(a)*point[0]-math.sin(a)*point[1]
    y=t.y+math.sin(a)*point[0]+math.cos(a)*point[1]
    origin=grid.info.origin;b=yaw(origin.orientation)
    dx,dy=x-origin.position.x,y-origin.position.y
    col=math.floor((math.cos(b)*dx+math.sin(b)*dy)/grid.info.resolution)
    row=math.floor((-math.sin(b)*dx+math.cos(b)*dy)/grid.info.resolution)
    if not 0<=col<grid.info.width or not 0<=row<grid.info.height:return None
    return grid.data[row*grid.info.width+col]


def main():
    scenario,mission,report=load_bundle(Path.home()/'CAS_sim_ws/generated_map')
    coordinator=MissionCoordinator(mission,scenario['shared_zone']['polygon'])
    rclpy.init();executor=SingleThreadedExecutor();workers={};grids={};subscriptions=[]
    for robot in ['robot_1','robot_2']:
        worker=Nav2Worker(robot,coordinator);workers[robot]=worker;executor.add_node(worker)
        subscriptions.append(worker.create_subscription(OccupancyGrid,f'/{robot}/local_costmap/costmap',
            lambda msg,name=robot:grids.update({name:msg}),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)))
    try:
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            executor.spin_once(timeout_sec=.02)
            for worker in workers.values():worker.poll(time.monotonic())
        results={}
        for robot,worker in workers.items():
            grid=grids.get(robot)
            if grid is None:results[robot]=dict(error='No local costmap received');continue
            try:
                transform=worker.buffer.lookup_transform(grid.header.frame_id,'map',Time())
                path=mission[robot]['segments'][0]['path'];samples=[];distance=0
                for i,point in enumerate(path):
                    if i:distance+=math.dist(path[i-1],point)
                    if distance>.20:break
                    if i%3==0:samples.append(dict(distance_m=distance,point=point,cost=sample(grid,transform,point)))
                pose=coordinator.robots[robot]['pose']
                results[robot]=dict(frame=grid.header.frame_id,resolution=grid.info.resolution,
                                    pose=pose,pose_cost=sample(grid,transform,pose) if pose else None,
                                    approach_first_20cm=samples)
            except Exception as error:results[robot]=dict(error=str(error))
        payload=dict(source_report=report,cost_legend='0 free; 99 inscribed; 100 lethal; -1 unknown',robots=results)
        output=Path.home()/'CAS_sim_ws/generated_map/costmap_diagnostic.json'
        output.write_text(json.dumps(payload,indent=2))
        print(json.dumps(payload,indent=2));print('READ ONLY — NO GOALS SENT | '+str(output))
    finally:
        for worker in workers.values():executor.remove_node(worker);worker.destroy_node()
        executor.shutdown();rclpy.shutdown()


if __name__=='__main__':main()

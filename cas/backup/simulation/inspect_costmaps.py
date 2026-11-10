"""Read-only costmap samples along the start of verified approach paths."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PolygonStamped
from rcl_interfaces.srv import GetParameters
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
    rclpy.init();executor=SingleThreadedExecutor();workers={};grids={};footprints={};subscriptions=[];parameter_clients={};parameter_futures={}
    for robot in ['robot_1','robot_2']:
        worker=Nav2Worker(robot,coordinator);workers[robot]=worker;executor.add_node(worker)
        parameter_clients[robot]=worker.create_client(GetParameters,f'/{robot}/local_costmap/local_costmap/get_parameters')
        subscriptions.append(worker.create_subscription(PolygonStamped,f'/{robot}/local_costmap/published_footprint',lambda msg,name=robot:footprints.update({name:msg}),1))
        subscriptions.append(worker.create_subscription(OccupancyGrid,f'/{robot}/local_costmap/costmap',
            lambda msg,name=robot:grids.update({name:msg}),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)))
    try:
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            executor.spin_once(timeout_sec=.02)
            for robot,worker in workers.items():
                worker.poll(time.monotonic())
                if robot not in parameter_futures and parameter_clients[robot].service_is_ready():
                    request=GetParameters.Request();request.names=['robot_radius','footprint_padding']
                    parameter_futures[robot]=parameter_clients[robot].call_async(request)
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
                footprint=footprints.get(robot);body={}
                if footprint is not None:
                    body_transform=worker.buffer.lookup_transform(grid.header.frame_id,footprint.header.frame_id,Time())
                    base=worker.buffer.lookup_transform(footprint.header.frame_id,f'{robot}/base_footprint',Time())
                    points=footprint.polygon.points
                    costs=[sample(grid,body_transform,[p.x,p.y]) for p in points]
                    body=dict(frame=footprint.header.frame_id,vertices=len(points),
                              max_radius_m=max(math.hypot(p.x-base.transform.translation.x,p.y-base.transform.translation.y) for p in points),
                              vertex_costs=costs)
                parameters={}
                future=parameter_futures.get(robot)
                if future is not None and future.done():
                    parameters={name:value.double_value for name,value in zip(['robot_radius','footprint_padding'],future.result().values)}
                results[robot]=dict(applied_parameters=parameters,published_body=body,frame=grid.header.frame_id,resolution=grid.info.resolution,
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

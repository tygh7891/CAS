"""Unapproved segmented mission geometry, independent of ROS or motion transport."""
import math


def zone_distance(point, polygon):
    # Euclidean distance to a convex polygon; zero inside or on boundary.
    signs = []
    minimum = float('inf')
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        signs.append(dx*(point[1]-a[1])-dy*(point[0]-a[0]))
        t = max(0.0, min(1.0, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
        minimum = min(minimum, math.dist(point, (a[0]+t*dx,a[1]+t*dy)))
    return 0.0 if all(s>=0 for s in signs) or all(s<=0 for s in signs) else minimum


def routes(scenario, reference_paths):
    polygon = scenario['shared_zone']['polygon']
    radius = scenario['robot_radius_with_margin_m']
    # Add 8 cm beyond body radius: 4 cm goal tolerance plus extra reserve.
    separation = radius + .08
    result = {}
    for robot, start, target in [('robot_1','1','B'),('robot_2','2','A')]:
        begin = [scenario['points'][start][k] for k in ['x','y']]
        goal = [scenario['points'][target][k] for k in ['x','y']]
        path = reference_paths[robot]
        if not path or math.dist(path[0],begin)>.05 or math.dist(path[-1],goal)>.04:
            raise ValueError('Verified reference route endpoints differ: '+robot)
        overlaps = [i for i,p in enumerate(path) if zone_distance(p,polygon)<=radius]
        if not overlaps:raise ValueError('Reference route misses shared zone: '+robot)
        approach = [p for p in path[:min(overlaps)] if zone_distance(p,polygon)>=separation]
        departure = [p for p in path[max(overlaps)+1:] if zone_distance(p,polygon)>=separation]
        if not approach or not departure:raise ValueError('No waiting / exit reserve: '+robot)
        wait, exit_point = list(approach[-1]), list(departure[0])
        yaw = math.atan2(goal[1]-begin[1],goal[0]-begin[0])
        result[robot] = dict(start=begin,wait=wait,exit=exit_point,goal=goal,yaw=yaw,destination=target,
                            segments=[dict(name='approach',start=begin,goal=wait,requires_permission=False),
                                      dict(name='crossing',start=wait,goal=exit_point,requires_permission=True),
                                      dict(name='departure',start=exit_point,goal=goal,requires_permission=False)])
    return result

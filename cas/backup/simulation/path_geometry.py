"""Conservative raster footprint audit; checks every segment, not only vertices."""
import math
import numpy as np
from scipy.spatial import cKDTree


def inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            cross = a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x < cross:
                result = not result
    return result


def audit(points, spec, allowed, polygon, radius):
    if not points or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError('Empty or nonfinite path')
    # Pixel cells are closed rectangles, not point obstacles at their centers.
    # Include a blocked border so map edges are also excluded.
    blocked = np.argwhere(~np.pad(allowed, 1, constant_values=False))[:, ::-1] - .5
    tree = cKDTree(blocked)
    step = spec.resolution / 4
    samples = [points[0]]
    length = 0.0
    for a, b in zip(points, points[1:]):
        distance = math.dist(a, b)
        length += distance
        count = max(1, math.ceil(distance/step))
        samples.extend([(a[0]+(b[0]-a[0])*i/count, a[1]+(b[1]-a[1])*i/count) for i in range(1, count+1)])
    minimum = float('inf')
    center_allowed = True
    crosses = False
    for point in samples:
        u, v = spec.world_to_image(*point)
        col, row = math.floor(u), math.floor(v)
        if not (0 <= row < allowed.shape[0] and 0 <= col < allowed.shape[1]):
            center_allowed = False
            minimum = 0.0
        else:
            center_allowed = center_allowed and bool(allowed[row, col])
            query = np.array([u,v])
            nearest, _ = tree.query(query)
            # Any cell farther than nearest center + half diagonal cannot win.
            candidates = blocked[tree.query_ball_point(query, nearest+math.sqrt(.5)+1e-9)]
            distances = np.linalg.norm(np.maximum(np.abs(candidates-query)-.5, 0), axis=1)
            clearance = float(distances.min())*spec.resolution
            minimum = min(minimum, clearance)
        crosses = crosses or inside(point, polygon)
    # Distance to a closed obstacle set is 1-Lipschitz: cover unsampled gaps.
    lower_bound = max(0.0, minimum-step/2)
    return dict(length_m=length, vertices=len(points), samples=len(samples),
                center_in_allowed_lane=center_allowed,
                min_sample_clearance_m=minimum, min_clearance_lower_bound_m=lower_bound, required_radius_m=radius,
                footprint_clear=lower_bound >= radius, shared_zone_crossed=crosses)

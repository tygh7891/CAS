"""Conservative raster footprint audit; checks every segment, not only vertices."""
import math
import numpy as np
from scipy.ndimage import distance_transform_edt


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
    # EDT measures cell-center distance. Subtract cell uncertainty at both ends
    # and half the maximum sample step to conservatively cover whole segments.
    step = spec.resolution / 4
    field = distance_transform_edt(np.pad(allowed, 1, constant_values=False))[1:-1, 1:-1] * spec.resolution
    margin = math.sqrt(2)*spec.resolution + step/2
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
            minimum = min(minimum, max(0.0, float(field[row, col])-margin))
        crosses = crosses or inside(point, polygon)
    return dict(length_m=length, vertices=len(points), samples=len(samples),
                center_in_allowed_lane=center_allowed,
                min_clearance_lower_bound_m=minimum, required_radius_m=radius,
                footprint_clear=minimum >= radius, shared_zone_crossed=crosses)

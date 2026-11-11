"""위쪽에서 세는 이미지 픽셀을 회전 없는 지도의 목표 포즈로 바꾼다."""

import argparse
import json
import math


def cell_center(column, row, height, resolution, origin_x, origin_y):
    # 이미지 행은 위에서 아래로, 지도 y축은 아래에서 위로 증가한다.
    grid_y = height - 1 - row
    # 0.5를 더하면 픽셀 모서리 대신 셀 중앙을 가리킨다.
    return origin_x + (column + 0.5) * resolution, origin_y + (grid_y + 0.5) * resolution


def make_goal(x, y, yaw_deg):
    # 수평면 회전만 있으므로 쿼터니언 x와 y는 0이다.
    half_yaw = math.radians(yaw_deg) / 2
    return {
        "frame_id": "map",
        "position": {"x": round(x, 4), "y": round(y, 4), "z": 0.0},
        "orientation": {
            "x": 0.0, "y": 0.0,
            "z": round(math.sin(half_yaw), 6), "w": round(math.cos(half_yaw), 6),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--column", type=int, default=1)
    parser.add_argument("--row", type=int, default=0)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--height", type=int, default=3)
    parser.add_argument("--resolution", type=float, default=0.5)
    parser.add_argument("--origin-x", type=float, default=-1.0)
    parser.add_argument("--origin-y", type=float, default=-1.0)
    parser.add_argument("--yaw-deg", type=float, default=90.0)
    args = parser.parse_args()
    numeric = (args.resolution, args.origin_x, args.origin_y, args.yaw_deg)
    if not all(map(math.isfinite, numeric)) or args.resolution <= 0:
        parser.error("해상도는 양수, 원점과 각도는 유한한 수여야 합니다.")
    if not 0 <= args.column < args.width or not 0 <= args.row < args.height:
        parser.error("행과 열은 이미지 범위 안에 있어야 합니다.")

    x, y = cell_center(
        args.column, args.row, args.height, args.resolution, args.origin_x, args.origin_y
    )
    # 이 프로그램은 JSON을 보여준다. ROS 토픽이나 액션에 발행하지 않는다.
    print(json.dumps(make_goal(x, y, args.yaw_deg), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

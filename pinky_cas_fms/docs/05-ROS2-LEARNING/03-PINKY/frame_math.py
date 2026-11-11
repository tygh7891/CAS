"""로봇 기준의 센서 좌표를 지도 기준 좌표로 바꾸는 2차원 계산."""

import argparse
import math


def in_map(base_x, base_y, yaw_deg, sensor_x, sensor_y):
    yaw = math.radians(yaw_deg)
    # 센서 벡터를 먼저 로봇 방향만큼 회전한 뒤 지도 위 로봇 위치를 더한다.
    rotated_x = math.cos(yaw) * sensor_x - math.sin(yaw) * sensor_y
    rotated_y = math.sin(yaw) * sensor_x + math.cos(yaw) * sensor_y
    return base_x + rotated_x, base_y + rotated_y


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaw-deg", type=float, default=90.0)
    args = parser.parse_args()
    if not math.isfinite(args.yaw_deg):
        parser.error("유한한 각도를 입력하세요.")
    x, y = in_map(1.0, 2.0, args.yaw_deg, 0.25, 0.0)
    print(f"study_map 기준 sensor = ({x:.2f}, {y:.2f}) m")


if __name__ == "__main__":
    main()

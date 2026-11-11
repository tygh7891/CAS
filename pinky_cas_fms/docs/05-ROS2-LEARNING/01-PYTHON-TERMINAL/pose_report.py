"""숫자 세 개를 받아 로봇 위치 보고서의 JSON 한 줄을 만든다."""

import argparse
import json
import math


def make_report(x_m, y_m, yaw_deg):
    # 값에 붙인 단위를 보고 위치(m)와 각도(deg, rad)를 구분한다.
    return {
        "robot_id": "study_robot",
        "pose": {"x_m": x_m, "y_m": y_m, "yaw_rad": round(math.radians(yaw_deg), 4)},
        "distance_from_origin_m": round(math.hypot(x_m, y_m), 4),
    }


def main():
    # 셸은 문자열을 넘긴다. argparse가 float 변환과 도움말을 처리한다.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x", type=float, default=3.0)
    parser.add_argument("--y", type=float, default=4.0)
    parser.add_argument("--yaw-deg", type=float, default=90.0)
    args = parser.parse_args()
    if not all(math.isfinite(value) for value in (args.x, args.y, args.yaw_deg)):
        parser.error("좌표와 방향에는 유한한 숫자를 입력하세요.")

    # 딕셔너리는 Python 객체다. JSON으로 변환하면 다른 프로그램도 읽을 수 있다.
    print(json.dumps(make_report(args.x, args.y, args.yaw_deg), allow_nan=False))


if __name__ == "__main__":
    main()

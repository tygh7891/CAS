"""Pinky /scan에서 한 메시지를 받아 요약하고 종료한다."""

import math
from time import monotonic

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class ScanReport(Node):
    def __init__(self):
        super().__init__("study_scan_report")
        self.received = False
        # 센서 데이터용 QoS로 구독만 한다. 모터 명령을 발행하는 객체는 없다.
        self.subscription = self.create_subscription(
            LaserScan, "/scan", self.on_scan, qos_profile_sensor_data
        )

    def on_scan(self, scan):
        # 무한대와 센서의 유효 거리 범위 밖 값은 최솟값 계산에서 뺀다.
        valid = [
            distance
            for distance in scan.ranges
            if math.isfinite(distance) and scan.range_min <= distance <= scan.range_max
        ]
        nearest = f"{min(valid):.2f} m" if valid else "유효값 없음"
        print(f"frame={scan.header.frame_id} valid={len(valid)}/{len(scan.ranges)}")
        print(f"nearest={nearest}")
        self.received = True


def main():
    rclpy.init()
    node = ScanReport()
    deadline = monotonic() + 5.0
    try:
        while rclpy.ok() and not node.received and monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.25)
        if not node.received:
            print("5초 안에 /scan을 받지 못했습니다. 도메인과 라이다 노드를 확인하세요.")
            return 1
        return 0
    except (KeyboardInterrupt, ExternalShutdownException):
        return 130
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())

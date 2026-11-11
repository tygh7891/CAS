"""정수 하나씩을 초마다 학습용 토픽에 발행한다."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Int32


class Talker(Node):
    def __init__(self):
        super().__init__("study_talker")
        self.count = 0
        self.publisher = self.create_publisher(Int32, "/study/count", 10)
        # 타이머가 울릴 때마다 ROS 실행기가 send_count를 호출한다.
        self.timer = self.create_timer(1.0, self.send_count)

    def send_count(self):
        message = Int32()
        message.data = self.count
        self.publisher.publish(message)
        self.get_logger().info(f"sent {message.data}")
        self.count += 1


def main():
    rclpy.init()
    node = Talker()
    try:
        # spin은 여기서 타이머·수신 콜백을 처리한다.
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

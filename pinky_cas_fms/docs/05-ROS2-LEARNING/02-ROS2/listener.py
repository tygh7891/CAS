"""같은 이름과 타입으로 토픽을 구독하고 받은 정수를 보여준다."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Int32


class Listener(Node):
    def __init__(self):
        super().__init__("study_listener")
        # 메시지가 들어올 때 ROS 실행기가 show_count를 호출한다.
        self.subscription = self.create_subscription(Int32, "/study/count", self.show_count, 10)

    def show_count(self, message):
        self.get_logger().info(f"received {message.data}")


def main():
    rclpy.init()
    node = Listener()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

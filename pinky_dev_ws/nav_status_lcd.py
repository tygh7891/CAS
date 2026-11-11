#!/usr/bin/env python3
"""Small standalone LCD status display for Pinky Nav2.

Run this on the Raspberry Pi after sourcing ROS and the Pinky workspace.
It observes Nav2 actions; it never sends velocity or navigation commands.

The optional /lcd_status String topic overrides the observed state.  It lets a
future fleet-management server display states such as WAIT or CROSSING without
changing this program.
"""

from __future__ import annotations

import time

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from nav2_msgs.action import NavigateThroughPoses, NavigateToPose
from PIL import Image, ImageDraw, ImageFont
from rclpy.node import Node
from std_msgs.msg import String

from pinky_emotion.pinky_lcd import LCD


class NavStatusLcd(Node):
    """Translate Nav2 action state into a short, readable LCD status."""

    def __init__(self) -> None:
        super().__init__('nav_status_lcd')

        self.declare_parameter('robot_name', 'PINKY')
        self.declare_parameter('approach_distance', 0.15)
        self.declare_parameter('arrived_display_seconds', 3.0)

        self.robot_name = self.get_parameter('robot_name').value
        self.approach_distance = float(
            self.get_parameter('approach_distance').value)
        self.arrived_display_seconds = float(
            self.get_parameter('arrived_display_seconds').value)

        self.state = 'IDLE'
        self.distance_remaining: float | None = None
        self.arrived_at: float | None = None
        self.external_state: str | None = None
        self.last_rendered: str | None = None

        self.lcd = LCD()
        self.font_large = self._font(58)
        self.font_small = self._font(26)

        # Nav2's two normal navigation actions.
        self.create_subscription(
            NavigateToPose.Impl.FeedbackMessage,
            '/navigate_to_pose/_action/feedback',
            self._feedback_callback,
            10)
        self.create_subscription(
            NavigateThroughPoses.Impl.FeedbackMessage,
            '/navigate_through_poses/_action/feedback',
            self._feedback_callback,
            10)
        self.create_subscription(
            GoalStatusArray,
            '/navigate_to_pose/_action/status',
            self._status_callback,
            10)
        self.create_subscription(
            GoalStatusArray,
            '/navigate_through_poses/_action/status',
            self._status_callback,
            10)

        # Optional future FMS override: IDLE, RUN, WAIT, CROSSING, ARRIVED...
        self.create_subscription(String, '/lcd_status', self._external_status, 10)
        self.create_timer(0.20, self._tick)
        self._render(force=True)
        self.get_logger().info('LCD status display ready')

    @staticmethod
    def _font(size: int):
        for path in (
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
        ):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
        return ImageFont.load_default()

    def _feedback_callback(self, msg) -> None:
        distance = float(msg.feedback.distance_remaining)
        self.distance_remaining = distance
        self.arrived_at = None
        self.state = 'APPROACH' if distance <= self.approach_distance else 'RUN'

    def _status_callback(self, msg: GoalStatusArray) -> None:
        statuses = [entry.status for entry in msg.status_list]
        if GoalStatus.STATUS_EXECUTING in statuses:
            if self.state == 'IDLE':
                self.state = 'RUN'
            return

        if GoalStatus.STATUS_SUCCEEDED in statuses:
            self.state = 'ARRIVED'
            self.distance_remaining = 0.0
            self.arrived_at = time.monotonic()
            return

        if (GoalStatus.STATUS_ABORTED in statuses or
                GoalStatus.STATUS_CANCELED in statuses):
            self.state = 'IDLE'
            self.distance_remaining = None
            self.arrived_at = None

    def _external_status(self, msg: String) -> None:
        text = msg.data.strip().upper()
        # Send AUTO to resume the direct Nav2-derived display.
        self.external_state = None if text == 'AUTO' else text or None

    def _effective_state(self) -> str:
        if self.external_state:
            return self.external_state
        if self.state == 'ARRIVED' and self.arrived_at is not None:
            if time.monotonic() - self.arrived_at >= self.arrived_display_seconds:
                self.state = 'IDLE'
                self.distance_remaining = None
        return self.state

    def _tick(self) -> None:
        self._render()

    def _render(self, force: bool = False) -> None:
        state = self._effective_state()
        if not force and state == self.last_rendered:
            return

        colors = {
            'IDLE': (45, 90, 180),
            'RUN': (30, 170, 80),
            'APPROACH': (230, 145, 20),
            'ARRIVED': (20, 180, 190),
            'WAIT': (230, 145, 20),
            'CROSSING': (165, 75, 205),
        }
        color = colors.get(state, (180, 180, 180))
        image = Image.new('RGB', (320, 240), color=(12, 16, 24))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 319, 239), outline=color, width=8)
        self._center_text(draw, self.robot_name, 34, self.font_small, (220, 220, 220))
        self._center_text(draw, state, 88, self.font_large, color)
        self.lcd.img_show(image)
        self.last_rendered = state

    @staticmethod
    def _center_text(draw, text, y, font, fill) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        draw.text(((320 - width) // 2, y), text, font=font, fill=fill)

    def destroy_node(self):
        self.lcd.clear()
        self.lcd.close()
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = NavStatusLcd()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

from math import cos, sin
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fms_geometry import Pose
from fms_settings import DEMO_TITLES, DemoPreset, Route, Scenario

ROBOT_COLORS = {"robot_1": "#1479bd", "robot_2": "#9c3db6"}
PHASES = {
    "TO_WAIT": "대기점 이동",
    "APPROACH_ZONE": "교차로 접근",
    "WAITING_ZONE": "진입 대기",
    "CROSSING": "교차로 통과",
    "TO_GOAL": "목적지 이동",
    "SPINNING": "제자리 회전",
    "TO_START": "출발점 복귀",
    "TURN_AT_START": "출발 방향 복원",
}
STATES = {
    "IDLE": "준비",
    "RUNNING": "실행 중",
    "SUCCEEDED": "완료",
    "FAILED": "실패",
    "CANCELING": "취소 처리 중",
    "CANCELED": "취소",
}
TASK_ERRORS = {
    "WAYPOINT_NOT_REACHED": "Nav2 완료 보고 뒤 위치 또는 방향 오차를 확인했습니다.",
    "ZONE_NOT_TRAVERSED": "교차로 진입과 이탈을 확인하지 못했습니다.",
}


class MapView(QWidget):
    robot_selected = pyqtSignal(str)

    def __init__(self, scenario: Scenario) -> None:
        super().__init__()
        self.scenario = scenario
        self.world = QImage(str(scenario.world.image))
        mask = QImage(str(scenario.keepout.image))
        if self.world.isNull() or mask.isNull() or self.world.size() != mask.size():
            raise ValueError(
                "World map and keepout mask must be readable and same-sized"
            )
        self.floorplan = QImage(mask.size(), QImage.Format_RGB32)
        wall, floor = QColor("#93a4b9"), QColor("#fbfdff")
        restricted, hatch = QColor("#e3ebf4"), QColor("#d8e2ee")
        for y in range(mask.height()):
            for x in range(mask.width()):
                if self.world.pixelColor(x, y).red() < 90:
                    color = wall
                elif mask.pixelColor(x, y).red() < 128:
                    color = hatch if (x + y) % 7 == 0 else restricted
                else:
                    color = floor
                self.floorplan.setPixelColor(x, y, color)
        self.robots: list[dict[str, Any]] = []
        self.blocked = False
        self.selection: str | None = None
        self.setMinimumSize(360, 280)

    def update_status(self, robots: list[dict[str, Any]], blocked: bool) -> None:
        self.robots = robots
        self.blocked = blocked
        self.update()

    def _pixel(self, x_m: float, y_m: float) -> QPointF:
        origin_x, origin_y, _ = self.scenario.world.origin
        resolution = self.scenario.world.resolution
        return QPointF(
            (x_m - origin_x) / resolution,
            self.world.height() - (y_m - origin_y) / resolution,
        )

    def select_robot(self, robot_id: str | None) -> None:
        self.selection = robot_id
        self.update()

    def _viewport(self) -> tuple[float, QPointF]:
        scale = min(
            (self.width() - 16) / self.world.width(),
            (self.height() - 16) / self.world.height(),
        )
        return scale, QPointF(
            (self.width() - self.world.width() * scale) / 2,
            (self.height() - self.world.height() * scale) / 2,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            scale, origin = self._viewport()
            point = (event.localPos() - origin) / scale
            radius = self.scenario.robot_radius_m / self.scenario.world.resolution
            for robot in self.robots:
                if robot["pose"] is not None:
                    pose = Pose(**robot["pose"])
                    if (
                        point - self._pixel(pose.x_m, pose.y_m)
                    ).manhattanLength() <= radius * 1.3:
                        self.robot_selected.emit(robot["robot_id"])
                        return
        super().mousePressEvent(event)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#edf2f8"))
        scale, origin = self._viewport()
        painter.translate(origin)
        painter.scale(scale, scale)
        painter.drawImage(0, 0, self.floorplan)
        bounds = self.scenario.zone
        top_left = self._pixel(bounds.min_x, bounds.max_y)
        bottom_right = self._pixel(bounds.max_x, bounds.min_y)
        painter.setPen(
            QPen(QColor("#b43f2d" if self.blocked else "#966300"), 0.7, Qt.DashLine)
        )
        painter.setBrush(QColor(255, 191, 48, 48))
        painter.drawRect(QRectF(top_left, bottom_right))
        for robot_id, route in self.scenario.routes.items():
            painter.setOpacity(
                0.30 if self.selection and self.selection != robot_id else 1.0
            )
            color = QColor(ROBOT_COLORS[robot_id])
            start = self._pixel(route.start.x_m, route.start.y_m)
            wait = self._pixel(route.wait.x_m, route.wait.y_m)
            exit_pose = self._pixel(route.exit.x_m, route.exit.y_m)
            goal = self._pixel(route.goal.x_m, route.goal.y_m)
            painter.setPen(QPen(color, 0.55, Qt.DashLine))
            painter.drawLine(start, wait)
            painter.drawLine(wait, exit_pose)
            painter.drawLine(exit_pose, goal)
            painter.setPen(color)
            font = painter.font()
            font.setPixelSize(6)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(start + QPointF(-10, 0), route.start_label)
            painter.drawText(goal + QPointF(8, 0), route.goal_label)
        painter.setOpacity(1.0)
        for robot in self.robots:
            if robot["pose"] is not None:
                self._draw_robot(painter, robot)
        painter.end()

    def _draw_robot(self, painter: QPainter, robot: dict[str, Any]) -> None:
        pose = Pose(**robot["pose"])
        center = self._pixel(pose.x_m, pose.y_m)
        radius = self.scenario.robot_radius_m / self.scenario.world.resolution
        if self.selection == robot["robot_id"]:
            painter.setPen(QPen(QColor(ROBOT_COLORS[robot["robot_id"]]), 0.7))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius + 1.8, radius + 1.8)
        painter.setOpacity(1.0 if robot["connected"] else 0.42)
        painter.setPen(QPen(QColor("#ffffff"), 0.65))
        painter.setBrush(QColor(ROBOT_COLORS[robot["robot_id"]]))
        painter.drawEllipse(center, radius, radius)
        heading = QPointF(cos(pose.yaw_rad), -sin(pose.yaw_rad))
        painter.setPen(QPen(QColor(ROBOT_COLORS[robot["robot_id"]]), 1.0))
        painter.drawLine(center + heading * radius, center + heading * (radius + 3))
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPixelSize(7)
        painter.setFont(font)
        painter.drawText(
            QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
            Qt.AlignCenter,
            self.scenario.routes[robot["robot_id"]].start_label,
        )
        painter.setOpacity(1.0)


class RobotCard(QFrame):
    def __init__(self, robot_id: str, route: Route) -> None:
        super().__init__()
        self.setObjectName("panel")
        self.title = QPushButton(
            f"핑키프로 {route.start_label}   ·   {route.start_label} → {route.goal_label}"
        )
        self.title.setCheckable(True)
        self.title.setObjectName("robotTitle")
        self.title.setStyleSheet(f"color: {ROBOT_COLORS[robot_id]};")
        self.title.setToolTip("지도에서 이 로봇의 경로 강조")
        self.task = QLabel()
        self.battery = QLabel()
        self.battery.setObjectName("batteryStatus")
        self.diagnostics = QLabel()
        self.diagnostics.setObjectName("muted")
        self.diagnostics.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(self.title, 1)
        header.addWidget(self.battery)
        layout.addLayout(header)
        for widget in (self.task, self.diagnostics, self.detail):
            layout.addWidget(widget)
        self.render({})

    def render(self, robot: dict[str, Any]) -> None:
        task = STATES.get(robot.get("task_state"), "대기")
        phase = PHASES.get(robot.get("phase"))
        self.task.setText(f"{task}  ·  {phase}" if phase else task)

        percent = robot.get("battery_percent")
        if percent is None:
            self.battery.setText("배터리 미수신")
        elif robot.get("battery_stale"):
            self.battery.setText("배터리 수신 중단")
        else:
            self.battery.setText(f"배터리 {percent:.0f}%")

        lidar = "수신" if robot.get("scan_received") else "미수신"
        odom = "수신" if robot.get("odom_received") else "미수신"
        if robot.get("location_paused"):
            pose = "보고 중단"
        elif robot.get("connected"):
            pose = f"수신 {robot['pose_age_s']:.1f}초 전"
        else:
            pose = "오래됨" if robot.get("pose") else "미수신"
        self.diagnostics.setText(
            f"라이다 {lidar}  ·  오도메트리 {odom}  ·  위치 {pose}"
        )
        error = robot.get("error_code")
        detail = TASK_ERRORS.get(error, error or "") or robot.get("detail", "")
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))


class FmsView(QMainWindow):
    start_requested = pyqtSignal()
    preset_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    location_requested = pyqtSignal()

    def __init__(self, scenario: Scenario, simulation_name: str = "가상 로봇") -> None:
        super().__init__()
        self.scenario = scenario
        self.gazebo = simulation_name == "Gazebo"
        self.setWindowTitle(f"CAS FMS · {simulation_name}")
        self.resize(1240, 800)
        self.setStyleSheet(
            Path(__file__).with_name("theme.qss").read_text(encoding="utf-8")
        )
        self.connection = QLabel("서버 연결 대기")
        self.connection.setObjectName("connection")
        self.zone = QLabel("교차로 상태 확인 중")
        self.zone.setObjectName("metric")
        self.zone_details = QLabel()
        self.zone_details.setWordWrap(True)
        self.zone_details.setObjectName("muted")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.run_status = QLabel("로봇 상태 확인 중")
        self.run_status.setWordWrap(True)
        self.start = QPushButton("시연 시작")
        self.cancel = QPushButton("작업 취소")
        self.cancel.setObjectName("cancel")
        self.location = QPushButton("위치 보고 중단")
        self.start.clicked.connect(self.start_requested)
        self.cancel.clicked.connect(self.cancel_requested)
        self.location.clicked.connect(self.location_requested)

        header = QHBoxLayout()
        heading = QLabel("CAS Fleet Management")
        heading.setObjectName("heading")
        mode = QLabel(simulation_name)
        mode.setObjectName("badge")
        header.addWidget(heading)
        header.addWidget(mode)
        header.addStretch()
        header.addWidget(self.connection)

        self.preset_buttons: dict[DemoPreset, QPushButton] = {}
        controls = QHBoxLayout()
        controls.addWidget(QLabel("시연 시나리오"))
        for index, (preset, title) in enumerate(DEMO_TITLES.items(), 1):
            button = QPushButton(f"{index}. {title}")
            button.setObjectName("preset")
            button.clicked.connect(
                lambda checked, key=preset: self.preset_requested.emit(key)
            )
            self.preset_buttons[preset] = button
            controls.addWidget(button)
        controls.addStretch()
        toolbar = QFrame()
        toolbar.setObjectName("panel")
        toolbar.setLayout(controls)
        toolbar.setVisible(self.gazebo)
        self.start.hide()
        self.location.hide()
        self.cancel.hide()

        self.map = MapView(scenario)
        self.map.robot_selected.connect(self._select_robot)
        map_panel, map_layout = self._panel(f"운행 지도  ·  {scenario.map_id}")
        map_layout.addWidget(self.map, 1)
        legend = QLabel(
            "● 로봇 위치와 방향    ·    점선은 경로    ·    노란 테두리는 교차로"
        )
        legend.setObjectName("muted")
        legend.setWordWrap(True)
        map_layout.addWidget(legend)

        side = QWidget()
        side.setObjectName("side")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        zone_panel, zone_layout = self._panel("교차로")
        zone_layout.addWidget(self.zone)
        zone_layout.addWidget(self.zone_details)
        side_layout.addWidget(zone_panel)
        self.cards = {
            robot_id: RobotCard(robot_id, route)
            for robot_id, route in scenario.routes.items()
        }
        for robot_id, card in self.cards.items():
            card.title.clicked.connect(
                lambda checked, key=robot_id: self._select_robot(key)
            )
            side_layout.addWidget(card)
        event_panel, event_layout = self._panel("최근 이벤트")
        self.events = QListWidget()
        self.events.setWordWrap(True)
        self.events.setMinimumHeight(100)
        self.events.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self._event_lines: tuple[str, ...] = ()
        self._render_events([])
        event_layout.addWidget(self.events, 1)
        side_layout.addWidget(event_panel, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumWidth(330)
        scroll.setWidget(side)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(map_panel)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([850, 370])

        footer = QHBoxLayout()
        footer.addWidget(self.run_status, 1)
        footer.addWidget(self.start)
        footer.addWidget(self.location)
        footer.addWidget(self.cancel)
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(toolbar)
        layout.addWidget(splitter, 1)
        layout.addLayout(footer)
        layout.addWidget(self.message)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.set_controls(False, False)

    @staticmethod
    def _panel(title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)
        return panel, layout

    def _select_robot(self, robot_id: str) -> None:
        selection = None if self.map.selection == robot_id else robot_id
        self.map.select_robot(selection)
        for key, card in self.cards.items():
            card.title.setChecked(key == selection)

    def set_controls(
        self, can_start: bool, can_cancel: bool, can_toggle_location: bool = False
    ) -> None:
        self.start.setEnabled(can_start)
        for button in self.preset_buttons.values():
            button.setEnabled(can_start)
        self.cancel.setEnabled(can_cancel)
        self.location.setEnabled(can_toggle_location)

    def show_disconnected(self) -> None:
        self.connection.setText("서버 연결 끊김")
        self.zone.setText("교차로 상태 확인 불가")
        self.zone_details.clear()
        self.run_status.setText("서버 연결을 확인하세요.")
        self.set_controls(False, False)
        self.map.update_status([], False)
        for card in self.cards.values():
            card.render({})
        self._render_events([])

    def render(self, state: dict[str, Any]) -> None:
        self.connection.setText("● 서버 연결됨")
        real_mode = state["real_mode"]
        read_only = real_mode and not state["motion_enabled"]
        preset = state.get("demo_preset")
        self.start.setVisible(not self.gazebo and not read_only)
        self.cancel.setVisible(not read_only)
        self.location.setVisible(
            not real_mode and preset not in (DemoPreset.DROPOUT, DemoPreset.CANCEL)
        )
        self.start.setText("실물 주행 시작" if real_mode else "시연 시작")
        paused_robot = state.get("paused_robot_id")
        self.location.setText("위치 보고 복구" if paused_robot else "위치 보고 중단")

        owner = self._robot_name(state["zone_owner"]) if state["zone_owner"] else "없음"
        waiting = (
            ", ".join(self._robot_name(robot_id) for robot_id in state["zone_waiting"])
            or "없음"
        )
        blocked = state["zone_blocked"]
        self.zone.setText(
            "진입 보류"
            if blocked
            else "진입권 사용 중"
            if state["zone_owner"]
            else "비어 있음"
        )
        self.zone.setStyleSheet("color: #aa3b27;" if blocked else "")
        details = f"진입권  {owner}    ·    대기  {waiting}"
        if state.get("zone_hold_reason"):
            details += "\n" + state["zone_hold_reason"]
        self.zone_details.setText(details)

        for robot in state["robots"]:
            self.cards[robot["robot_id"]].render(robot)
        self.map.update_status(state["robots"], blocked)
        self._render_events(state.get("events", []))
        if read_only:
            status = "읽기 전용 · 위치와 센서 수신 상태를 확인할 수 있습니다."
        elif state["resetting"]:
            status = "두 로봇을 출발점으로 초기화 중…"
        elif state.get("reset_failed"):
            status = "출발점 초기화 실패 · 다시 선택하면 재시도합니다."
        elif state["can_start"] and real_mode:
            status = "두 로봇의 출발 위치와 정지를 확인했습니다."
        elif state["can_start"]:
            task_states = {robot["task_state"] for robot in state["robots"]}
            result = "준비 완료"
            if task_states == {"SUCCEEDED"}:
                result = (
                    "두 로봇 출발점 복귀 완료"
                    if preset == DemoPreset.NORMAL
                    else "두 로봇 회전 완료"
                )
            elif task_states == {"CANCELED"}:
                result = "취소 및 정지 확인"
            if "FAILED" in task_states:
                result = "시연 실패"
            status = f"{result} · 새 시연은 출발점부터 시작합니다."
        else:
            status = DEMO_TITLES.get(preset, "로봇 상태 확인 중")
        self.run_status.setText(status)

    def _robot_name(self, robot_id: str) -> str:
        return f"핑키 {self.scenario.routes[robot_id].start_label}"

    def _render_events(self, events: list[dict[str, Any]]) -> None:
        lines = tuple(
            f"{event['elapsed_s'] // 60:02}:{event['elapsed_s'] % 60:02}   {event['text']}"
            for event in reversed(events[-16:])
        ) or ("아직 이벤트가 없습니다.",)
        if self._event_lines != lines:
            self.events.clear()
            self.events.addItems(lines)
            self._event_lines = lines

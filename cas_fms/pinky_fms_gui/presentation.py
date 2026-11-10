from typing import Any
from uuid import uuid4

from PyQt5.QtCore import QObject, QTimer

from pinky_fms_gui.http_client import FmsClient
from pinky_fms_gui.views import FmsView


class FmsPresenter(QObject):
    def __init__(self, view: FmsView, server_url: str) -> None:
        super().__init__(view)
        self.view = view
        self.client = FmsClient(server_url, self)
        self.client.finished.connect(self._finished)
        self.status: dict[str, Any] | None = None
        self.status_pending = False
        self.action_pending = False
        self.view.start_requested.connect(self._start)
        self.view.preset_requested.connect(self._start_preset)
        self.view.cancel_requested.connect(self._cancel)
        self.view.location_requested.connect(self._toggle_location)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)
        self.refresh()

    def refresh(self) -> None:
        if not self.status_pending:
            self.status_pending = True
            self.client.send("status")

    def _start(self) -> None:
        if self.status and self.status["can_start"] and not self.action_pending:
            self._send_action("run", {"request_id": uuid4().hex})

    def _start_preset(self, preset: str) -> None:
        if self.status and self.status["can_start"] and not self.action_pending:
            self._send_action("run", {"request_id": uuid4().hex, "preset": preset})

    def _cancel(self) -> None:
        if self.status and self.status["can_cancel"] and not self.action_pending:
            self._send_action(
                "cancel", {"request_id": uuid4().hex, "run_id": self.status["run_id"]}
            )

    def _toggle_location(self) -> None:
        if not self.status or self.action_pending:
            return
        paused_robot = self.status.get("paused_robot_id")
        robot_id = paused_robot or self.status.get("location_pause_target")
        if robot_id:
            self._send_action(
                "demo/location-reporting",
                {"robot_id": robot_id, "paused": not paused_robot},
            )

    def _send_action(self, action: str, payload: dict[str, str | bool]) -> None:
        self.action_pending = True
        self.view.set_controls(False, False)
        self.view.message.setText("요청 처리 중…")
        self.client.send(action, payload)

    def _finished(self, action: str, data: dict[str, Any] | None, error: str) -> None:
        if action == "status":
            self.status_pending = False
            self.status = data
            if data is None:
                self.view.show_disconnected()
                return
            self.view.render(data)
            self.view.set_controls(
                data["can_start"] and not self.action_pending,
                data["can_cancel"] and not self.action_pending,
                bool(data.get("paused_robot_id") or data.get("location_pause_target"))
                and not self.action_pending,
            )
            return
        self.action_pending = False
        self.view.message.setText(error or "요청이 접수되었습니다.")
        self.refresh()

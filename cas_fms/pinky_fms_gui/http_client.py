import json
from functools import partial

from PyQt5.QtCore import QObject, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class FmsClient(QObject):
    finished = pyqtSignal(str, object, str)

    def __init__(self, server_url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.server_url = server_url.rstrip("/")
        self.network = QNetworkAccessManager(self)

    def send(self, action: str, payload: dict[str, str | bool] | None = None) -> None:
        request = QNetworkRequest(QUrl(f"{self.server_url}/api/{action}"))
        request.setTransferTimeout(1000)
        if payload is None:
            reply = self.network.get(request)
        else:
            request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            reply = self.network.post(request, json.dumps(payload).encode("utf-8"))
        reply.finished.connect(partial(self._finish, action, reply))

    def _finish(self, action: str, reply: QNetworkReply) -> None:
        try:
            data = json.loads(bytes(reply.readAll()))
        except ValueError:
            data = None
        if reply.error() != QNetworkReply.NoError:
            error = (
                data.get("error", reply.errorString())
                if isinstance(data, dict)
                else (reply.errorString())
            )
            self.finished.emit(action, None, str(error))
        elif isinstance(data, dict):
            self.finished.emit(action, data, "")
        else:
            self.finished.emit(action, None, "서버 응답을 읽을 수 없습니다.")
        reply.deleteLater()

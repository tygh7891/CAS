"""작업 요청과 상태 응답을 localhost에서 비교하는 연습 서버."""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class StudyHandler(BaseHTTPRequestHandler):
    def respond(self, status, payload):
        # Python 딕셔너리를 HTTP 본문으로 보낼 JSON 바이트로 바꾼다.
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            self.respond(HTTPStatus.OK, {"pending": self.server.pending})
        else:
            self.respond(HTTPStatus.NOT_FOUND, {"error": "unknown route"})

    def do_POST(self):
        if self.path != "/api/jobs":
            self.respond(HTTPStatus.NOT_FOUND, {"error": "unknown route"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 1024:
                raise ValueError("invalid request length")
            job = json.loads(self.rfile.read(length))
            if not isinstance(job, dict):
                raise ValueError("expected an object")
            robot, spins = job.get("robot_id"), job.get("spin_count")
            if robot != "robot_1" or type(spins) is not int or not 0 <= spins <= 100:
                raise ValueError("invalid robot_id or spin_count")
        except ValueError as error:
            self.respond(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        # 202는 큐에 넣었다는 뜻이다. 이 예제의 작업은 여기서 움직이지 않는다.
        entry = {"robot_id": robot, "spin_count": spins, "status": "QUEUED"}
        self.server.pending.append(entry)
        self.respond(HTTPStatus.ACCEPTED, entry)


def main():
    # 같은 컴퓨터만 연결한다. 실제 CAS 서버의 포트 8765와 분리한다.
    with HTTPServer(("127.0.0.1", 8766), StudyHandler) as server:
        server.pending = []
        print("Study HTTP: http://127.0.0.1:8766", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n학습용 HTTP 서버 종료")


if __name__ == "__main__":
    main()

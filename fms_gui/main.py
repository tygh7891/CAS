"""CAS FMS GUI. ROS2-independent PyQt5 operator console."""
import argparse
import json
import math
import sys
from urllib.parse import urljoin

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, QByteArray
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.QtWidgets import (QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QMainWindow, QMessageBox, QPushButton, QSpinBox,
                             QSplitter, QTextEdit, QVBoxLayout, QWidget)


DARK = '#101823'
PANEL = '#192535'
BORDER = '#304358'
FG = '#edf3fa'
MUTED = '#aab9c9'
ACCENT = '#4ba3ff'
R1 = '#61c6ac'
R2 = '#e9b76a'


def label(text='', size=11, bold=False, color=FG):
    obj = QLabel(str(text))
    obj.setWordWrap(True)
    obj.setStyleSheet(f'color:{color}; background:transparent;')
    f = obj.font()
    f.setPointSize(size)
    f.setBold(bold)
    obj.setFont(f)
    return obj


def panel():
    w = QFrame()
    w.setObjectName('Panel')
    w.setStyleSheet(f'QFrame#Panel {{background:{PANEL}; border:1px solid {BORDER}; border-radius:10px;}}')
    return w


class TrackMap(QWidget):
    """Topology view based on YAML points, NOT a live OccupancyGrid map."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 320)
        self.state = {}

    def update_state(self, state):
        self.state = state
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(PANEL))
        p.setPen(QColor(MUTED))
        if not self.state.get('configured'):
            p.drawText(self.rect(), Qt.AlignCenter,
                       '좌표 미설정\nfms_server/config.yaml 파일에\n활성 로봇의 포인트와 공유존 경계를 입력하세요')
            return
        routes = self.state['routes']
        zone = self.state['zone']
        points = [item for route in routes.values() for item in route.values()]
        x1,y1,x2,y2 = zone['bounds']
        allx = [v['x'] for v in points] + [x1,x2]
        ally = [v['y'] for v in points] + [y1,y2]
        lowx, highx, lowy, highy = min(allx), max(allx), min(ally), max(ally)
        rangex, rangey = max(highx-lowx, 0.2), max(highy-lowy, 0.2)
        margin=40
        scale=min((self.width()-2*margin)/rangex,(self.height()-2*margin)/rangey)
        ox=(self.width()-scale*rangex)/2
        oy=(self.height()-scale*rangey)/2
        def xy(x,y):
            return QPointF(ox+(x-lowx)*scale, self.height()-(oy+(y-lowy)*scale))
        # The zone is rendered with the clearance included, matching server overlap logic.
        rad=zone['clearance_m']
        z0=xy(x1-rad,y2+rad)
        z1=xy(x2+rad,y1-rad)
        dashed_pen = QPen(QColor('#ff8b8b'))
        dashed_pen.setWidthF(1.3)
        dashed_pen.setStyle(Qt.DashLine)
        p.setPen(dashed_pen)
        p.setBrush(QBrush(QColor(150,55,65,75)))
        p.drawRect(QRectF(z0,z1).normalized())
        p.setPen(QColor('#e9a9a9'))
        p.drawText(xy(x1,y2)+QPointF(5,-6),'SHARED ZONE')
        for rid, color in [('robot_1',R1),('robot_2',R2)]:
            if rid not in routes:
                continue  # Inactive robot: no route is needed or drawn.
            route=routes[rid]
            a,b=route['endpoint_a'],route['endpoint_b']
            p.setPen(QPen(QColor(color),4,Qt.SolidLine,Qt.RoundCap))
            p.drawLine(xy(a['x'],a['y']), xy(b['x'],b['y']))
            for key, radius in [('endpoint_a',6),('endpoint_b',6),('wait_a',4),('wait_b',4)]:
                v=route[key]; loc=xy(v['x'],v['y'])
                point_pen = QPen(QColor(color))
                point_pen.setWidthF(1.5)
                p.setPen(point_pen)
                p.setBrush(QColor(DARK if key.startswith('wait') else color))
                p.drawEllipse(loc,radius,radius)
                p.setPen(QColor(FG))
                p.drawText(loc+QPointF(8,-7), rid[-1]+':'+key.replace('endpoint_','E').replace('wait_','W'))
            robot=self.state.get('robots',{}).get(rid,{})
            pose=robot.get('pose')
            if pose:
                pos=xy(pose['x'],pose['y'])
                p.setBrush(QColor(color))
                p.setPen(QPen(QColor('#ffffff'),2))
                p.drawEllipse(pos,8,8)
                heading=QPointF(pos.x()+16*math.cos(pose['yaw']),
                                pos.y()-16*math.sin(pose['yaw']))
                p.drawLine(pos,heading)
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, server_url):
        super().__init__()
        self.setWindowTitle('CAS FMS | Central Fleet Control')
        self.resize(1300, 830)
        self.server_url = server_url.rstrip('/')+'/'
        self.http = QNetworkAccessManager(self)
        self.loading = False
        self.status = {}
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.refresh()

    def _build(self):
        central=QWidget()
        central.setStyleSheet(f'''QWidget {{background:{DARK}; color:{FG};}}
            QComboBox,QSpinBox,QTextEdit {{background:#0e1b2a; color:{FG}; border:1px solid {BORDER};
                                        border-radius:5px; padding:7px;}}
            QPushButton {{background:#2267a6; color:white; border-radius:6px; padding:11px; font-weight:bold;}}
            QPushButton:hover {{background:#327fc0;}}''')
        main=QVBoxLayout(central)
        main.setSpacing(12)
        head=QHBoxLayout()
        head.addWidget(label('CAS  /  FMS CONTROL',20,True))
        head.addStretch()
        self.connection=label('서버 연결 중',10,False,MUTED)
        head.addWidget(self.connection)
        main.addLayout(head)
        horizontal=QSplitter(Qt.Horizontal)
        # LEFT: dispatch and independent per-robot job queues
        left=panel(); l=QVBoxLayout(left); l.setContentsMargins(16,16,16,16)
        l.addWidget(label('작업 등록',15,True))
        l.addWidget(label('작업 1건 = 반대편 이동 → 회전 → 출발점 복귀',10,False,MUTED))
        l.addWidget(label('대상 로봇',10,False,MUTED))
        self.robot_pick=QComboBox()
        self.robot_pick.addItems(['robot_1','robot_2'])
        l.addWidget(self.robot_pick)
        l.addWidget(label('도착지 회전 횟수',10,False,MUTED))
        self.spins=QSpinBox(); self.spins.setRange(0,100); self.spins.setValue(2)
        l.addWidget(self.spins)
        self.add_button=QPushButton('작업 큐에 추가')
        self.add_button.clicked.connect(self.enqueue)
        l.addWidget(self.add_button)
        self.delay_info=label('작업 완료 → 3초 후 다음 작업',10,False,MUTED)
        l.addWidget(self.delay_info)
        l.addSpacing(16)
        l.addWidget(label('Robot 1  ·  작업 큐',12,True,R1))
        self.queue1=QTextEdit(); self.queue1.setReadOnly(True); self.queue1.setMinimumHeight(120)
        l.addWidget(self.queue1)
        l.addWidget(label('Robot 2  ·  작업 큐',12,True,R2))
        self.queue2=QTextEdit(); self.queue2.setReadOnly(True); self.queue2.setMinimumHeight(120)
        l.addWidget(self.queue2)
        l.addStretch()
        horizontal.addWidget(left)
        # CENTER: coordinate-based schematic
        middle=panel(); m=QVBoxLayout(middle); m.setContentsMargins(12,12,12,12)
        m.addWidget(label('공유존 · 경로 및 현재 위치',15,True))
        m.addWidget(label('설정 좌표 기반 개략도 (Nav2 Costmap 아님)',10,False,MUTED))
        self.map=TrackMap(); m.addWidget(self.map,1)
        horizontal.addWidget(middle)
        # RIGHT: owner / queue / live pose / action feedback
        right=panel(); r=QVBoxLayout(right); r.setContentsMargins(16,16,16,16)
        r.addWidget(label('공유존 통행권',15,True))
        self.owner=label('점유권: 없음',15,True)
        r.addWidget(self.owner)
        self.wait=label('대기열: 없음',11,False,MUTED)
        r.addWidget(self.wait)
        self.blocked=label('차단: 없음',10,False,MUTED)
        r.addWidget(self.blocked)
        r.addSpacing(16)
        r.addWidget(label('로봇 주행 상태',15,True))
        self.robot_views={}
        for rid, color in [('robot_1',R1),('robot_2',R2)]:
            r.addWidget(label(rid,12,True,color))
            status=label('Worker 연결 대기',10,False,MUTED)
            r.addWidget(status)
            self.robot_views[rid]=status
        r.addStretch()
        horizontal.addWidget(right)
        horizontal.setSizes([295,610,325])
        main.addWidget(horizontal,1)
        main.addWidget(label('중앙 이벤트 기록 (서버 메모리)',12,True))
        self.events=QTextEdit(); self.events.setReadOnly(True); self.events.setMaximumHeight(170)
        main.addWidget(self.events)
        self.setCentralWidget(central)

    def request(self, method, route, data=None, handler=None):
        url=QUrl(urljoin(self.server_url,route.lstrip('/')))
        req=QNetworkRequest(url)
        req.setHeader(QNetworkRequest.ContentTypeHeader,'application/json')
        if method=='POST':
            reply=self.http.post(req, QByteArray(json.dumps(data).encode('utf-8')))
        else:
            reply=self.http.get(req)
        def done():
            raw=bytes(reply.readAll())
            err=reply.error()
            try:
                parsed=json.loads(raw) if raw else {}
            except (ValueError, UnicodeDecodeError):
                parsed={'detail':raw.decode('utf-8','replace')[:200]}
            reply.deleteLater()
            if handler:
                handler(err,parsed)
        reply.finished.connect(done)

    def refresh(self):
        if self.loading:
            return
        self.loading=True
        def received(err,data):
            self.loading=False
            if err:
                self.connection.setText('서버 연결 실패')
                self.connection.setStyleSheet('color:#ff9292')
                return
            self.connection.setText('서버 연결 · 실시간 갱신')
            self.connection.setStyleSheet(f'color:{R1}')
            self.status=data
            self.render(data)
        self.request('GET','api/state',handler=received)

    def enqueue(self):
        payload={'robot_id':self.robot_pick.currentText(), 'spin_count':self.spins.value()}
        def received(err,data):
            if err:
                QMessageBox.warning(self,'작업 등록 실패',str(data.get('detail',data)))
            else:
                self.refresh()
        self.request('POST','api/jobs',payload,received)

    def render(self,data):
        self.map.update_state(data)
        if not data.get('configured'):
            self.owner.setText('좌표 설정 필요')
            self.blocked.setText(data.get('configuration_error',''))
            self.add_button.setEnabled(False)
            return
        # The server is the only authority for the participating robot list.
        active_ids = list(data.get('settings', {}).get('active_robots') or data['robots'])
        shown = [self.robot_pick.itemText(i) for i in range(self.robot_pick.count())]
        if shown != active_ids:
            selected = self.robot_pick.currentText()
            self.robot_pick.clear()
            self.robot_pick.addItems(active_ids)
            if selected in active_ids:
                self.robot_pick.setCurrentText(selected)
        self.add_button.setEnabled(bool(active_ids))
        z=data['zone']
        self.owner.setText('예약 주체: '+str(z.get('owner') or '없음'))
        self.wait.setText('FIFO 대기열: '+(', '.join(z.get('waiting') or []) or '없음'))
        self.blocked.setText('차단: '+str(z.get('blocked') or '없음'))
        self.delay_info.setText(f'정상 완료 후 {data["settings"]["next_job_delay_s"]:g}초 → 다음 작업')
        for rid,widget in [('robot_1',self.queue1),('robot_2',self.queue2)]:
            if rid not in data['robots']:
                widget.setPlainText('운용 제외 (서버 설정)')
                self.robot_views[rid].setText('INACTIVE · 서버 설정에서 운용하지 않음')
                continue
            bot=data['robots'][rid]
            active=bot.get('active')
            items=[]
            if active:
                items.append(f'▶ {active["job_id"]}  회전 {active["spin_count"]}회  [{active["phase"]}]')
            for idx,job in enumerate(bot['pending'],1):
                items.append(f'{idx}. {job["job_id"]}  회전 {job["spin_count"]}회')
            widget.setPlainText('\n'.join(items) if items else '작업 없음')
            pose=bot.get('pose')
            pos='좌표 없음' if pose is None else f'x={pose["x"]:.2f}, y={pose["y"]:.2f}'
            feedback=bot.get('feedback') or {}
            dist=feedback.get('distance_remaining_m')
            extra='' if dist is None else f'\n남은 거리 {dist:.2f} m'
            self.robot_views[rid].setText(
                f'{"ONLINE" if bot["ready"] else "OFFLINE / TF 미수신"} · {bot["phase"]}'
                f'\n{pos}{extra}\n다음 작업 대기 {bot["cooldown_remaining_s"]:.1f}초'
                + f'\n다음 작업 조건: {bot.get("start_reason", "")}'
                + ('\n작업 실패: 복구 정책 미구현' if bot['halted'] else ''))
        self.events.setPlainText('\n'.join(
            f'{e["at"][11:19]} · {e["robot_id"] or "SERVER"} · {e["type"]} · {e["message"]}'
            for e in reversed(data.get('events',[])[-80:])))


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument('--server',default='http://127.0.0.1:8765')
    args=arg.parse_args()
    app=QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    window=MainWindow(args.server)
    window.show()
    sys.exit(app.exec_())


if __name__=='__main__':
    main()

"""Single-screen PyQt5 operator view. HTTP only; no robot control imports."""
import json
import math
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from map_view import ReceivedMapView
from PyQt5.QtCore import Qt, QTimer, QUrl, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF, QFont
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtWidgets import (QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,
                            QGroupBox,QTextEdit,QMessageBox,QSplitter,QCheckBox,QSizePolicy)

PHASE={'RETURNING':'출발점 복귀 중','VERIFY_HOME':'초기 방향·정지 확인','VERIFY_WAIT':'대기점 정지 확인','VERIFY_GOAL':'목적지 정지 확인','VERIFY_DONE':'회전 후 정지 확인','CANCELED':'취소됨','IDLE':'대기','TO_WAIT':'대기점 이동','WAITING_ZONE':'공유존 권한 대기','CROSSING':'공유존 통과',
       'TO_GOAL':'목적지 이동','SPINNING':'회전 작업 중','DONE':'완료 · 목적지 대기','HALTED':'중단'}
STATES={'IDLE':'미요청','RUNNING':'진행 중','SUCCEEDED':'작업 완료','FAILED':'실패','CANCELED':'취소 완료'}
EVENTS={'RETURN_REQUESTED':'출발점 복귀 요청','RETURN_COMPLETED':'출발점 복귀 완료','SESSION_CREATED':'세션 준비','TASK_ACCEPTED':'작업 접수','PHASE_CHANGED':'단계 변경','ZONE_REQUESTED':'공유존 요청','ZONE_GRANTED':'진입 허가','ZONE_ENTERED':'공유존 진입','ZONE_EXIT_VERIFIED':'전체 이탈 확인','ZONE_RELEASED':'권한 해제','ZONE_BLOCKED':'공유존 보류','CANCELED':'작업 취소','HALTED':'진행 중단','SERVER_ERROR':'서버 오류'}
COLORS={'robot_1':'#2563eb','robot_2':'#d97706'}

class Dashboard(QMainWindow):
    def __init__(self,url,token):
        super().__init__();self.url=url;self.token=token;self.state=None;self.polling=False
        self.connected=False;self.pending=False;self.last_seq=0;self._callbacks={}
        self.setWindowTitle('CAS | 실물 관제 · 로봇 1 / 2');self.resize(1260,820)
        self.network=QNetworkAccessManager(self)
        root=QWidget();self.setCentralWidget(root);outer=QVBoxLayout(root)
        header=QHBoxLayout();title=QLabel('CAS  /  작업 관제');title.setStyleSheet('font-size:24px;font-weight:700')
        self.connection=QLabel('서버 연결 중');self.mode=QLabel('REAL_NAV2 · 도메인 14 / 30')
        header.addWidget(title);header.addStretch();header.addWidget(self.mode);header.addWidget(self.connection)
        outer.addLayout(header)
        self.notice=QLabel('실물 위치·Nav2 연결 대기')
        self.notice.setWordWrap(True);self.notice.setFixedHeight(36);outer.addWidget(self.notice)
        middle=QHBoxLayout();outer.addLayout(middle,1)
        command=QGroupBox('작업 명령');command.setMaximumWidth(250);left=QVBoxLayout(command)
        intro=QLabel('등록 작업 선택\n이동 → 공유존 순차 통과 → 회전');intro.setWordWrap(True);left.addWidget(intro)
        self.task_buttons={}
        for mission,label in [('scenario','1차 시나리오 시작\n1번 → B  /  2번 → A'),('work_B','B 작업장 작업\n로봇 1 · 이동 후 회전'),('work_A','A 작업장 작업\n로봇 2 · 이동 후 회전')]:
            b=QPushButton(label);b.setMinimumHeight(62);b.clicked.connect(lambda checked=False,m=mission:self.post('/api/v1/tasks',dict(mission=m)))
            self.task_buttons[mission]=b;left.addWidget(b)
        left.addStretch()
        self.cancel_all=QPushButton('전체 작업 취소');self.cancel_all.clicked.connect(lambda:self.post('/api/v1/cancel',dict(target='all')))
        left.addWidget(self.cancel_all)
        self.reset=QPushButton('출발점 복귀');self.reset.clicked.connect(self.reset_session);left.addWidget(self.reset)
        hint=QLabel('현재 작업 정지 후 한 대씩 출발점·초기 방향으로 복귀합니다.')
        self.reset_hint=hint
        hint.setWordWrap(True);hint.setStyleSheet('color:#64748b;font-size:11px');left.addWidget(hint)
        middle.addWidget(command)
        mapbox=QGroupBox('지도 · 로봇 위치');ml=QVBoxLayout(mapbox);self.map_container=ml;ml.setSpacing(6);self.map=ReceivedMapView();self.map.on_point=lambda text:self.point_info.setText(text);ml.addWidget(self.map,1)
        self.map_metadata=QLabel('');self.map_metadata.setWordWrap(True);self.map_metadata.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed);ml.addWidget(self.map_metadata)
        self.mask_toggle=QCheckBox('마스크 흰 영역 강조 (보기 전용 · 적용 의미 미확정)');self.mask_toggle.hide();self.mask_toggle.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed)
        self.mask_toggle.toggled.connect(self.toggle_mask);ml.addWidget(self.mask_toggle)
        self.point_info=QLabel('');self.point_info.setWordWrap(True);self.point_info.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Fixed);ml.addWidget(self.point_info);middle.addWidget(mapbox,1)
        right=QVBoxLayout();middle.addLayout(right);self.cards={};self.cancel_buttons={}
        for name in ['robot_1','robot_2']:
            box=QGroupBox('로봇 '+name[-1]);box.setMinimumWidth(280);layout=QVBoxLayout(box)
            label=QLabel('수신 대기');label.setWordWrap(True);layout.addWidget(label);self.cards[name]=label
            button=QPushButton('이 로봇 작업 취소');button.clicked.connect(lambda checked=False,n=name:self.post('/api/v1/cancel',dict(target=n)))
            self.cancel_buttons[name]=button;layout.addWidget(button);right.addWidget(box)
        box=QGroupBox('공유존');layout=QVBoxLayout(box);self.zone=QLabel('수신 대기');self.zone.setWordWrap(True);layout.addWidget(self.zone);right.addWidget(box);right.addStretch()
        events=QGroupBox('최근 이벤트');el=QVBoxLayout(events);self.log=QTextEdit();self.log.setReadOnly(True);self.log.document().setMaximumBlockCount(500);self.log.setMaximumHeight(190);el.addWidget(self.log);outer.addWidget(events)
        self.statusBar().showMessage(url+' | REAL_NAV2 · 실물 연결 대기')
        self.setStyleSheet('QMainWindow{background:#eef2f7} QGroupBox{font-size:13px;background:white;border:1px solid #dbe2ec;border-radius:8px;margin-top:12px;padding:12px;font-weight:600} QGroupBox::title{subcontrol-origin:margin;left:12px} QPushButton{font-size:13px;padding:8px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc} QPushButton:hover{background:#e0eaff} QPushButton:disabled{color:#94a3b8} QLabel{font-size:13px;font-weight:400} QTextEdit{border:0;font-family:monospace;font-size:11px}')
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(200)
        self.update_buttons();self.poll()

    def request(self,path,body=None):
        request=QNetworkRequest(QUrl(self.url+path));request.setRawHeader(b'X-CAS-Token',self.token.encode())
        request.setTransferTimeout(2500)
        if body is None:reply=self.network.get(request)
        else:
            request.setHeader(QNetworkRequest.ContentTypeHeader,'application/json')
            reply=self.network.post(request,json.dumps(body).encode())
        return reply

    def poll(self):
        if self.polling:return
        self.polling=True;reply=self.request('/api/v1/state')
        def done():
            self.polling=False
            try:
                if reply.error()!=QNetworkReply.NoError:raise ValueError(reply.errorString())
                self.render(json.loads(bytes(reply.readAll())))
            except (ValueError,KeyError,TypeError):
                self.connected=False;self.connection.setText('서버 연결 끊김');self.notice.setText('서버 응답 없음 · 지도/상태는 마지막 수신값 · 명령 비활성');self.update_buttons()
            finally:self._callbacks.pop(reply,None);reply.deleteLater()
        self._callbacks[reply]=done
        reply.finished.connect(done)

    def render(self,state):
        self.state=state;self.connected=True;self.connection.setText('서버 연결 정상 · 5Hz')
        self.mode.setText('REAL_NAV2 · 도메인 14 / 30')
        self.notice.setText(state.get('preflight_reason','실물 관제'))
        self.render_real_map(state)
        tag='실물'
        for r in state['simulation']['robots']:
            reason='공유존 대기 — 다른 로봇 통과 중' if r['phase']=='WAITING_ZONE' else PHASE.get(r['phase'],r['phase'])
            conn='실물 Nav2 정상' if r.get('connection')=='REAL_NAV2_OK' else '실물 연결 대기'
            fresh=r.get('pose_valid',False)
            position='미수신' if r.get('position') is None else f"{r['position']} m ({tag})"+(' · 마지막 수신' if not fresh else '')
            age='미수신' if r.get('pose_age_s') is None else f"{r['pose_age_s']:.2f}초 전"
            stop='미확인' if not fresh else ('확인('+tag+')' if r['stopped_confirmed'] else '이동/작업 중')
            self.cards[r['id']].setText(f"{conn} · 배터리: —\n작업: {r['destination']} 작업장\n결과: {STATES.get(r['task_state'],r['task_state'])}\n단계: {reason}\n위치: {position}\n위치 갱신: {age}\n정지: {stop}")
        z=state['zone'];join=lambda xs:', '.join(xs) if xs else '없음'
        self.zone.setText(f"진입권: {z['owner'] or '없음'}\n실제 {tag} 점유: {join(z['occupants'])}\n대기: {join(z['waiting'])}\n보류: {z['blocked_reason'] or '없음'}")
        for e in state['events']:
            if e['seq']>self.last_seq:
                stamp=datetime.fromisoformat(e['timestamp']).astimezone(ZoneInfo('Asia/Seoul')).strftime('%H:%M:%S')
                detail=PHASE.get(e['phase'],e['phase'] or '')
                if e['event'] in ('SERVER_ERROR','ZONE_BLOCKED','HALTED'):detail=e['reason']
                self.log.append(f"{stamp}  {e['robot_id'] or '서버'}  {EVENTS.get(e['event'],e['event'])}  {detail}")
                self.last_seq=e['seq']
        self.update_buttons()

    def render_real_map(self,state):
        from map_view import ReceivedMapView
        review=state['map_review']
        if not isinstance(self.map,ReceivedMapView):
            old=self.map;self.map=ReceivedMapView();self.map.on_point=self.point_info.setText
            self.map.show_mask=False
            self.map_container.replaceWidget(old,self.map);self.map_container.setStretchFactor(self.map,1);old.deleteLater()
            self.mask_toggle.setChecked(False)
            self.point_info.setText('지도를 클릭하면 map 좌표가 표시됩니다.')
        self.map.state=state
        self.map.set_review(review)
        self.map.update()
        self.mask_toggle.setVisible(review['mask'] is not None)
        self.mask_toggle.setText('통행 허용 영역 강조 (원본 흰 픽셀 · 파란 통로)')
        b=review['base']
        self.map_metadata.setText(f"{b['width']}×{b['height']} px · {b['resolution']*100:.1f} cm/px · 원점 {b['origin']} · 지도 식별 {b['sha256'][:10]}")

    def toggle_mask(self,checked):
        if hasattr(self.map,'show_mask'):self.map.show_mask=checked;self.map.update()

    def update_buttons(self):
        ready=self.connected and not self.pending and self.state is not None and not self.state.get('commands_locked',False)
        started=set(self.state['started']) if ready else set()
        blocked=bool(self.state['zone']['blocked_reason']) if ready else True
        for mission,button in self.task_buttons.items():
            ids={'scenario':{'robot_1','robot_2'},'work_B':{'robot_1'},'work_A':{'robot_2'}}[mission]
            button.setEnabled(ready and not blocked and not (ids & started))
        active=self.state['active'] if ready else False
        self.cancel_all.setEnabled(ready and active);self.reset.setEnabled(ready and not self.state.get('returning',False))
        for name,button in self.cancel_buttons.items():
            running=ready and any(r['id']==name and r['task_state']=='RUNNING' for r in self.state['simulation']['robots'])
            button.setEnabled(bool(running))

    def post(self,path,fields):
        if not self.connected or self.pending or self.state is None:return
        self.pending=True;self.update_buttons()
        mode='REAL_NAV2'
        body=dict(fields,request_id=uuid.uuid4().hex,session_id=self.state['session_id'],mode=mode)
        reply=self.request(path,body)
        def done():
            self.pending=False
            try:
                data=json.loads(bytes(reply.readAll()))
                if reply.error()!=QNetworkReply.NoError or 'error' in data:
                    self.statusBar().showMessage(data.get('error',reply.errorString()))
                else:self.statusBar().showMessage('요청 접수 — 작업 완료는 상태 카드에서 확인')
            except ValueError:self.statusBar().showMessage('응답 확인 실패. 자동 재전송하지 않습니다. 상태를 다시 확인하세요.')
            finally:self._callbacks.pop(reply,None);reply.deleteLater();self.update_buttons();self.poll()
        self._callbacks[reply]=done
        reply.finished.connect(done)

    def reset_session(self):
        self.post('/api/v1/return-home',{})

# A3 — 1차 임무 상태 흐름 (내장 모의 주행 + 실물 1번 읽기 전용)

## 이번 단계의 범위

- 두 임무는 모두 내장 가상 주행으로 실행: robot_1은 1→B→회전, robot_2는 2→A→회전.
- 기본 흐름: TO_WAIT → WAITING_ZONE → CROSSING → TO_GOAL → SPINNING → DONE. 회전까지 성공해야 task_state=SUCCEEDED.
- 공유존 권한은 한 대만 보유. 가상 원형 외형(여유 포함)이 공유존에 들어왔다가 완전히 이탈한 뒤 해제. 같은 시점 요청은 robot_1 우선.
- A3용 모의 좌표·외형·속도·회전 시간은 scenario.mock.json에 있으며 실제 지도나 실물 운용값이 아님.
- 실제 로봇 1의 위치·배터리·속도는 별도 REAL_READ_ONLY 행으로만 표시. 실물 odom은 공유존 판단에 사용하지 않음.
- 로봇 2 실물과는 통신하지 않음. 실물 ROS 조회는 도메인 14의 구독 전용 수신기에만 있음.
- 이 프로그램은 실제 /cmd_vel, Nav2 Goal, Spin, Cancel을 발행하지 않음. 표시되는 가상 이동·회전은 실제 모터 동작이 아님.
- 앞서 만든 A2 /cas_mock/* Action 서버를 호출하지 않는 독립적인 상태 흐름 시제품임. Worker 비동기 Action 연결·실패 전달·위치 지연 처리는 후속 구현 및 검증 필요.
- GUI·HTTP API와 A1 전체 규약은 아직 구현하지 않음. 이 폴더는 PC의 로컬 초안이며 원격 작업 브랜치에 자동 반영되지 않음.

## PC 터미널 — 기본 실행 (실물 1번 조회 포함)

핑키프로1 SSH 터미널의 기본 구동은 그대로 켜둡니다. PC의 새 터미널에서:

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/backup_server/run_demo.py --live-robot1
```

A2 모의 서버를 켤 필요는 없습니다. 실행 중 [SIM] 이벤트와 [SIM STATUS] 상태, [REAL robot_1 READ ONLY] 실물 센서 상태를 구분해 확인합니다. 약 10초 내외의 모의 임무가 끝나면 SIMULATION COMPLETED가 표시되고 읽기 전용 수신기도 종료합니다. 실제 로봇의 기본 구동은 종료하지 않습니다.

## PC 터미널 — 모의 상태 흐름만 실행

ROS나 로봇 없이:

```bash
python3 ~/CAS/cas/backup/backup_server/run_demo.py
```

## PC 터미널 — 모의 취소 시험

```bash
python3 ~/CAS/cas/backup/backup_server/run_demo.py --cancel-after 3
```

가상 진행을 중단하고 SIMULATION HALTED로 종료합니다. 예약은 검사할 수 있도록 유지합니다. 재실행은 새로운 모의 세션입니다. 이것은 실제 Nav2 취소 검증이 아닙니다. 실행 중 Ctrl+C도 가상 진행과 읽기 전용 수신기만 종료합니다.

## 확인할 로그

1. robot_1 / task_B, robot_2 / task_A가 각각 시작.
2. 한 대가 ZONE_GRANTED이면 다른 로봇은 WAITING_ZONE.
3. ZONE_ENTERED → ZONE_EXIT_VERIFIED → ZONE_RELEASED 후 다음 ZONE_GRANTED.
4. 각 로봇 TO_GOAL → SPINNING → DONE, 최종 task_state=SUCCEEDED.
5. 최종 owner=null, 가상 로봇은 B·A에 남고 출발점 복귀하지 않음.
6. --live-robot1 사용 시 실물 조회 상태는 RECEIVING이고 odom·배터리 정보가 나타남. 미연결·수신 실패여도 가상 작업은 독립적으로 실행되며 실물 연결 성공으로 간주하지 않음.

실행 기록은 backup_server/logs/<실행시각>.jsonl에 저장합니다. 실제 수신 시 odom과 배터리 값도 기록하므로 공유 전에 로그 범위를 확인합니다.

## 검사 결과

문법 검사와 가상 시계 기반 6개 검사 통과. 정상 두 임무·상호배제·최종 목적지, 공유존 내부 취소·동결·권한 유지, 실패 시 권한 유지, 실물 모드 거부, 과도한 시간 간격 거부, 외형 접촉 판정을 확인했습니다.

사용자가 보는 터미널에서 데모와 실물 읽기 전용 수신 확인은 아직 대기 중입니다. A4의 종합 권한·지연·실패 시험이나 실물 충돌 방지 검증 완료를 의미하지 않습니다.

# CAS 독립 구현 인계 (2026-11-10)

## 현재 상태

- 작업 저장소: `tygh7891/CAS`, 브랜치 `feature/backup-server-gui`.
- 독립 서버/GUI/판단 로직. 팀원의 `cas_fms`와 실물 로봇 구동은 변경하지 않습니다.
- 1차 목표: 1번→B, 2번→A, 공유존 진입 전 정지·중앙 허가, 몸체 이탈 후 주행 중 권한 반납,
  목적지에서 한 바퀴 회전 후 정지·대기. 출발점 복귀/통신 장애 우회/자동 공유존은 이후 목표입니다.
- agy B5 코드와 본 수정의 단위/HTTP/화면 없는 GUI 검사는 통과했습니다.
- **현재 조합의 Gazebo–GUI 통합 주행은 아직 검증하지 않았습니다. B5 전체 완료로 간주하지 마세요.**
- 원본 `map/`은 사용자 로컬 데이터이며 Git에 포함하지 않습니다. 새 PC에서는 동일 지도와 ROS/Gazebo 설치가 별도로 필요합니다.

## 작업 이력

| 커밋 | 변경과 검증 범위 |
|---|---|
| `315e0a0` | 위치 추정 TF/시계 확인 뒤 Nav2 활성화. 시작 시 로봇2 활성화 실패 대응 |
| `d573054` | Nav2 도착 허용 1.5cm, 중앙 확인 2cm, 경로 이탈 감시 2.5cm 일치 |
| `9afc71b` | 검증된 crossing+departure를 하나의 FollowPath로 연결, 이탈점 정지 제거 |
| `b3ebc60` | 회전 최대 0.2rad/s·가속도 0.4rad/s², 실패 시 지도/외곽 스냅샷 저장 |
| `850e104` (agy) | A/B 후보를 외벽에서 안쪽으로 이동, 끝점 목표 방향을 마지막 3cm 구간으로 계산 |
| `b2c61fa` (agy) | B5 HTTP/PyQt GUI ↔ SimNav2Adapter ↔ Worker 연결, 위치/방향·상태 표시, 개별 취소 |
| 본 수정 | HALTED/CANCELED 상태에서도 취소 명령 전달, 다른 로봇의 대기 명령 보존, 초기화의 정지/종료 검증, 오래된 응답 격리 |

검토 시작 시 실제 GitHub 브랜치 끝은 `b3ebc60`이었고, agy 두 커밋은 로컬에만 있었습니다.
본 수정과 함께 해당 선행 커밋도 원격에 반영합니다. `git log`가 최종 커밋 이력의 기준입니다.

## 현재 구조와 제한

- PC ROS2 Jazzy, Gazebo Harmonic. 시뮬레이션은 localhost domain 84 전용. 실물용 모드는 미구현입니다.
- `operator_app/launch.py --sim-nav2`: 로컬 HTTP/PyQt GUI, `sim_nav2_adapter.py`.
- `simulation/zone_coordinator.py`: 실제 관측에 기반한 중앙 공유존 상태기계.
- `simulation/nav2_worker.py`: 로봇별 TF/odom, FollowPath/Spin/Cancel 접수·결과.
- `simulation/lease_pump.py` 및 `sim_velocity_relay.py`: 진행 신호/임대 만료 시 0속도.
- `simulation/check_workers.py:load_bundle`: 지도와 현재 목적지가 맞고 통과한 분할 경로만 사용.
- `~/CAS_sim_ws/generated_map`: 생성 월드·후보·계획 및 로그. 저장소 외부입니다.
- 출발점: 이미지 왼쪽 위1/아래2, 작업점: 오른쪽 위A/아래B. 파란 X 통로 허용, 내부 흰 배경 금지.
- 몸체 반경은 여유 포함 0.10m, 추가 footprint_padding=0.0. 충돌 검사는 활성입니다.
- 새 작업점에 맞춰 경로 검사를 다시 실행해야 합니다. 지도 해시가 같아도 이전 목적지의 보고서를 재사용하면 안 됩니다.

## 이번 취소·초기화 수정

- `tick()`은 active 여부와 관계없이 명령 큐를 처리합니다. 오류 시 우선 임대를 비우고 CANCEL을 전달합니다.
- 단일 로봇 취소 시 다른 로봇의 유효 대기 명령을 버리지 않습니다.
- 초기화는 진행 작업 없음, Worker 접수/결과 대기 없음, 외부 Action 없음, Relay 정상,
  1초 이내 위치·속도와 0.3초 정지, 출발점·공유존 밖 위치를 모두 요구합니다.
- 초기화는 목표 핸들을 강제로 지우지 않습니다. source stamp/실제 수신 시각은 보존합니다.
- 명령 번호는 새 세션에서도 증가합니다. Worker는 이전 접수 응답의 목표를 취소하고 이전 결과는 무시합니다.

## 남은 확인 항목

1. 새 A/B 후보와 경로 검사를 갱신하고 아래 B5 터미널 순서를 확인합니다.
2. GUI에서 먼저 단일 작업, 이후 초기화된 월드에서 동시 시나리오를 확인합니다.
3. 공유존 밖에서 개별 취소, 공유존 점유 중 취소/전체 정지, 종료 결과 전 초기화 거부를 확인합니다.
4. 초기화는 로봇을 출발점으로 이동시키지 않습니다. 중간/완료 위치이면 GUI·Nav2·Gazebo를 종료하고 월드부터 재시작합니다.
5. 회전 실패가 다시 나면 `mission_logs/nav2_failure_*.json`과 Nav2 behavior 로그의 source 시각을 비교합니다.
6. SimNav2Adapter 생성 도중 예외가 날 때 부분 생성된 ROS/Relay 자원 정리도 추후 점검할 항목입니다.

## 실행 — 모두 PC 터미널

이전 관제/CLI 주행, Nav2, Gazebo를 각각 종료한 초기 상태에서 진행합니다.

터미널1:
```bash
bash ~/CAS/cas/backup/simulation/run_map_sim.sh
```

터미널2:
```bash
bash ~/CAS/cas/backup/simulation/run_nav2_preview.sh
```

터미널3에서 순서대로 실행하고 각 PASSED를 확인합니다:
```bash
bash ~/CAS/cas/backup/simulation/check_nav2_preview.sh
bash ~/CAS/cas/backup/simulation/check_paths.sh
bash ~/CAS/cas/backup/simulation/check_paths.sh --segments
```

이후 같은 터미널:
```bash
bash ~/CAS/cas/backup/simulation/run_operator_gui.sh
```

GUI의 준비 상태가 정상이 된 뒤 작업 버튼을 누르면 가상 로봇이 움직입니다.
CLI `run_mission.sh`와 GUI를 동시에 실행하지 마세요(같은 domain84 제어 잠금).
GUI를 여는 것만으로 작업 목표를 보내지는 않지만 Relay의 0속도 출력 연결은 생성합니다.
중단 시 GUI의 작업 취소를 사용하고 최종 정지를 확인한 후 앱을 닫습니다.

## 정적/자동 검사 — 주행 없음

```bash
source /opt/ros/jazzy/setup.bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s ~/CAS/cas/backup/operator_app -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B ~/CAS/cas/backup/simulation/test_nav2_worker.py
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B ~/CAS/cas/backup/simulation/test_zone_coordinator.py
```

본 수정 검증: operator 25건(가짜 Worker 어댑터 6건 포함), Worker 9건, 공유존 10건,
합계 44건 통과. 실제 ROS 노드/주행은 실행하지 않았습니다.

## 선별 실행 증거

`validation/2026-11-10/`에 이전 버전 시뮬레이션 로그를 보관합니다.
반복 PREFLIGHT_STATUS는 생략했으며 실패 원인·명령·상태·정지 결과는 유지했습니다.

- `20261110_172202.jsonl`: 이동 없는 전체 연결 검사 통과.
- `20261110_173902.jsonl`: 로봇2 진입권 획득 직후 3.57cm 인계 오차로 중단. 이후 도착 허용 오차를 수정함.
- `20261110_175118.jsonl`: 두 로봇 공유존 순차 통과, 로봇2 목적지 회전 도중 Nav2 703 충돌 감지,
  전체 취소와 최종 정지 확인. **최신 B5 GUI의 성공 증거가 아닙니다.**

원본 런타임 로그는 `~/CAS_sim_ws/generated_map/mission_logs/`와
`~/CAS_sim_ws/ros_logs/`에 있습니다. 비밀번호, 인증 토큰, 지도 원본은 이 인계에 포함하지 않습니다.

## GUI 위치 수신·안내 흔들림 후속 수정

- TF가 odom보다 약 0.22초 늦을 때 최신 odom 하나만 계속 덮어쓰면 동일 시각 TF를
  조회할 기회를 놓쳤습니다. 제한된 대기 큐에서 최신 공통 TF 시각과 일치하는 관측을 선택합니다.
- 관측의 원래 source/receipt 시각과 0.5초 유효 범위를 유지합니다. 재전송/캐시로 freshness를 갱신하지 않습니다.
- 상단 안내 높이를 고정하고 긴 원문 오류는 툴팁으로 이동했습니다.
- 미수신 좌표는 None/미수신, 오래된 관측의 정지는 미확인으로 표시하며 유효하지 않은 위치 마커는 그리지 않습니다.
- Worker 11건 + operator HTTP/화면 없는 GUI/어댑터 25건 통과. 실제 GUI는 재시작 후 확인이 필요합니다.

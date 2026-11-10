# CAS 예비 구현

작업 브랜치: `feature/backup-server-gui`

## 현재 구현

| 경로 | 범위 | 실물 영향 |
|---|---|---|
| `monitor.py` | 도메인 14/30 센서 모니터 | 읽기 전용 |
| `mock_connection/` | A2 PC 내부 모의 Action 이동·회전·취소 | 없음 |
| `backup_server/` | A3 내장 가상 주행·공유존 순차 통과·회전 완료, 선택적 실물 1번 상태 수신 | 실물 읽기 전용 |
| `proposals/cmd_timeout/` | 1번 자동 정지 수정안·패치·검사 | 적용·실물 시험 파일은 수동 실행 시 영향 있음 |

A2 모의 연결과 A3 정상 상태 흐름은 사용자 터미널 실행으로 확인했습니다. A3는 A2 Action 서버를 호출하지 않는 독립 모의 구현입니다. A4 공유존 예외 모의 검사 12개를 추가했습니다. GUI·HTTP 서버·실물 Nav2 연동은 아직 미완료입니다. 작업 완료 후 출발점 복귀는 2차 범위입니다.

## PC 터미널 — A3 데모

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/backup_server/run_demo.py --live-robot1
```

두 작업은 모두 가상이며, 실물 1번은 별도 상태만 표시합니다. 실물 조회가 필요 없으면 `--live-robot1`을 생략합니다. 상세 실행법은 각 하위 README와 MONITOR.md를 참고하세요.

## PC 터미널 — 로봇 없이 코드 검사

```bash
python3 ~/CAS/cas/backup/backup_server/test_engine.py
python3 ~/CAS/cas/backup/backup_server/test_zone_cases.py
python3 ~/CAS/cas/backup/proposals/cmd_timeout/test_timeout.py
```

## Git 관리

`cas/shared/` 공통 규칙, `cas/primary/` 팀 메인 구현 자리, `cas/backup/` 예비 구현을 사용합니다. main에는 검토 후 PR로 병합합니다. 개인 적용 기록·실행 로그·임시 파일은 올리지 않습니다. 실제 로봇의 기존 Nav2 수정 사항을 덮어쓰지 않습니다.

이 PC에서는 기존 `~/CAS/monitor.py`, `~/CAS/backup_server`, `~/CAS/mock_connection`, `~/CAS/proposals` 경로를 로컬 바로가기로 유지합니다. 이 바로가기는 Git에 올리지 않으므로 팀원은 위의 정식 경로를 사용합니다.

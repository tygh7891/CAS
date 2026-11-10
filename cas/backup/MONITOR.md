# CAS (Collision Avoidance System)

Pinky Pro 2대 중앙 관제 프로젝트. 이 문서는 읽기 전용 모니터 안내입니다. A2 모의 Action 및 A3 모의 상태 흐름은 각 하위 폴더 안내를 참고하세요. 실물 공유존 주행 제어는 아직 미구현입니다.

## 실행

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/monitor.py
```

Ctrl+C로 종료합니다. 실행에 실패하면 터미널에 표시되는 오류를 확인하세요.

한 번만 확인하고 종료하려면:

```bash
python3 ~/CAS/cas/backup/monitor.py --duration 15 --json
```

- pinky1: robot_1 (domain 14), ROS_DOMAIN_ID=14
- pinky2: robot_2 (domain 30), ROS_DOMAIN_ID=30
- 로봇별 별도 프로세스로 odom, scan, battery/voltage, battery/percent를 구독합니다.
- 각 로봇에서 기본 구동 프로그램이 실행 중이어야 합니다. SSH 인증은 필요하지 않습니다.
- RECEIVING: odom 수신 후 3초 이내. STALE: 마지막 odom 수신 후 3초 초과. WAITING: odom 수신 이력 없음.
- 연결 표시는 오도메트리 수신 상태이며 네트워크 단절 원인을 판정하지 않습니다. 배터리 등 개별 토픽의 수신 시간도 따로 표시합니다. 배터리는 약 5초 주기를 고려하여 12초 초과 시 수신 지연으로 표시합니다.
- 위치는 각 로봇의 odom 좌표입니다. 두 로봇의 좌표를 공통 지도상 위치로 직접 비교하면 안 됩니다.
- 토픽 수신 시간은 PC의 단조 증가 시계를 사용합니다. 수신 freshness가 센서 원본 timestamp의 freshness를 보장하지는 않습니다.
- 이동 명령, 목적지, 정지 명령을 발행하지 않으며 로봇 설정을 수정하지 않습니다.
- 1번에는 cmd_vel 타임아웃 수정과 바퀴를 띄운 시험을 수행했습니다. 이는 서버 통신 단절 전체의 정지를 보장하지 않습니다. proposals/cmd_timeout 안내를 참고하세요.

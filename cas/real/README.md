# CAS 실물 1차 시나리오

독립 중앙 서버와 PyQt5 GUI로 Pinky Pro 두 대를 제어합니다.
로봇1은 1→B, 로봇2는 2→A로 이동하고, 중앙 공유존 진입권을 순차 부여합니다.
각 목적지에서 제자리 한 바퀴 회전 후 정지합니다.
반복 시험용 **출발점 복귀**는 현재 작업 취소·정지 후 한 대씩 초기 위치와 방향으로 복귀합니다.

## 현재 검증 상태 — 2026-11-12

- 실물 /map 수신, 두 로봇 TF 위치 표시, 단독 주행과 출발점 복귀: 사용자 확인.
- 기존 작업 폴더에서 1차 시나리오 두 번 연속 완료 후 복귀: 사용자 로그로 확인.
- 세 번째 실행에서 로봇1 회전 중 `Spin COLLISION_AHEAD=703` 발생: **미해결**.
- 최신 대기점 계산(공유존까지 중심 최단거리 16cm): 로봇 충전으로 **실물 미검증**.
- 이 브랜치로 분리한 패키지: 비주행 테스트 12개 통과, **분리 후 실물 재실행은 미검증**.

따라서 모든 실물 조건이 최종 검증된 버전이라고 간주하지 않습니다.
자세한 작업 이력과 다음 순서는 [HANDOFF.md](HANDOFF.md), 실물 이벤트는
[validation/physical_session_20261112.jsonl](validation/physical_session_20261112.jsonl)을 확인하세요.

## 포함 범위

- PC 중앙 관제, 실물 로봇별 ROS domain Worker(14 / 30).
- 실시간 기본 지도(로봇1 /map)·로봇 위치/방향·상태·공유존 표시.
- 대기점 이동 → 단독 진입권 → 목적지 이동 → 회전 → 정지·완료.
- 본체의 목적지 방향 전체 이탈을 관측하면 이동 중 권한 해제.
- 작업 취소, 순차 출발점 복귀와 재시험.
- 최소 정지 처리: 위치/odom 수신 중단, Action 실패, 무권한 진입.

이전 CAS의 MOCK/Gazebo 실행, 속도 릴레이·lease, 경로 감사,
경로 편차 2.5cm·로봇 간 22cm 제한, 복잡한 모의 초기화 기능은 포함하지 않습니다.
통신 끊김/블락존/우회, 자동 공유존 생성, 로봇 간 직접 통신도 구현 범위가 아닙니다.
저장소에 원래 있던 Pinklab 패키지는 main 그대로 유지합니다.

## 실행 준비

PC: ROS2 Jazzy, nav2_msgs, tf2_ros, PyQt5, PyYAML이 필요합니다.
실행 스크립트는 `/usr/bin/python3`를 사용합니다. 해당 Python에서 PyQt5가 import돼야 합니다.

두 로봇은 팀원이 구성한 Keepout 지원 `pinky_navigation` launch가 설치된 상태를 전제로 합니다.
원본 Pinklab launch만 설치된 새 로봇에 이 YAML 하나만 전달해서 재현되는 구성은 아닙니다.
현재 두 로봇의 설치 launch는 확인됐으며, 참고본은 `config/launch_reference/`에 있습니다.

### 로봇1 SSH (192.168.14.64), 로봇2 SSH (192.168.14.75)

각 로봇에서 두 터미널을 사용합니다. 기존 실행이 있다면 중복 실행하지 않습니다.
기존 팀원 FMS Worker와 다른 제어 프로그램은 종료합니다.

터미널 A — 기본 구동:

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/local_setup.bash
export ROS_DOMAIN_ID=14  # 로봇2는 30
ros2 launch pinky_bringup bringup_robot.launch.xml
```

터미널 B — Nav2:

```bash
source /opt/ros/jazzy/setup.bash
source ~/pinky_pro/install/local_setup.bash
export ROS_DOMAIN_ID=14  # 로봇2는 30
ros2 launch pinky_navigation bringup_launch.xml map:=/home/pinky/dev_ws/maps/fleet_world_new.yaml params_file:=/home/pinky/cas_nav2_test.yaml
```

두 로봇에 `fleet_world_new.yaml/pgm`, `fleet_x_keepout_new.yaml/pgm`이
`/home/pinky/dev_ws/maps/`에 있어야 합니다. 저장소 `maps/`의 확인된 복사본을 사용할 수 있습니다.

**3cm 도착 오차를 재시작 후 유지하려면** `config/robot_nav2.yaml`을
각 로봇의 `/home/pinky/cas_nav2_test.yaml`에 전달합니다. 이 파일은 확인한 기존 설정에
실물 시험에서 적용한 footprint·1cm 해상도·Keepout inflation과 최신 도착 허용 오차를
반영해 재구성한 배포용 설정입니다. 원본 설치 YAML은 덮어쓰지 않습니다.

PC에서 (저장소 루트 기준):

```bash
scp cas/real/config/robot_nav2.yaml pinky@192.168.14.64:/home/pinky/cas_nav2_test.yaml
scp cas/real/config/robot_nav2.yaml pinky@192.168.14.75:/home/pinky/cas_nav2_test.yaml
```

변경된 설정은 다음 Nav2 재시작부터 적용됩니다. 현재 충전 중인 로봇을 원격으로 실행하지 않습니다.

### PC — 관제

```bash
bash cas/real/run_gui.sh
```

실행만으로 이동 목표를 보내지 않습니다. 각 로봇의 초기 위치를 RViz에서 맞추고,
두 로봇의 상태·실제 위치를 GUI와 비교한 뒤 버튼을 사용합니다.
GUI 시험 중 RViz에서 별도 목표를 보내지 않습니다.

- **출발점 복귀**: 정지 확인 후 순차 복귀. 위치 추정을 초기화하지 않습니다.
- **1차 시나리오 시작**: 두 작업을 시작하고, 먼저 대기 준비된 로봇에게 공유존을 허가합니다.
- **전체 작업 취소**: Nav2 Action 취소 요청. 하드웨어 비상정지 버튼이 아닙니다.

기본 지도와 Keepout은 `maps/`, 좌표는 `real_config.json`을 사용합니다.
GUI는 로봇1의 `/map`을 수신하면 그 지도를 표시하고, 수신 전에는 저장 지도임을 표시합니다.
파란 Keepout 강조는 선택 표시입니다. 지도 클릭은 이동 명령이 아닙니다.

## 좌표와 허용 오차

| 항목 | x (m) | y (m) | yaw (rad) |
|---|---:|---:|---:|
| 출발 1 | -0.286 | -0.330 | -2.944 |
| 출발 2 | -0.276 | -0.955 | 3.029 |
| A | -1.400255 | -0.316184 | 진입 경로 방향 |
| B | -1.470270 | -1.011520 | 진입 경로 방향 |

공유존: x=[-0.918066, -0.703603], y=[-0.703771, -0.544142].
대기점: 각 출발→목적지 접근 직선에서 공유존까지 최단거리 16cm인 곳.
Nav2 goal tolerance: xy=3cm, yaw=0.15rad. 실물 위치 오차는 별도로 존재합니다.
본체 footprint: 앞 4.5cm, 뒤 7.5cm, 좌우 5.5cm; padding=1cm.
중앙 서버의 영역 점유 판단은 이 외곽을 포함하는 반경 10.8cm를 사용합니다.

## 비주행 검증

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest discover -s cas/real -p 'test_*.py'
```

테스트는 가상 입력으로 중앙 로직·GUI를 확인하며 실제 ROS 목표를 보내지 않습니다.
실행 로그는 `cas/real/logs/`에 저장되고 Git에서 제외됩니다. SSH 비밀번호는 저장하지 않습니다.

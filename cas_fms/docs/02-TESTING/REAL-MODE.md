# 핑키프로 실물 연결 모드

[문서 홈](../README.md) · [Gazebo 시연](LOCAL-DEMO.md)

PyQt GUI, 중앙 FMS 서버, 로봇별 Worker는 노트북에서 실행한다. 기본 ROS 2 도메인은 `robot_1`이 `14`, `robot_2`가 `30`이다. 노트북과 로봇은 서로 ROS 2 통신이 가능한 네트워크에 연결하고 시스템 시간을 맞춘다.

## 노트북에서 읽기 전용으로 연결 확인

`cas_fms/`에서 실행한다. 화면은 수신된 위치와 주행 준비 상태를 보여준다. 읽기 전용 Worker는 속도 발행기를 만들지 않으며, FMS 서버도 시작 요청을 거부한다. `--local-only`와 별도 도메인을 지정하면 노트북 내부의 가상 ROS 2 환경에 연결할 수 있다.

```bash
source /opt/ros/jazzy/setup.bash
python3 -m real_mode
```

실물 점검에서는 로봇의 기존 센서와 엔코더를 읽고 노트북에서 MapServer·AMCL을 실행했다. 두 로봇에서 FMS로 데이터를 받는 순서와 로봇에 파일을 복사하지 않는 실행 명령은 실습 문서에 정리했다. [실물 읽기 전용 실습](../05-ROS2-LEARNING/03-PHYSICAL-READONLY-LAB.md) · [현장 검증 결과](../05-ROS2-LEARNING/05-FIELD-NAV2-CHECK.md#5-이번-실물-점검-기록)

## 향후 실물 주행을 위한 구성

노트북에서 `python3 -m real_nav_config --output pinky_fms_nav2.yaml`로 Nav2 설정을 생성한다. 각 로봇에는 `pinky_navigation`의 FMS 실행 설정과 생성한 Nav2 설정, `fleet_world_new`와 `fleet_x_keepout_new`의 YAML·PGM 파일을 배치한다. 로봇의 `pinky_bringup`은 센서와 모터를 실행하고, 아래 Nav2 실행은 기존 기본 Nav2 실행을 대체한다. 동일 도메인에서는 속도를 제어하는 다른 실행 구성이나 원격 조작을 종료한다.

```bash
ros2 launch pinky_navigation fms_robot_navigation.launch.xml \
  map:=/path/to/fleet_world_new.yaml \
  keepout_mask:=/path/to/fleet_x_keepout_new.yaml \
  params_file:=/path/to/pinky_fms_nav2.yaml
```

이 설정에서 Nav2의 주행·회전 출력은 노트북 Worker를 거쳐 로봇에서 실행되는 속도 조절 노드로 돌아간다. 이 노드는 입력이 0.5초 동안 끊기면 정지 명령을 보낸다. Worker는 명령 경로, 정지 시간 설정, 라이다와 위치의 최신성, 공유 맵·마스크의 일치를 확인한다. 실제 바퀴 정지는 장비에서 확인한다.

현장에서 출발 위치, 대기점, 교차로 경계, 목적지를 확인한 별도 시나리오에 `physical_layout_verified: true`를 설정한다. 실물 주행은 노트북에서 `python3 -m real_mode --scenario 경로 --enable-motion`으로 명시적으로 열 수 있다. 두 로봇을 출발점에 놓고 RViz에서 AMCL 초기 위치와 방향을 잡는다. FMS는 두 로봇이 출발점에 정지해 있음을 확인한 뒤 시작 버튼을 활성화한다. 시연 뒤에는 각 로봇을 출발점으로 옮겨 다시 위치를 잡는다. 교차로 안에서 취소했다면 점유를 해소하고 출발 위치를 확인한 뒤 FMS를 재시작한다.

## 노트북 검증 결과

로컬 ROS 2 도메인에서 가상 핑키프로 두 대와 실물용 Nav2 실행 구성을 연결했다. 읽기 전용 모드에서 두 위치를 받았고 시작 요청은 거부됐다. 주행 경로 시험에서 두 대 모두 교차로를 순차 통과해 목적지에 도착했다. 1번의 회전은 완료됐고, 2번의 회전은 Nav2의 충돌 검사로 중단됐다. 별도 노트북 시험에서 Nav2 속도 조절 노드는 입력이 끊긴 뒤 약 0.48초에 속도 0을 발행했다.

후속 실물 점검에서는 두 대의 네트워크와 데이터 수신을 확인했다. 실제 주행, 회전 지점 여유 공간, 실제 바퀴의 정지 동작은 장비 시험에 남겨 두었다. [실물 점검 기록](../05-ROS2-LEARNING/05-FIELD-NAV2-CHECK.md#5-이번-실물-점검-기록)

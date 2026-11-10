# 가상 로봇과 Gazebo 실습

[학습 홈](README.md) · [ROS 2 기초](01-ROS2-BASICS.md) · [다음 실습 · 실물 읽기 전용](03-PHYSICAL-READONLY-LAB.md)

## 1. 좌표 보간 시연으로 FMS 확인

노트북 터미널에서 실행한다. `local_demo`는 FMS 서버, PyQt 창, 가상 Worker 두 개를 연다. Worker가 경유점 사이의 좌표를 계산해 서버로 보내므로 교차로 통과 순서와 화면 상태를 확인할 수 있다.

```bash
cd ~/Pinky_Fleet_Coordinator/CAS/cas_fms
python3 -m local_demo
```

**시연 시작**을 누른다. 두 대가 대기점으로 이동하고, 한 대씩 교차로를 통과한다. 목적지 회전이 끝나면 **다시 시작**으로 각 출발점에서 재시연할 수 있다. 창을 닫으면 이 시연에서 실행한 서버와 Worker가 종료된다. [로컬 가상 시연](../02-TESTING/LOCAL-DEMO.md)

## 2. Gazebo 실행

노트북에 ROS 2 Jazzy, Gazebo Harmonic, `colcon`, `ros_gz`, Nav2, RViz2와 시스템 Python의 PyQt5·Flask·PyYAML을 사용한다. `source`는 현재 터미널에 ROS 2 명령과 패키지 경로를 불러온다. 터미널을 새로 열 때마다 해당 명령을 실행한다.

```bash
cd ~/Pinky_Fleet_Coordinator/CAS/cas_fms
source /opt/ros/jazzy/setup.bash
gz sim --versions
ros2 pkg prefix ros_gz_bridge
ros2 pkg prefix nav2_bringup
/usr/bin/python3 -c 'import PyQt5, flask, yaml, rclpy'
```

아래 두 방법 중 하나로 실행한다. 시연 중인 Gazebo FMS 창을 닫고 실행하면 같은 가상 도메인에 로봇을 중복으로 띄우는 일을 피할 수 있다.

```bash
./run_gazebo_demo.sh --port 18765
```

스크립트가 하는 빌드와 실행을 터미널에서 나눠서 하려면 다음 세 명령을 차례대로 실행한다. `colcon`은 Pinky 모델 패키지와 Nav2 실행 설정을 `.gazebo_build/install` 아래에 준비한다. 두 번째 `source`로 그 패키지를 현재 터미널에 추가한다.

```bash
colcon --log-base .gazebo_build/log build \
  --base-paths ../pinky_description ../pinky_navigation \
  --build-base .gazebo_build/build \
  --install-base .gazebo_build/install --symlink-install
source .gazebo_build/install/local_setup.bash
/usr/bin/python3 -m gazebo_demo --port 18765
```

Gazebo에는 위에서 내려다본 X자 통로와 핑키프로 두 대가 보인다. 흰색은 주행 통로이고 청회색은 진입 제한 구역이다. **CAS FMS · Gazebo** 창에서 두 로봇이 준비되면 시연 버튼 세 개가 활성화된다. `gazebo_demo`는 맵으로 가상 공간을 만들고 로봇 모델, 브리지, Nav2와 FMS를 실행한다. [실행 스크립트](../../run_gazebo_demo.sh) · [가상 공간 생성 코드](../../gazebo_scene.py) · [SLAM-Nav2 2강 · Gazebo](../../../../../dev_ws/SLAM-Nav2/present_02_ROS2_Gazebo_PKG.html) · [SLAM-Nav2 7강 · Nav2 실행 설정](../../../../../dev_ws/SLAM-Nav2/present_07_ROS2_Nav2_PKG_설정.html)

## 3. ROS 2 메시지와 좌표를 직접 읽기

Gazebo FMS를 켜 둔 채 노트북에서 새 터미널을 연다. 아래 명령은 1번 가상 로봇의 ROS 2 도메인 `114`에서 실행한다. 2번을 관찰하려면 `ROS_DOMAIN_ID`를 `130`으로 바꾸고 같은 명령을 실행한다. `--once`는 메시지 하나를 읽고 종료한다.

```bash
source /opt/ros/jazzy/setup.bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=114 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_STATIC_PEERS=''
ros2 topic list --no-daemon --spin-time 2 -t
ros2 topic echo /scan sensor_msgs/msg/LaserScan \
  --qos-reliability best_effort --once --timeout 5 --field header
ros2 topic echo /odom nav_msgs/msg/Odometry \
  --once --timeout 5 --field pose.pose.position
ros2 action list -t
ros2 action info /navigate_to_pose
```

`/scan`의 `frame_id`에서 라이다 좌표계를 확인한다. 토픽 이름 뒤의 `sensor_msgs/msg/LaserScan`은 메시지 형식이다. `/odom`의 `x`, `y`는 `odom` 좌표계 값이다. FMS 지도상의 위치를 확인하려면 TF를 읽는다. `tf2_echo`는 계속 출력하므로 확인 후 `Ctrl+C`를 누른다.

```bash
ros2 run tf2_ros tf2_echo map base_footprint
```

`Translation`의 앞 두 값이 지도 기준 `x`, `y`다. 시작 시 한두 번 좌표계를 찾지 못했다는 메시지가 나오면 TF 수신을 기다린다. 계속 출력되지 않으면 FMS 연결 상태와 도메인 번호를 먼저 확인한다. [ROS2 2강 · 기초 명령](../../../../../dev_ws/ROS2/docs/present_02_ROS_기초명령.html) · [ROS2 10강 · TF 구독](../../../../../dev_ws/ROS2/docs/present_10_TF_frame을_구독하고_좌표계_사이의_정보를_활용하는_법.html)

## 4. 교차로 진입권과 작업 결과 확인

FMS 창에서 **1. 정상 순차 통과**를 누르고 `출발점 초기화 → 대기점 이동 → 진입 대기 → 교차로 통과 → 목적지 이동 → 제자리 회전 → 완료`를 관찰한다. 먼저 통과하는 번호는 대기점 도착 순서에 따라 달라진다. **한 번에 한 대에만 진입권이 있는지** 확인한다.

노트북의 다른 터미널에서 다음 명령을 여러 번 실행하면 화면 뒤의 서버 상태를 읽을 수 있다. `zone_owner`는 현재 진입권을 가진 로봇이고, `zone_waiting`은 대기 목록이다. `robots`에는 로봇별 위치, 작업 단계와 결과가 들어 있다.

```bash
curl -fsS http://127.0.0.1:18765/api/status | python3 -m json.tool
```

정상 주행이 끝나면 **2. 위치 보고 중단·복구**를 누른다. 선행 로봇의 마지막 위치가 화면에 남고, 서버는 **진입 보류** 상태로 진입권을 유지한다. 5초 뒤 새 위치로 선행 로봇의 이탈을 확인하면 후행 로봇이 출발한다. **3. 교차로 내 작업 취소**를 누르면 두 대가 출발점에서 다시 시작하고 선행 로봇이 교차로에 진입한 시점에 두 대가 정지한다. [시연 시나리오](../02-TESTING/LOCAL-DEMO.md#시연-시나리오)

**[프로젝트 구현·검증 기록]** 초기 시험에서 2번 로봇의 회전이 충돌 검사로 중단됐다. Gazebo에서만 A의 회전 위치를 벽에서 약 11cm 떨어진 쪽으로 조정한 뒤 세 버튼을 다시 시험했다. 취소 뒤 **1. 정상 순차 통과**를 눌러 두 대가 출발점으로 복귀하고 정상 통과하는 것까지 확인했다. [Gazebo 시나리오 좌표](../../gazebo_scenario.yaml)

## 5. 코드와 시험 연결

| 확인할 동작 | 코드 위치 |
| --- | --- |
| 화면에서 누른 시작·취소가 HTTP 요청이 되는 과정 | [PyQt Presenter](../../pinky_fms_gui/presentation.py) · [Flask API](../../pinky_fms_server/http.py) |
| 진입권을 한 건만 유지하고 위치가 확인된 뒤 해제하는 규칙 | [관제 도메인](../../pinky_fms_server/domain.py) · [서버 유스케이스](../../pinky_fms_server/application.py) |
| `NAVIGATE`와 `SPIN`이 ROS 2 Action 목표가 되는 과정 | [공통 Nav2 Worker](../../ros_nav_worker.py) · [Gazebo 출발점 초기화](../../gazebo_worker.py) |

`cas_fms/`에서 테스트와 코딩 기준 검사를 실행한다. `ruff`나 `pytest`가 없는 경우 [프로젝트 의존성](../../requirements.txt)을 설치한 Python 환경에서 실행한다.

```bash
ruff check .
ruff format --check .
python3 -m pytest -q
```

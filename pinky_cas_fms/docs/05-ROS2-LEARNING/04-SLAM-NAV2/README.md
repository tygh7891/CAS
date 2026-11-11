# 04 · 지도 만들기에서 목표 주행까지

[학습 목차](../README.md) · [강의 출처표](../00-START/SOURCE-INDEX.md) · [용어](../00-START/GLOSSARY.md)

**목표** · 지도를 만드는 일, 기존 지도에서 내 위치를 찾는 일, 목표로 주행하는 일을 구분한다. 강의실 Ubuntu 노트북에서 지도 좌표를 계산한 뒤 Gazebo 로봇 한 대로 확인한다.

| 필요한 이론 | HTML 원본에서 볼 슬라이드 |
|---|---|
| URDF/Xacro 모델과 Gazebo–ROS 브리지 | [NAV-01](../00-START/SOURCE-INDEX.md#nav-01) 22·33·68·77번, [NAV-02](../00-START/SOURCE-INDEX.md#nav-02) 15·18·28·35번 |
| SLAM과 지도 저장 | [NAV-03](../00-START/SOURCE-INDEX.md#nav-03) 7·9·11·19·23번, [PINKY-03](../00-START/SOURCE-INDEX.md#pinky-03) 4·5·7·10·14번 |
| AMCL, 초기 위치, 비용 지도 | [NAV-04](../00-START/SOURCE-INDEX.md#nav-04) 20·24·35·40번, [NAV-05](../00-START/SOURCE-INDEX.md#nav-05) 4·6·8·10·14번, [NAV-07](../00-START/SOURCE-INDEX.md#nav-07) 25·67·88·99번 |
| 액션 결과와 경유점 | [NAV-06](../00-START/SOURCE-INDEX.md#nav-06) 9·13·17·40번, [PINKY-04](../00-START/SOURCE-INDEX.md#pinky-04) 6·10·14·18번, [PINKY-05](../00-START/SOURCE-INDEX.md#pinky-05) 9·11·19·24·26번 |

## A · Ubuntu에서 지도와 좌표 읽기

```bash
/usr/bin/python3 04-SLAM-NAV2/map_goal.py
/usr/bin/python3 04-SLAM-NAV2/map_goal.py --row 1 --yaw-deg 0
```

기본값에서 위치는 `x=-0.25, y=0.25`, 방향의 `z,w`는 약 `0.707107`이다. 이미지에서 한 줄 아래로 가면 지도 `y`는 0.5 m 줄고, 0° 방향이면 `z=0, w=1`이다. [map_goal.py](map_goal.py)는 예제 픽셀 중심을 지도 좌표와 쿼터니언으로 바꿔 출력한다. 이 공식은 지도 YAML의 원점 각도가 0인 경우를 다룬다. 출력이 빈 공간인지 지도에서 확인하는 작업은 별개다.

예시 [Fleet 지도 YAML](../../../../pinky_dev_ws/maps/fleet_world_new.yaml)은 이미지 파일명, 해상도(1 cm/픽셀), 원점과 점유 판정 기준을 가진다. [Fleet 마스크 YAML](../../../../pinky_navigation/map/fleet_x_keepout_new.yaml)과 해상도·원점을 비교한다. 점유 지도는 환경을 표현하고, 마스크는 진입 제한을 별도로 지정한다.

- **SLAM**은 위치 추정과 지도 작성을 동시에 한다. **Localization**은 기존 지도에서 현재 위치를 추정한다.
- **Costmap**은 센서와 지도 등을 반영해 이동 비용을 계산한다. **Keepout**은 ‘들어가지 말다’라는 뜻이다.
- **Goal**은 목표 위치·방향, **Result**는 액션이 끝난 뒤의 결과다.

## B · Ubuntu에서 Gazebo와 Nav2 준비

Ubuntu 24.04에서 [기본 패키지 설치](../00-START/UBUNTU.md)를 마친 뒤 Gazebo Harmonic, ROS 브리지, SLAM Toolbox, Nav2, 키보드 조작기와 빌드 도구를 설치한다. Gazebo는 가상 로봇을 실행하고, RViz는 ROS에서 받은 지도·센서·경로를 표시한다. [Gazebo 공식 ROS 연동](https://gazebosim.org/docs/harmonic/ros_installation/) · [CAS 실행 명령](../../../../README.md#시뮬레이션)

```bash
sudo apt update
sudo apt install ros-dev-tools python3-yaml ros-jazzy-ros-gz \
  ros-jazzy-gz-ros2-control ros-jazzy-slam-toolbox ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup ros-jazzy-teleop-twist-keyboard
```

`rosdep`은 `package.xml`의 의존성을 설치하고, `colcon`은 실습에 필요한 Pinky 패키지를 빌드한다. 처음 설정하는 노트북에서는 `sudo rosdep init`을 한 번 실행한다. [Jazzy rosdep 안내](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Intermediate/Rosdep.rst)

예시는 CAS가 `~/cas-study-ws/src/CAS`에 있는 경우다. 다른 ROS 워크스페이스를 이미 사용한다면 `cd`의 경로를 바꾸고 `src/CAS`가 실제 저장소 위치와 일치하는지 확인한다. 같은 워크스페이스에는 같은 이름의 Pinky 패키지를 한 벌만 둔다.

빌드 명령은 `dpkg --print-architecture`가 `amd64`인 노트북을 기준으로 한다. CAS는 시뮬레이션 Bringup 의존성에 `pinky_mujoco`를 포함하며, 이 패키지는 `arm64`에서 설치 동작이 다르다. [Bringup 의존성](../../../../pinky_bringup/package.xml) · [MuJoCo 패키지 설정](../../../../pinky_mujoco/setup.py)

```bash
cd "$HOME/cas-study-ws"
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths src/CAS/pinky_bringup src/CAS/pinky_description \
  src/CAS/pinky_gz_sim src/CAS/pinky_mujoco src/CAS/pinky_navigation --ignore-src -y
colcon build --packages-up-to pinky_description pinky_gz_sim pinky_bringup pinky_navigation
```

빌드 요약에 `Failed`가 없고 `~/cas-study-ws/install/setup.bash`가 생겼는지 확인한다. **C와 D에서 새로 여는 모든 터미널**을 [학습 폴더](../README.md#실행-경로)에서 열고 아래 두 줄로 ROS 2와 빌드한 패키지를 불러온다. 워크스페이스 경로가 다르면 `install/setup.bash`의 경로를 맞춘다.

```bash
source 02-ROS2/lab_env.bash 51
source "$HOME/cas-study-ws/install/setup.bash"
```

한 터미널에서 아래로 설치와 환경을 확인한다. `jazzy`, `51`, `LOCALHOST`와 Gazebo 버전 및 두 패키지의 설치 경로가 출력되어야 한다. PyYAML 가져오기는 성공하면 출력 없이 끝난다.

```bash
printenv ROS_DISTRO ROS_DOMAIN_ID ROS_AUTOMATIC_DISCOVERY_RANGE
gz sim --versions
ros2 pkg prefix pinky_gz_sim
ros2 pkg prefix pinky_navigation
/usr/bin/python3 -c 'import yaml'
```

## C · 시뮬레이션에서 지도 만들기

아래 명령은 각각 다른 터미널에서 B의 공통 환경을 불러온 뒤 번호순으로 실행한다. 터미널 1의 Gazebo 창에서 로봇이 보이면 SLAM을 시작한다.

```bash
# 터미널 1 · 가상 로봇 시작
ros2 launch pinky_bringup bringup_sim.launch.xml sim:=gz
```

```bash
# 터미널 2 · SLAM
ros2 launch pinky_navigation gz_map_building.launch.xml
```

```bash
# 터미널 3 · RViz로 지도 보기
ros2 launch pinky_navigation gz_map_view.launch.xml
```

```bash
# 터미널 4 · 가상 로봇을 저속 조작
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

터미널 5에서 시뮬레이션 시각과 라이다 메시지를 하나씩 확인한다. `/map`의 발행자 수가 1 이상인지, RViz에서 지도가 채워지는지 본다. 메시지가 10초 안에 안 오면 Gazebo가 일시정지 상태인지, 모든 터미널에서 B의 환경을 불러왔는지 확인한다.

```bash
# 터미널 5 · 토픽 확인
timeout 10s ros2 topic echo /clock rosgraph_msgs/msg/Clock --once
timeout 10s ros2 topic echo /scan sensor_msgs/msg/LaserScan --once \
  --qos-reliability best_effort --field header
ros2 topic info /map
```

터미널 4에 표시된 키로 주변을 조금 주행하고 정지한다. 같은 터미널 5에서 실습마다 새 폴더를 만들어 지도를 저장한다.

```bash
# 터미널 5 · 지도 저장
mkdir -p "$HOME/cas-study-maps"
STUDY_MAP_DIR="$(mktemp -d "$HOME/cas-study-maps/session.XXXXXX")"
STUDY_MAP="$STUDY_MAP_DIR/map"
ros2 run nav2_map_server map_saver_cli -f "$STUDY_MAP" --fmt pgm \
  --ros-args -p use_sim_time:=true
ls -l "$STUDY_MAP.yaml" "$STUDY_MAP.pgm"
head -n 5 "$STUDY_MAP.yaml"
```

두 파일이 생성되고 YAML의 `image` 값이 `map.pgm`인지 확인한다. 터미널 1의 Gazebo와 터미널 5는 열어 둔다. 터미널 2의 SLAM, 3의 지도용 RViz, 4의 조작기를 Ctrl+C로 종료한다. [Nav2 Jazzy 지도 저장 명령](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_map_server/src/map_saver/main_cli.cpp)

## D · 기존 지도에서 위치 추정하고 목표 하나 주행

새로 만든 지도는 팀 X자 코스와 좌표가 다를 수 있다. 이 시뮬레이션 실습에서는 [sim_params.py](sim_params.py)로 CAS의 Nav2 설정에서 코스 전용 keepout 필터를 뺀 사본을 지도 폴더에 만든다. C에서 지도를 저장한 터미널 5에서 계속한다. 다시 실행할 때 `nav2.yaml`이 이미 있으면 `SIM_PARAMS`의 파일명을 바꾼다.

```bash
# 터미널 5 · C에서 지도를 저장한 터미널
NAV_SHARE="$(ros2 pkg prefix --share pinky_navigation)"
SIM_PARAMS="$STUDY_MAP_DIR/nav2.yaml"
/usr/bin/python3 04-SLAM-NAV2/sim_params.py "$NAV_SHARE/params/nav2_params.yaml" \
  "$SIM_PARAMS" && \
  ros2 launch pinky_navigation gz_bringup_launch.xml \
    map:="$STUDY_MAP.yaml" params_file:="$SIM_PARAMS"
```

```bash
# 터미널 3 · 지도용 RViz를 종료한 터미널
ros2 launch pinky_navigation gz_nav2_view.launch.xml
```

1. RViz의 **2D Pose Estimate**로 Gazebo에서 보이는 로봇의 실제 위치와 방향을 넣는다. 라이다 점이 지도 벽과 맞는지 확인한다.
2. 터미널 2에서 `/amcl`이 `active`, `/navigate_to_pose`의 액션 서버가 1개 이상인지 확인한다. `tf2_echo`에서 `Translation`과 `Rotation`이 출력되면 Ctrl+C로 끝낸다.
3. RViz의 **Nav2 Goal**을 선택하고 가까운 빈 공간을 클릭·드래그한다. 경로가 그려지고 가상 로봇이 이동하는지 확인한다. RViz 또는 터미널 5에서 목표 도달 결과를 확인한 뒤 RViz·Nav2·Gazebo를 Ctrl+C로 종료한다.

```bash
ros2 lifecycle get /amcl
ros2 action info /navigate_to_pose
ros2 run tf2_ros tf2_echo map base_footprint
```

### 확장 · Python과 Pinky에서 연결하기

NAV-06의 Python 액션 예제는 `BasicNavigator.goToPose()`, `isTaskComplete()`, `getResult()`로 목표 전송·대기·결과 확인을 나눈다. PINKY-05는 이를 주피터로 실행하고 경유점을 다룬다. [Jazzy Simple Commander API](https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/)

PINKY-04 10·14번의 `/clicked_point`는 RViz에서 찍은 점, `/amcl_pose`는 추정된 로봇 포즈다. 실제 로봇에서는 학습용 Gazebo 명령 대신 [저장소의 실물 Nav2 절차](../../../../README.md#navigation2)를 따른다. 본 실습의 필수 목표는 시뮬레이션에서 위치와 주행 목표를 구분하는 것이다.

**통과 기준** · RViz에서 보이는 초기 위치·목표·경로·현재 위치를 각각 가리킬 수 있다. 파일에서 바뀐 값과 액션에서 넘어가는 값을 구분한 뒤 [05 FMS](../05-FMS/README.md)로 간다.

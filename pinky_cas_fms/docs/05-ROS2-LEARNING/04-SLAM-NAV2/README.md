# 04 · 지도 만들기에서 목표 주행까지

[학습 목차](../README.md) · [강의 출처표](../00-START/SOURCE-INDEX.md) · [용어](../00-START/GLOSSARY.md)

**목표** · 지도를 만드는 일, 기존 지도에서 내 위치를 찾는 일, 목표로 주행하는 일을 구분한다. 먼저 Mac에서 지도 좌표를 계산하고, 강의실에서는 한 대의 Gazebo 로봇으로 동작을 확인한다.

| 필요한 이론 | HTML 원본에서 볼 슬라이드 |
|---|---|
| URDF/Xacro 모델과 Gazebo–ROS 브리지 | [NAV-01](../00-START/SOURCE-INDEX.md#nav-01) 22·33·68·77번, [NAV-02](../00-START/SOURCE-INDEX.md#nav-02) 15·18·28·35번 |
| SLAM과 지도 저장 | [NAV-03](../00-START/SOURCE-INDEX.md#nav-03) 7·9·11·19·23번, [PINKY-03](../00-START/SOURCE-INDEX.md#pinky-03) 4·5·7·10·14번 |
| AMCL, 초기 위치, 비용 지도 | [NAV-04](../00-START/SOURCE-INDEX.md#nav-04) 20·24·35·40번, [NAV-05](../00-START/SOURCE-INDEX.md#nav-05) 4·6·8·10·14번, [NAV-07](../00-START/SOURCE-INDEX.md#nav-07) 25·67·88·99번 |
| 액션 결과와 경유점 | [NAV-06](../00-START/SOURCE-INDEX.md#nav-06) 9·13·17·40번, [PINKY-04](../00-START/SOURCE-INDEX.md#pinky-04) 6·10·14·18번, [PINKY-05](../00-START/SOURCE-INDEX.md#pinky-05) 9·11·19·24·26번 |

## A · Mac 또는 Ubuntu에서 지도와 좌표 읽기

```bash
python3 04-SLAM-NAV2/map_goal.py
python3 04-SLAM-NAV2/map_goal.py --row 1 --yaw-deg 0
```

기본값에서 위치는 `x=-0.25, y=0.25`, 방향의 `z,w`는 약 `0.707107`이다. 이미지에서 한 줄 아래로 가면 지도 `y`는 0.5 m 줄고, 0° 방향이면 `z=0, w=1`이다. [map_goal.py](map_goal.py)는 예제 픽셀 중심을 지도 좌표와 쿼터니언으로 바꿔 출력한다. 이 공식은 지도 YAML의 원점 각도가 0인 경우를 다룬다. 출력이 빈 공간인지 지도에서 확인하는 작업은 별개다.

예시 [Fleet 지도 YAML](../../../../pinky_dev_ws/maps/fleet_world_new.yaml)은 이미지 파일명, 해상도(1 cm/픽셀), 원점과 점유 판정 기준을 가진다. [Fleet 마스크 YAML](../../../../pinky_navigation/map/fleet_x_keepout_new.yaml)과 해상도·원점을 비교한다. 점유 지도는 환경을 표현하고, 마스크는 진입 제한을 별도로 지정한다.

- **SLAM**은 위치 추정과 지도 작성을 동시에 한다. **Localization**은 기존 지도에서 현재 위치를 추정한다.
- **Costmap**은 센서와 지도 등을 반영해 이동 비용을 계산한다. **Keepout**은 ‘들어가지 말다’라는 뜻이다.
- **Goal**은 목표 위치·방향, **Result**는 액션이 끝난 뒤의 결과다.

## B · Ubuntu 준비

ROS 2 Jazzy, Gazebo Harmonic, `ros_gz`, SLAM Toolbox, Nav2, RViz, `teleop_twist_keyboard`와 Python의 PyYAML이 필요하다. 강의실에서 빌드한 CAS/Pinky 워크스페이스에 `pinky_bringup`, `pinky_gz_sim`, `pinky_navigation`이 있는지 확인한다. ROS와 Gazebo 조합 및 CAS 실행 진입점은 아래 문서를 따른다. [Gazebo 공식 ROS 연동](https://gazebosim.org/docs/harmonic/ros_installation/) · [CAS 실행 명령](../../../../README.md#시뮬레이션)

워크스페이스를 처음 준비한다면, ROS APT 저장소와 `rosdep` 초기 설정을 마친 Ubuntu에서 아래를 실행한다. 예시는 `~/pinky_pro/src/CAS`에 이 브랜치를 받아 둔 경우다. 같은 이름의 ROS 패키지는 한 벌을 사용한다.

```bash
sudo apt install ros-dev-tools ros-jazzy-ros-gz ros-jazzy-slam-toolbox \
  ros-jazzy-teleop-twist-keyboard python3-yaml
cd "$HOME/pinky_pro"
source /opt/ros/jazzy/setup.bash
rosdep update
rosdep install --from-paths src/CAS/pinky_bringup src/CAS/pinky_description \
  src/CAS/pinky_gz_sim src/CAS/pinky_mujoco src/CAS/pinky_navigation --ignore-src -r -y
colcon build --packages-up-to pinky_description pinky_gz_sim pinky_bringup pinky_navigation
```

**B~D의 모든 터미널**을 [학습 폴더](../README.md#실행-경로)에서 열고 공통 환경을 적용한다. `~/pinky_pro`는 예시이므로 실제 워크스페이스로 바꾼다. 이 절에서는 실물의 도메인 대신 로컬 실습 도메인 51을 쓴다.

```bash
source 02-ROS2/lab_env.bash 51
source "$HOME/pinky_pro/install/setup.bash"
ros2 pkg prefix pinky_gz_sim
ros2 pkg prefix pinky_navigation
```

패키지 경로가 출력되는지 확인한다. [ROS2-01](../00-START/SOURCE-INDEX.md#ros2-01)의 환경 설정, NAV-01·02의 모델·시뮬레이터 준비에 해당한다.

## C · 시뮬레이션에서 지도 만들기

아래 명령은 각각 다른 터미널에서 위 공통 환경을 불러온 뒤 실행한다.

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

Gazebo에서 모델이 보이고 RViz에서 `/map`이 채워지는지 확인한다. 조작 키는 터미널 4에 표시된다. 주변을 조금 주행하고 정지한 뒤 아래처럼 저장한다.

```bash
# 터미널 5 · 새 실습 파일 만들기
mkdir -p "$HOME/cas-study-maps"
STUDY_MAP="$HOME/cas-study-maps/session_01"
test ! -e "$STUDY_MAP.yaml" && test ! -e "$STUDY_MAP.pgm" && \
  ros2 run nav2_map_server map_saver_cli -f "$STUDY_MAP" --fmt pgm \
  --ros-args -p use_sim_time:=true
ls -l "$STUDY_MAP.yaml" "$STUDY_MAP.pgm"
```

이미 같은 이름의 지도가 있으면 새 이름을 정하고 D에도 같은 이름을 쓴다. 저장한 YAML의 `image` 값이 함께 저장된 이미지를 가리키는지 확인한다. Gazebo는 켜 두고 SLAM, 지도용 RViz, 조작기를 Ctrl+C로 종료한 다음 D로 간다.

## D · 기존 지도에서 위치 추정하고 목표 하나 주행

새로 만든 지도는 팀 X자 코스와 좌표가 다를 수 있다. **이 시뮬레이션 실습에서만** [sim_params.py](sim_params.py)로 CAS의 Nav2 설정에서 코스 전용 keepout 필터를 뺀 사본을 만든다. 실제 Pinky의 지도나 CAS 원본 설정은 그대로 사용한다. 사본 경로가 이미 존재하면 새 이름을 사용한다.

```bash
# 터미널 2 · 공통 환경을 불러온 Ubuntu 학습 폴더
NAV_SHARE="$(ros2 pkg prefix --share pinky_navigation)"
SIM_PARAMS="$HOME/cas-study-maps/nav2-session_01.yaml"
python3 04-SLAM-NAV2/sim_params.py "$NAV_SHARE/params/nav2_params.yaml" \
  "$SIM_PARAMS" && \
  ros2 launch pinky_navigation gz_bringup_launch.xml \
    map:="$HOME/cas-study-maps/session_01.yaml" params_file:="$SIM_PARAMS"
```

```bash
# 터미널 3 · 공통 환경
ros2 launch pinky_navigation gz_nav2_view.launch.xml
```

1. RViz의 **2D Pose Estimate**로 Gazebo에서 보이는 로봇의 실제 위치와 방향을 넣는다. 라이다 점이 지도 벽과 맞는지 확인한다.
2. 관찰 터미널에서 아래 명령으로 목표 액션과 지도 기준 TF가 보이는지 확인한다. `tf2_echo`는 확인 후 Ctrl+C로 끝낸다.
3. RViz의 **Nav2 Goal**을 선택하고 가까운 빈 공간을 클릭·드래그한다. 경로, 실제 이동, 목표 도달을 차례대로 본다. 정상 종료 시 RViz·Nav2·Gazebo를 닫는다.

```bash
ros2 action info /navigate_to_pose
ros2 run tf2_ros tf2_echo map base_footprint
```

### 확장 · Python과 Pinky에서 연결하기

NAV-06의 Python 액션 예제는 `BasicNavigator.goToPose()`, `isTaskComplete()`, `getResult()`로 목표 전송·대기·결과 확인을 나눈다. PINKY-05는 이를 주피터로 실행하고 경유점을 다룬다. [Jazzy Simple Commander API](https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/)

PINKY-04 10·14번의 `/clicked_point`는 RViz에서 찍은 점, `/amcl_pose`는 추정된 로봇 포즈다. 실제 로봇에서는 학습용 Gazebo 명령 대신 [저장소의 실물 Nav2 절차](../../../../README.md#navigation2)를 따른다. 본 실습의 필수 목표는 시뮬레이션에서 위치와 주행 목표를 구분하는 것이다.

**통과 기준** · RViz에서 보이는 초기 위치·목표·경로·현재 위치를 각각 가리킬 수 있다. 파일에서 바뀐 값과 액션에서 넘어가는 값을 구분한 뒤 [05 FMS](../05-FMS/README.md)로 간다.

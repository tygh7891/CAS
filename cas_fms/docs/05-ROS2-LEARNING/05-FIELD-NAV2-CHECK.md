# 실물 지도 위치와 Nav2 점검

[학습 홈](README.md) · [이전 실습 · 센서와 FMS](03-PHYSICAL-READONLY-LAB.md) · [실물 주행 준비 조건](../02-TESTING/REAL-MODE.md)

## 1. 노트북에서 지도 위치 띄우기

두 로봇에서 센서와 읽기 전용 오도메트리가 수신된 다음 진행한다. 아래 명령으로 로봇마다 MapServer와 AMCL을 노트북에서 실행한다.

- **MapServer**는 팀이 공유한 YAML·PGM을 읽어 `/map`을 발행한다.
- **AMCL**은 그 지도와 실제 `/scan`, `odom`을 이용해 `map → odom` 변환을 발행한다. FMS는 TF를 따라 지도 기준의 `base_footprint` 위치를 읽는다.
- **Robot State Publisher**는 로봇 중심과 라이다 센서 사이의 변환을 제공한다.

[SLAM-Nav2 4강 · 위치 추정](../../../../../dev_ws/SLAM-Nav2/present_04_Localization.html) · [ROS2 10강 · TF 읽기](../../../../../dev_ws/ROS2/docs/present_10_TF_frame을_구독하고_좌표계_사이의_정보를_활용하는_법.html)

새 노트북 터미널에서 [로봇별 IP·도메인 환경](03-PHYSICAL-READONLY-LAB.md#1-ssh와-ros-2-도메인-확인)을 설정한다. `.gazebo_build/install`이 없다면 [Pinky 패키지 빌드](02-GAZEBO-FMS-LAB.md#2-gazebo-실행)를 먼저 한다. 실제 로봇이 해당 번호의 출발점에서 교차로를 보고 있을 때만 아래 `CAS_AT_START=1`을 사용한다. 다른 위치에 있다면 `0`으로 시작해 RViz에서 현재 위치를 잡는다.

<details>
<summary>노트북의 위치 추정 실행 명령</summary>

~~~bash
source .gazebo_build/install/local_setup.bash
export CAS_AT_START=1
export CAS_LOC_DIR=$(mktemp -d)
python3 - <<'PY'
import os
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from fms_settings import load_scenario

root = Path.cwd()
directory = Path(os.environ["CAS_LOC_DIR"])
navigation = root.parent / "pinky_navigation"
scenario = load_scenario(root / "gazebo_scenario.yaml")
robot = {"14": "robot_1", "30": "robot_2"}[os.environ["CAS_DOMAIN"]]
start = scenario.routes[robot].start
base = yaml.safe_load((navigation / "params/nav2_params.yaml").read_text())
amcl = base["amcl"]["ros__parameters"]
amcl.update(
    set_initial_pose=os.environ["CAS_AT_START"] == "1",
    initial_pose={"x": start.x_m, "y": start.y_m, "z": 0.0, "yaw": start.yaw_rad},
    transform_tolerance=0.04,
    sigma_hit=0.055,
    laser_max_range=6.0,
    laser_min_range=0.09,
    save_pose_rate=-1.0,
)
params = directory / "amcl.yaml"
params.write_text(yaml.safe_dump({"amcl": {"ros__parameters": amcl}}))

launch = ET.Element("launch")
rsp = ET.SubElement(launch, "include", file="$(find-pkg-share pinky_description)/launch/upload_robot.launch.py")
ET.SubElement(rsp, "arg", name="is_sim", value="false")
localization = ET.SubElement(launch, "include", file=str(navigation / "launch/localization_launch.xml"))
for name, value in (("map", str(root / "maps/fleet_world_new.yaml")),
                    ("params_file", str(params)), ("use_sim_time", "false")):
    ET.SubElement(localization, "arg", name=name, value=value)
ET.ElementTree(launch).write(directory / "localization.launch.xml", encoding="unicode")
PY
ros2 launch "$CAS_LOC_DIR/localization.launch.xml"
~~~

</details>

같은 도메인을 설정한 다른 터미널에서 다음을 실행한다. `Translation`의 처음 두 값은 지도 기준 `x, y`이며, `RPY`의 마지막 값은 방향인 `yaw`다.

~~~bash
ros2 run tf2_ros tf2_echo map base_footprint
~~~

RViz에서 초기 위치를 직접 지정할 때는 같은 도메인의 `cas_fms/` 터미널에서 실행한다.

~~~bash
rviz2 -d ../pinky_navigation/rviz/nav2_view.rviz
~~~

**2D Pose Estimate**를 선택하고 현재 위치에서 실제 앞 방향으로 드래그한다. FMS 지도와 실물 배치를 다시 대조한다. [SLAM-Nav2 5강 · RViz에서 현재 위치 지정](../../../../../dev_ws/SLAM-Nav2/present_05_Navigation_PKG_다뤄보기.html) · [Pinky 4강 · 저장한 맵 사용](../../../../../dev_ws/Pinky/04_present_PinkyPro_내비게이션으로_주행하기.html)

## 2. 지도와 진입 제한 마스크 확인

공유 기본 지도와 마스크는 모두 **192 × 134 셀**, **셀당 1cm**, **원점 (-0.748, -1.041) m**다. 기본 지도는 벽과 빈 공간을 담고, 마스크는 X자 통로 바깥의 진입을 제한한다. 원점이나 해상도가 어긋나면 화면에서 맞아 보이는 통로도 Nav2에서는 다른 위치에 놓일 수 있다. [기본 지도 YAML](../../maps/fleet_world_new.yaml) · [마스크 YAML](../../maps/fleet_x_keepout_new.yaml)

다음 단계에서는 경로를 만드는 **전역 비용 지도**와 로봇 주변을 확인하는 **지역 비용 지도**가 둘 다 마스크를 받는지 확인한다. [Nav2 · 진입 제한 설정](https://docs.nav2.org/rolling/tutorials/general_tutorials/navigation2_with_keepout_filter/navigation2_with_keepout_filter/)

## 3. 주행 목표 없이 Nav2 준비 상태 확인

MapServer와 AMCL을 유지한 채 별도 터미널에서 Nav2와 마스크를 실행한다. 노트북 임시 폴더에서 기존 설정을 읽어 점검용 실행 파일을 만든다. Nav2 속도 조절기의 출력을 `/fms_readonly/nav_output`으로 옮긴다. 이 토픽을 로봇 드라이버에 연결하지 않는다.

<details>
<summary>노트북의 마스크·Nav2 실행 명령</summary>

새 터미널에서 [로봇별 IP·도메인 환경](03-PHYSICAL-READONLY-LAB.md#1-ssh와-ros-2-도메인-확인)을 적용한다. `/cmd_vel`에 발행자나 구독자가 있으면 먼저 팀의 다른 실행 세션을 확인한다.

~~~bash
export CAS_NAV_DIR=$(mktemp -d)
python3 -m real_nav_config --output "$CAS_NAV_DIR/nav2.yaml"
python3 - <<'PY'
import os
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path.cwd()
directory = Path(os.environ["CAS_NAV_DIR"])
source = root.parent / "pinky_navigation/launch"
nav = ET.parse(source / "navigation_launch.xml")
outputs = [remap for remap in nav.iter("remap") if remap.get("from") == "cmd_vel_smoothed"]
assert len(outputs) == 2 and all(remap.get("to") == "cmd_vel" for remap in outputs)
for remap in outputs:
    remap.set("to", "/fms_readonly/nav_output")
isolated_nav = directory / "navigation-isolated.launch.xml"
nav.write(isolated_nav, encoding="unicode")

launch = ET.Element("launch")
for node in ET.parse(source / "fms_robot_navigation.launch.xml").getroot().findall("node"):
    launch.append(deepcopy(node))
assert [node.get("name") for node in launch] == ["keepout_mask", "keepout_info"]
launch.find(".//param[@name='yaml_filename']").set(
    "value", str(root / "maps/fleet_x_keepout_new.yaml")
)
manager = ET.SubElement(
    launch, "node", pkg="nav2_lifecycle_manager", exec="lifecycle_manager",
    name="lifecycle_manager_keepout", output="screen",
)
ET.SubElement(manager, "param", name="autostart", value="true")
ET.SubElement(manager, "param", name="node_names", value="['keepout_mask', 'keepout_info']")
include = ET.SubElement(launch, "include", file=str(isolated_nav))
for name, value in (
    ("params_file", str(directory / "nav2.yaml")),
    ("use_sim_time", "false"),
    ("controller_cmd_vel_topic", "/fms/cmd_vel_raw"),
    ("behavior_cmd_vel_topic", "/fms/cmd_vel_raw"),
):
    ET.SubElement(include, "arg", name=name, value=value)
ET.ElementTree(launch).write(directory / "navcheck.launch.xml", encoding="unicode")
PY
ros2 launch "$CAS_NAV_DIR/navcheck.launch.xml"
~~~

</details>

같은 도메인의 다른 터미널에서 다음을 조회한다. `lifecycle get`은 노드의 활성 상태를 묻고, `action info`는 목표를 받는 서버가 있는지 보여준다.

~~~bash
ros2 lifecycle get /keepout_mask
ros2 lifecycle get /controller_server
ros2 lifecycle get /planner_server
ros2 topic info /keepout_filter_info --verbose
ros2 topic info /keepout_filter_mask --verbose
ros2 action info /navigate_to_pose
ros2 action info /spin
ros2 topic info /fms_readonly/nav_output --verbose
~~~

`active` 상태와 두 비용 지도 로그의 `Received filter mask`를 확인한다. 속도 출력 토픽의 구독자는 0이어야 한다. FMS의 `motion_enabled`는 `false`이며, 속도 입력을 분리한 상태에서는 `ready: false`가 나올 수 있다. 이번 단계에서는 이동·회전 목표를 보내지 않는다. [ROS2 7강 · 실행 상태와 디버그](../../../../../dev_ws/ROS2/docs/present_07_디버그와_관찰을_위한_도구들_그리고_roslaunch.html) · [SLAM-Nav2 7강 · Nav2 구성](../../../../../dev_ws/SLAM-Nav2/present_07_ROS2_Nav2_PKG_설정.html)

## 4. 종료하고 팀원에게 넘기기

1. 이 실습에서 열어 둔 Nav2와 위치 추정 터미널에서 **Ctrl+C**를 누르고 FMS 창을 닫는다.
2. 센서·엔코더를 실행한 SSH 터미널에서 **Ctrl+C**를 누른다. 별도로 연 SSH 셸은 `exit`로 나온다.
3. 노트북에서 아래를 실행한다. 출력이 비어 있으면 해당 주소로 유지 중인 TCP 연결과 FMS 대기 포트가 없다. 로봇 IP가 바뀌었다면 필터를 바꾼다.

~~~bash
ss -Htnp state established |
  awk '$4 ~ /(^|:)192\.168\.(4\.1|14\.(64|75)):[0-9]+$/'
ss -Hltn 'sport = :18881'
~~~

## 5. 이번 실물 점검 기록

**[프로젝트 구현·검증 기록]** 2026-11-10

| 항목 | 1번 · 도메인 14 | 2번 · 도메인 30 |
| --- | --- | --- |
| SSH, 라이다, 오도메트리, 배터리 수신 | 확인 | 확인 |
| AMCL 위치와 방향 | (-0.523, 0.094) m · -0.560 rad | (-0.533, -0.856) m · +0.580 rad |
| 실측 라이다와 지도 벽 거리 비교 | 15개 스캔, 차이의 중앙값 7.2cm | 15개 스캔, 차이의 중앙값 6.0cm |
| 마스크 | 파일 정렬과 경유점 확인. 마스크 노드는 활성화됐고, Nav2 적용 확인은 남음 | 전역·지역 비용 지도에서 마스크 수신 로그 확인 |
| Nav2 | 컨트롤러의 상태 전환 응답 타임아웃 이후 활성화 미확인 | 관리 대상 노드 활성화 확인 |

지도 위치는 현장에서 확인한 출발점과 방향으로 AMCL을 초기화한 뒤 읽었다. 라이다 비교 수치는 측정 거리와 지도에서 예상한 벽 거리의 차이다. 점검한 시나리오에서 두 대의 출발점·대기점·교차로 출구·목적지는 모두 기본 지도와 마스크의 허용 셀에 있었다.

로봇 파일을 복사하거나 수정하지 않았고 실물 주행도 하지 않았다. 배터리 충전을 위해 중단한 뒤 팀 사용 순서에 맞춰 SSH, FMS, 위치 추정, Nav2 점검 세션을 종료했다. 팀 사용이 끝나면 **1번의 센서와 TF부터 복구하고, 컨트롤러가 활성화되는지 확인한 뒤 두 비용 지도에서 마스크 수신 로그를 확인**한다.

1번을 재점검할 때는 `ros2 node list --no-daemon --spin-time 3`으로 같은 이름의 컨트롤러가 중복 실행 중인지 확인한다. 이어서 `ros2 lifecycle get /controller_server`의 상태와 Nav2 터미널의 `change_state` 응답을 함께 본다. 지난 기록은 상태 전환 응답이 타임아웃됐다는 것까지다.

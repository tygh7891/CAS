# 실물 핑키프로 읽기 전용 실습

[학습 홈](README.md) · [Gazebo 실습](02-GAZEBO-FMS-LAB.md) · [다음 실습 · 지도와 Nav2 점검](05-FIELD-NAV2-CHECK.md)

다른 팀원이 두 로봇의 사용을 마친 뒤, 1번부터 진행한다. 로봇에서는 기존 센서 프로그램을 실행한다. 공유 지도, MapServer, AMCL, FMS는 노트북에서 실행한다. 모든 명령은 아래에 지정한 노트북 터미널에서 입력한다.

| FMS | 점검 당시 IP | ROS 2 도메인 | 지도 출발점 |
| --- | --- | --- | --- |
| 1번 | 192.168.14.64 | 14 | 1 |
| 2번 | 192.168.14.75 | 30 | 2 |

## 1. SSH와 ROS 2 도메인 확인

SSH는 로봇의 컴퓨터에 접속하는 통로다. ROS 2 토픽을 받으려면 라이다 등 데이터를 보내는 노드가 실행되어야 하고, 수신 쪽도 같은 도메인을 사용해야 한다. 두 로봇은 같은 이름의 토픽을 사용하므로 도메인으로 구분한다.

로봇별로 새 터미널을 열 때 아래 설정을 먼저 넣는다. 2번에서는 IP와 도메인을 표에 맞게 바꾼다. IP는 장비나 네트워크가 바뀌면 다시 확인한다.

~~~bash
cd ~/Pinky_Fleet_Coordinator/CAS/cas_fms
export CAS_PEER=192.168.14.64 CAS_DOMAIN=14
export CAS_LAPTOP_IP=$(ip -4 route get "$CAS_PEER" |
  awk '{for (i=1; i<NF; i++) if ($i=="src") {print $(i+1); exit}}')
printf '로봇 %s · 도메인 %s · 노트북 %s\n' "$CAS_PEER" "$CAS_DOMAIN" "$CAS_LAPTOP_IP"
ping -c 2 "$CAS_PEER"
ssh "pinky@$CAS_PEER" 'hostname; ip -br -4 address; ls ~/pinky_pro/install/setup.bash; timedatectl show -p NTPSynchronized'
~~~

실습에서는 노트북과 로봇이 서로의 IP를 ROS 2 탐색 대상으로 지정한다. 노트북의 시간을 확인하려면 [기존 ROS 2 실습](01-ROS2-BASICS.md)과 함께 아래 명령을 사용한다. [Pinky 2강 · 환경 설정](../../../../../dev_ws/Pinky/02_present_Pinky_환경_설정.html) · [ROS2 12강 · 도메인 ID](../../../../../dev_ws/ROS2/docs/present_12_하나의_노드에서_서로_다른_도메인ID에_접근.html)

~~~bash
timedatectl show -p NTPSynchronized
source /opt/ros/jazzy/setup.bash
unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID="$CAS_DOMAIN" ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_STATIC_PEERS="$CAS_PEER"
ros2 node list --no-daemon --spin-time 3
~~~

이미 로봇에서 센서·모터 드라이버가 실행 중이면 중복 실행 전에 팀원과 세션을 확인한다. 이 절차는 다른 드라이버가 시리얼 포트를 사용하고 있지 않을 때 진행한다.

## 2. 기존 라이다·배터리 노드 실행

1번의 센서 터미널에서 실행한다. SSH 세션을 열어 두고, 종료할 때 해당 터미널에서 **Ctrl+C**를 누른다. 명령은 SSH로 전달되며 로봇에 프로젝트 파일을 복사하지 않는다.

~~~bash
ssh -tt "pinky@$CAS_PEER" "export ROS_DOMAIN_ID=$CAS_DOMAIN ROS_STATIC_PEERS=$CAS_LAPTOP_IP; $(cat <<'REMOTE'
source /opt/ros/jazzy/setup.bash
source "$HOME/pinky_pro/install/setup.bash"
unset ROS_LOCALHOST_ONLY
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PYTHONDONTWRITEBYTECODE=1
lidar="$(ros2 pkg prefix sllidar_ros2)/lib/sllidar_ros2/sllidar_node"
battery="$(ros2 pkg prefix pinky_bringup)/lib/pinky_bringup/battery_publisher"
"$lidar" --ros-args --disable-external-lib-logs \
  -p serial_port:=/dev/ttyAMA0 -p serial_baudrate:=460800 \
  -p frame_id:=rplidar_link -p inverted:=false -p angle_compensate:=true \
  -p scan_mode:=DenseBoost &
lidar_pid=$!
"$battery" --ros-args --disable-external-lib-logs &
battery_pid=$!
cleanup() {
  trap - EXIT HUP INT TERM
  kill -INT "$lidar_pid" "$battery_pid" 2>/dev/null
  wait "$lidar_pid" "$battery_pid" 2>/dev/null
}
trap cleanup EXIT HUP INT TERM
wait -n "$lidar_pid" "$battery_pid"
REMOTE
)"
~~~

정상이라면 라이다 로그에 `SLLidar health status : OK`가 나온다. 배터리 노드는 잔량과 전압을 약 5초마다 발행한다. [기존 배터리 노드](../../../pinky_bringup/pinky_bringup/battery_publisher.py)

## 3. 엔코더를 읽어 오도메트리 받기

기본 `bringup_robot.launch.xml`은 모터 토크도 켠다. 이번 점검에서는 기존 오도메트리 코드의 엔코더 읽기와 TF 발행만 사용했다. 아래 명령은 실행 중인 Python 프로세스 안에서만 모터 쓰기를 막고 속도 입력을 별도 토픽으로 옮긴다. 설치된 코드가 점검한 버전과 다르면 실행을 중단한다.

<details>
<summary>엔코더 읽기 전용 명령</summary>

같은 로봇의 새 터미널에 **1단계의 환경 설정**을 입력한 뒤 아래 명령을 실행한다.

~~~bash
ssh -tt "pinky@$CAS_PEER" "export ROS_DOMAIN_ID=$CAS_DOMAIN ROS_STATIC_PEERS=$CAS_LAPTOP_IP; $(cat <<'REMOTE'
source /opt/ros/jazzy/setup.bash
source "$HOME/pinky_pro/install/setup.bash"
unset ROS_LOCALHOST_ONLY
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST PYTHONDONTWRITEBYTECODE=1
exec python3 -B -u - <<'PY'
from hashlib import sha256
from os import environ
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from pinky_bringup import bringup, dynamixel_driver

domain = environ["ROS_DOMAIN_ID"]
expected_bringup = {
    "14": "338f76478dbac0b2b5f20c62849348610cf49080d6a6f9713bca5ba45fa64fb5",
    "30": "dd956cf678baac97229904fc3d977044bbb2f7950d6a40eaa03790ff865ba907",
}
for module, expected in (
    (bringup, expected_bringup[domain]),
    (dynamixel_driver, "9c59fd54a2f1563945526dcef1a1b1282527998284670e7ce2c184b1ba1fa31c"),
):
    if sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
        raise SystemExit("점검한 드라이버 버전과 다릅니다.")


class EncoderOnly(dynamixel_driver.DynamixelDriver):
    def initialize_motors(self, profile_accel=200):
        for motor_id in self.DXL_IDS:
            torque, result, error = self.packetHandler.read1ByteTxRx(
                self.portHandler, motor_id, self.ADDR_TORQUE_ENABLE
            )
            if result != 0 or error != 0 or torque != 0:
                return False
        print("두 모터 토크 꺼짐 확인. 엔코더 읽기만 허용합니다.")
        return True

    def set_double_rpm(self, rpm_left, rpm_right):
        return rpm_left == 0 and rpm_right == 0

    def terminate(self):
        self.portHandler.closePort()


bringup.DynamixelDriver = EncoderOnly
bringup.Pinky.twist_callback = lambda self, message: None

rclpy.init(args=[
    "--ros-args", "--disable-external-lib-logs",
    "-r", f"cmd_vel:=/fms_readonly/domain_{domain}/ignored_cmd_vel",
])
node = bringup.Pinky()
try:
    if not node.is_initialized:
        raise SystemExit("엔코더 읽기 초기화 실패")
    rclpy.spin(node)
except (KeyboardInterrupt, ExternalShutdownException):
    pass
finally:
    if node.is_initialized:
        node.driver.terminate()
    node.destroy_node()
    rclpy.try_shutdown()
PY
REMOTE
)"
~~~

</details>

두 모터의 토크가 꺼진 상태에서만 오도메트리를 시작한다. 토크를 확인할 수 없으면 해당 세션을 중단하고 팀원과 기존 드라이버 상태를 확인한다. [Pinky 모터·오도메트리 코드](../../../pinky_bringup/pinky_bringup/bringup.py) · [Dynamixel 엔코더 읽기](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/api_reference/python/python_groupbulkread/)

## 4. 노트북에서 수신 여부 확인

같은 도메인을 설정한 노트북 터미널에서 실행한다. `--once`는 한 건을 읽고 종료한다. 1번이 확인되면 2번도 1~4단계를 반복한다.

~~~bash
ros2 topic list --no-daemon --spin-time 3 -t
ros2 topic echo /scan sensor_msgs/msg/LaserScan \
  --qos-reliability best_effort --once --timeout 5 --field header
ros2 topic echo /odom nav_msgs/msg/Odometry \
  --once --timeout 5 --field pose.pose.position
ros2 topic echo /battery/percent std_msgs/msg/Float32 --once --timeout 10
ros2 topic info /cmd_vel
ros2 topic info "/fms_readonly/domain_$CAS_DOMAIN/ignored_cmd_vel" --verbose
~~~

`/scan`과 `/odom`이 보이면 센서 데이터가 노트북까지 온 것이다. 읽기 전용 오도메트리의 속도 입력은 `ignored_cmd_vel`에만 있고 이 토픽의 발행자 수는 0이어야 한다. `/cmd_vel`의 `Unknown topic`은 이 단계에서 해당 토픽이 발견되지 않았다는 뜻이다. [ROS2 2강 · 기초 명령](../../../../../dev_ws/ROS2/docs/present_02_ROS_기초명령.html)

## 5. 읽기 전용 FMS 열기

아래는 이번 점검에서 사용한 실행 방식이다. 로봇마다 IP를 지정하고 도메인별 Worker를 띄운다. 두 IP가 달라지면 아래 값을 함께 바꾼다.

~~~bash
cd ~/Pinky_Fleet_Coordinator/CAS/cas_fms
source /opt/ros/jazzy/setup.bash
python3 - <<'PY'
import os
from pathlib import Path

from local_demo import run_demo

env = dict(os.environ, ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST")
env.pop("ROS_LOCALHOST_ONLY", None)
workers = {
    "robot_1": dict(env, ROS_DOMAIN_ID="14", ROS_STATIC_PEERS="192.168.14.64"),
    "robot_2": dict(env, ROS_DOMAIN_ID="30", ROS_STATIC_PEERS="192.168.14.75"),
}
run_demo(Path("gazebo_scenario.yaml"), 18881, worker_envs=workers,
         real_mode=True, motion_enabled=False)
PY
~~~

다른 터미널에서 서버 응답을 읽는다.

~~~bash
curl -fsS http://127.0.0.1:18881/api/status | python3 -m json.tool
~~~

`motion_enabled: false`는 FMS에서 주행이 꺼져 있다는 뜻이다. `scan_received`, `odom_received`가 `true`이면 두 센서를 받는 중이다. `pose`가 비어 있다면 노트북에서 [지도 위치 확인](05-FIELD-NAV2-CHECK.md#1-노트북에서-지도-위치-띄우기)을 진행한다. FMS 화면의 배터리는 잔량만 표시하며, 15초 동안 갱신되지 않으면 **배터리 수신 중단**으로 바뀐다. [실물 Worker](../../real_worker.py) · [FMS GUI](../../pinky_fms_gui/views.py)

| 상태 | 먼저 확인할 곳 |
| --- | --- |
| SSH는 되는데 ROS 2 토픽이 없다 | 로봇의 노드가 실행 중인지, 양쪽 도메인이 같은지, 상대 IP가 올바른지 확인한다. |
| 라이다와 오도메트리는 오는데 지도 위치가 없다 | MapServer·AMCL 실행, 초기 위치, `map → odom → base_footprint` 변환을 확인한다. |
| 터미널에서 TF를 읽을 수 있는데 FMS 위치가 오래됐다 | 두 장비의 시스템 시각과 센서 메시지 시각을 확인한다. |

# 02 · ROS 2에서 누가 무엇을 주고받는지 보기

[학습 목차](../README.md) · [강의 출처표](../00-START/SOURCE-INDEX.md) · [용어](../00-START/GLOSSARY.md)

**목표** · 토픽의 발행·구독, 서비스의 요청·응답, 액션의 목표·피드백·결과를 눈으로 확인한다. 노드 이름은 실행 단위의 이름이고, 토픽 이름과 메시지 타입은 연결 규칙이다.

| 필요한 이론 | HTML 원본에서 볼 슬라이드 |
|---|---|
| 노드 정보, 토픽 출력, 서비스와 액션 비교 | [ROS2-02](../00-START/SOURCE-INDEX.md#ros2-02) 17·35·50·65·72번 |
| 구독 콜백, 패키지 실행 진입점 | [ROS2-03](../00-START/SOURCE-INDEX.md#ros2-03) 16·26·32·37·42번 |
| 커스텀 메시지·서비스의 계약, 액션의 세 부분 | [ROS2-04](../00-START/SOURCE-INDEX.md#ros2-04) 5·69·120번, [ROS2-05](../00-START/SOURCE-INDEX.md#ros2-05) 5·11·68번 |
| 파라미터, 로그·rqt·bag·launch | [ROS2-06](../00-START/SOURCE-INDEX.md#ros2-06) 5·11·23·48번, [ROS2-07](../00-START/SOURCE-INDEX.md#ros2-07) 30·47·65·73번 |
| 도메인 격리, 로봇별 실행, 브리지 | [ROS2-12](../00-START/SOURCE-INDEX.md#ros2-12) 3·12·14·22번, [ROS2-13](../00-START/SOURCE-INDEX.md#ros2-13) 14·33번, [ROS2-14](../00-START/SOURCE-INDEX.md#ros2-14) 4·17·25번 |

## 준비 · 강의실 Ubuntu

기본 패키지를 설치하고 실습 터미널마다 학습 폴더를 연다. [Ubuntu 설치와 새 터미널 설정](../00-START/UBUNTU.md)

```bash
source 02-ROS2/lab_env.bash 51
printenv ROS_DISTRO ROS_DOMAIN_ID ROS_AUTOMATIC_DISCOVERY_RANGE
/usr/bin/python3 -c 'import rclpy; from std_msgs.msg import Int32'
ros2 pkg executables turtlesim
```

`jazzy`, `51`, `LOCALHOST`와 `turtlesim_node`를 확인한다. Python 명령은 성공하면 출력 없이 끝난다. 아래 터미널에서도 같은 학습 폴더로 이동한 뒤 각 블록을 실행한다. `lab_env.bash`는 DDS 기반 Jazzy 환경에서 같은 컴퓨터만 검색하도록 설정한다. 강의의 `ROS_LOCALHOST_ONLY` 설정은 ROS2-12 12번에 있다. [Jazzy 검색 범위](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst)

## A · 토픽을 보내고 받기

```bash
# Ubuntu 터미널 1
source 02-ROS2/lab_env.bash 51 && /usr/bin/python3 02-ROS2/talker.py
```

```bash
# Ubuntu 터미널 2
source 02-ROS2/lab_env.bash 51 && /usr/bin/python3 02-ROS2/listener.py
```

```bash
# Ubuntu 터미널 3
source 02-ROS2/lab_env.bash 51
ros2 node list
ros2 topic info /study/count
ros2 interface show std_msgs/msg/Int32
timeout 10s ros2 topic echo /study/count --once
```

터미널 1은 `sent 0`, `sent 1`처럼 출력하고 터미널 2는 연결된 시점의 값부터 `received …`를 표시한다. 터미널 3에서는 `/study_talker`와 `/study_listener`, 발행자와 구독자 각각 1개, `data: 정수`를 확인한다. 10초 안에 값이 오지 않으면 터미널 1과 2의 프로세스가 켜져 있는지 보고, 각 터미널의 도메인이 `51`인지 확인한다.

[talker.py](talker.py)는 타이머로 값을 만들고 [listener.py](listener.py)는 메시지가 들어올 때 함수가 호출된다. `Int32`는 32비트 정수 메시지이며 이 예제에서는 `data` 필드 하나를 사용한다. 두 파일에서 타입과 토픽 이름을 대조한다. `echo`는 메아리라는 뜻이다. 여기서는 받은 메시지를 화면에 보여준다. [ROS 2 토픽 튜토리얼](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Topics/Understanding-ROS2-Topics.rst)

## B · 같은 이름이어도 도메인이 다르면

터미널 1은 켜 두고 터미널 2를 Ctrl+C로 멈춘다. 터미널 2에서 아래를 실행해 잠깐 기다린 뒤 Ctrl+C를 누른다.

```bash
source 02-ROS2/lab_env.bash 52 && /usr/bin/python3 02-ROS2/listener.py
```

`received`가 나오지 않는 것을 확인한다. 다시 터미널 2를 51로 설정해 실행하면 수신이 돌아온다. 도메인은 ROS 그래프의 검색 영역이다. FMS에는 로봇별 Worker 프로세스가 해당 로봇 도메인에 연결하는 방식이 쓰인다. ROS2-14의 `domain_bridge`는 도메인을 의도적으로 잇는 별도 실습이다. A·B가 끝나면 터미널 1·2를 Ctrl+C로 종료한다.

## C · 서비스와 액션을 화면 속 거북이로 비교

```bash
# Ubuntu 터미널 1
source 02-ROS2/lab_env.bash 51 && ros2 run turtlesim turtlesim_node
```

```bash
# Ubuntu 터미널 2
source 02-ROS2/lab_env.bash 51
ros2 node info /turtlesim
ros2 service call /clear std_srvs/srv/Empty '{}'
ros2 action list -t
ros2 interface show turtlesim/action/RotateAbsolute
ros2 action send_goal /turtle1/rotate_absolute \
  turtlesim/action/RotateAbsolute '{theta: 1.57}' --feedback
```

터미널 1에서 거북이 창이 뜬 뒤 터미널 2를 실행한다. `/clear`는 요청을 한 번 처리해 응답한다. `action list -t`에 `/turtle1/rotate_absolute`가 보이면 회전 목표를 보낼 수 있다. 성공하면 거북이가 위쪽을 향하고 최종 상태에 `SUCCEEDED`가 나타난다. `Goal accepted`는 목표 접수 시점이다. [Jazzy 액션 튜토리얼](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Actions/Understanding-ROS2-Actions.rst) · [RotateAbsolute 정의](https://raw.githubusercontent.com/ros/ros_tutorials/jazzy/turtlesim/action/RotateAbsolute.action)

같은 터미널에서 노드 설정도 읽어본다.

```bash
ros2 param get /turtlesim background_r
ros2 param set /turtlesim background_r 100
ros2 param get /turtlesim background_r
```

두 번째 조회에서 100을 확인하고 turtlesim을 Ctrl+C로 종료한다. 파라미터는 프로그램 설정이고, 액션의 `theta`는 개별 작업 입력이다.

## 확장 · 패키지와 관찰 도구

ROS2-03 16·26·37번의 순서는 `ros2 pkg create` → 소스와 `setup.py`의 `console_scripts` 연결 → `colcon build` → `source install/setup.bash` → `ros2 run`이다. 이 단계의 Python 파일은 터미널에서 직접 실행하는 예제다. FMS Worker의 실제 진입점은 [pinky_fms/setup.py](../../../../pinky_fms/setup.py)에 있다.

ROS2-04의 `.msg`는 필드 묶음, `.srv`는 `---` 앞뒤의 요청·응답, ROS2-05의 `.action`은 목표·결과·피드백 정의로 읽는다. ROS2-07의 `rqt_graph`는 연결, `rqt_plot`은 값 변화, `ros2 bag`은 메시지 기록·재생, `ros2 launch`는 노드 묶음 시작에 사용한다. A의 터미널 1·2에서 노드를 다시 실행하고 터미널 3에서 아래를 실행해 `/study/count` 연결을 찾는다. 그래프 창을 닫은 뒤 터미널 1·2를 Ctrl+C로 종료한다.

```bash
source 02-ROS2/lab_env.bash 51
ros2 run rqt_graph rqt_graph
```

**통과 기준** · 수신이 안 될 때 프로세스·토픽 이름/타입·도메인 중 무엇부터 확인할지 말한다. 액션 접수와 성공 결과를 구분한 뒤 [03 센서와 TF](../03-PINKY/README.md)로 간다.

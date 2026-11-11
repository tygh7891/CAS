# 03 · Pinky의 센서 값과 지도 위치 구분하기

[학습 목차](../README.md) · [강의 출처표](../00-START/SOURCE-INDEX.md) · [용어](../00-START/GLOSSARY.md)

**목표** · ‘앞 0.25 m’라는 말에는 기준이 필요하다는 것을 확인한다. 라이다의 거리 배열, 바퀴 움직임의 누적 추정, 지도에서의 위치를 구분한다.

| 필요한 이론 | HTML 원본에서 볼 슬라이드 |
|---|---|
| 부모·자식 프레임, 변환과 자세 | [ROS2-08](../00-START/SOURCE-INDEX.md#ros2-08) 6·12·20·34·38번, [ROS2-09](../00-START/SOURCE-INDEX.md#ros2-09) 4·13·27번 |
| 변환 저장·조회와 RViz 표시 | [ROS2-10](../00-START/SOURCE-INDEX.md#ros2-10) 4·18·20·28번, [ROS2-11](../00-START/SOURCE-INDEX.md#ros2-11) 8·31·43번 |
| Pinky 플랫폼·원격 연결·Bringup | [PINKY-01](../00-START/SOURCE-INDEX.md#pinky-01) 5·10번, [PINKY-02](../00-START/SOURCE-INDEX.md#pinky-02) 26·48번 |
| 지도상 위치와 센서, LCD와 LED | [PINKY-04](../00-START/SOURCE-INDEX.md#pinky-04) 6·10·14번, [PINKY-06](../00-START/SOURCE-INDEX.md#pinky-06) 8·22·37·42번, [PINKY-07](../00-START/SOURCE-INDEX.md#pinky-07) 3·4·7·11번 |

## A · Mac 또는 Ubuntu에서 좌표 계산

```bash
python3 03-PINKY/frame_math.py
python3 03-PINKY/frame_math.py --yaw-deg 0
```

지도 기준 로봇 위치가 `(1, 2)`이고 센서가 로봇 기준 전방 0.25 m에 있다. 로봇이 +90° 돌아 있으면 센서는 지도 기준 `(1.00, 2.25)`, 0°이면 `(1.25, 2.00)`이다. [frame_math.py](frame_math.py)에서 **회전 → 이동** 순서를 찾아보고, `--yaw-deg -90`의 결과를 먼저 예상한다. `pose`는 위치와 방향을 같이 담는다.

## B · Ubuntu에서 같은 관계를 TF와 RViz로 확인

```bash
# 터미널 1 · 학습 도메인, 정적인 가상 프레임
source 02-ROS2/lab_env.bash 51
ros2 run tf2_ros static_transform_publisher --x 1 --y 2 --yaw 1.5707963 \
  --frame-id study_map --child-frame-id study_base
```

```bash
# 터미널 2
source 02-ROS2/lab_env.bash 51
ros2 run tf2_ros static_transform_publisher --x 0.25 \
  --frame-id study_base --child-frame-id study_sensor
```

```bash
# 터미널 3
source 02-ROS2/lab_env.bash 51
ros2 run tf2_ros tf2_echo study_map study_sensor
```

초기에 검색 중 메시지가 나올 수 있다. 연결 뒤 `Translation`이 약 `[1.0, 2.25, 0.0]`인지 확인한다. 순서를 `study_sensor study_map`으로 바꾸면 역변환을 조회한다. [Jazzy 정적 TF 명령](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Intermediate/Tf2/Writing-A-Tf2-Static-Broadcaster-Py.rst)

같은 도메인의 다른 터미널에서 `ros2 run rviz2 rviz2`를 실행한다. **Global Options → Fixed Frame**에 `study_map`을 넣고 **Add → TF**를 추가한다. 세 프레임 이름과 축을 확인하고 RViz를 닫은 뒤 각 터미널을 Ctrl+C로 종료한다.

## C · Pinky가 준비된 경우 Ubuntu에서 읽기만 하기

담당 Pinky의 Bringup을 확인한다. 새로 시작해야 한다면 로봇의 준비된 ROS 워크스페이스와 실제 도메인을 불러온 터미널에서 `ros2 launch pinky_bringup bringup_robot.launch.xml`을 실행한다. 원격 터미널이 필요하면 수업에서 확인한 계정과 호스트로 `ssh 계정@호스트`를 사용한다. [Pinky Bringup](../../../../pinky_bringup/launch/bringup_robot.launch.xml)

노트북은 **새 터미널**을 열어 아래의 `14`를 담당 Pinky의 실제 값으로 바꾼다. B의 `LOCALHOST` 학습 셸은 같은 컴퓨터용이므로 여기서는 로봇과 통신 가능한 검색 설정을 사용한다.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=14
printenv ROS_AUTOMATIC_DISCOVERY_RANGE
ros2 topic list -t
ros2 topic info /scan
python3 03-PINKY/scan_report.py
ros2 topic echo /odom --once
ros2 run tf2_ros tf2_echo odom base_footprint
```

[scan_report.py](scan_report.py)는 유효 거리 개수와 센서 기준 최솟값만 출력하고 종료한다. `/scan`과 `/odom`의 이름이 다르면 `topic list -t`에서 실제 이름을 확인한다. `/scan`은 `--ros-args -r /scan:=/실제/토픽`으로 바꿔 읽을 수 있다. `tf2_echo`는 확인 뒤 Ctrl+C로 종료한다. `map → base_footprint` 조회는 SLAM 또는 위치 추정이 지도 기준 TF를 제공할 때 가능하다.

- **LiDAR**는 방향별 거리다. 가장 가까운 반사점이 로봇의 지도 위치를 뜻하지 않는다.
- **Odometry**의 어근 `hodos`는 ‘길’이다. `/odom`은 주행에 따른 상대 위치 추정이며 움직임을 누적하면 오차가 쌓일 수 있다.
- **RViz**는 전달받은 데이터를 그린다. 센서 데이터를 `Fixed Frame`에 표시하려면 두 프레임을 연결하는 TF가 필요하다.

### 확장 읽기

[ROS2-19](../00-START/SOURCE-INDEX.md#ros2-19) 41·68번은 `Image → CvBridge → OpenCV`와 해상도 변경, [ROS2-20](../00-START/SOURCE-INDEX.md#ros2-20) 25·30번은 HSV 보정, [ROS2-21](../00-START/SOURCE-INDEX.md#ros2-21) 21·42번은 Canny 임계값과 입출력 토픽, [ROS2-22](../00-START/SOURCE-INDEX.md#ros2-22) 19·28번은 이전·현재 영상의 흐름을 다룬다. 이미지 토픽을 확인한 뒤 `ros2 run rqt_image_view rqt_image_view`의 토픽 선택 메뉴에서 원본과 처리 결과를 비교한다. 창을 닫아 종료한다.

PINKY-06 22·37번에서 LCD에 문자·GIF를 직접 그리는 예제를, PINKY-07 3·4·7·11번에서 LCD·LED를 ROS 서비스로 제어하는 예제를 비교한다. CAS의 인터페이스 패키지를 빌드한 환경이라면 장비 없이도 `ros2 interface show pinky_interfaces/srv/Emotion`으로 요청 필드 `emotion`을 확인할 수 있다.

**통과 기준** · 센서의 ‘앞’과 지도의 ‘앞’이 다른 예를 숫자로 설명한다. `/scan`, `/odom`, `map → base_footprint` 중 무엇을 보면 지도상 위치를 읽을 수 있는지 고르고 [04 SLAM과 Nav2](../04-SLAM-NAV2/README.md)로 간다.

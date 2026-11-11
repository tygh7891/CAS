# 영어 용어와 명령 이름 풀이

**어원**은 단어의 역사적 유래를, **이름 풀이**는 약어의 원형이나 코드 이름을 읽는 법을 뜻한다. 명령의 이름 풀이를 그대로 실행 동작으로 추정하기보다 예제에서 확인한다. [학습 시작](../README.md)

## 터미널과 코드

| 용어 | 어원 또는 이름 풀이 | 실습에서 하는 일 |
|---|---|---|
| `terminal` / `shell` | terminal은 끝단, shell은 껍질을 뜻한다. 셸은 시스템에 명령을 전달하는 프로그램에 붙인 이름이다. | 터미널 창에서 셸이 입력을 읽고 Python 또는 ROS 2 프로그램을 시작한다. |
| `Bash` / `.bashrc` | Bash는 Bourne Again SHell의 줄임말이다. `.bashrc`는 대화형 비로그인 Bash가 읽는 시작 설정 파일이다. | 강의실에서는 먼저 현재 터미널에서 `source`로 ROS 환경을 불러온다. [GNU Bash 시작 파일](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html) |
| `pwd` / `cd` / `ls` | print working directory / change directory / list. | 작업 경로를 출력하고, 이동하고, 파일 목록을 본다. |
| `source` / `export` | source는 원천, export는 바깥으로 내보낸다는 뜻이다. | `source`는 파일을 현재 셸에서 실행한다. `export`는 자식 프로그램도 환경 변수 값을 읽도록 한다. |
| `alias` | ‘다른 이름으로’라는 뜻의 라틴어 `alias`에서 온 이름이다. [alias 어원](https://www.etymonline.com/word/alias) | 길게 반복하는 명령에 별칭을 붙인다. 원래 명령을 먼저 이해하고 쓴다. |
| `def` / `return` / `callback` | define의 축약, ‘돌려주다’, ‘다시 호출하다’. | 함수를 정의하고 값을 돌려준다. 콜백은 메시지나 타이머 등 사건이 들어오면 호출된다. |
| `JSON` / `YAML` | JavaScript Object Notation. YAML은 재귀 약어 YAML Ain’t Markup Language다. | FMS HTTP의 JSON은 요청·응답 데이터이고, 지도·서버의 YAML은 파일에 저장한 설정이다. |
| `CLI` / `GUI` / `venv` | Command-Line Interface / Graphical User Interface / virtual environment. | 명령줄과 그래픽 화면, Python 라이브러리를 분리해 설치하는 가상환경이다. |

## ROS 2 통신

| 용어 | 어원 또는 이름 풀이 | 실습에서 하는 일 |
|---|---|---|
| `robot` | 체코어 `robota`는 부역·강제 노동을 뜻한다. 단어가 희곡 *R.U.R.*을 통해 널리 알려졌다. [robot 어원](https://www.etymonline.com/word/robot) | ROS 2는 여러 로봇 프로그램을 연결하는 도구를 제공한다. |
| `node` | 라틴어 `nodus`는 매듭이다. [node 어원](https://www.etymonline.com/word/node) | ROS 그래프의 연결점이다. 한 프로세스에 노드가 여러 개 있을 수도 있다. |
| `topic` | 그리스어 `topos`(장소·주제)와 관련된 어휘에서 왔다. [topic 어원](https://www.etymonline.com/word/topic) | 이름 있는 메시지 통로다. `/study/count`로 어떤 메시지가 흐르는지 본다. |
| `publish` / `subscribe` | publish는 라틴어 `publicare`(공개하다), subscribe는 `subscribere`(아래에 쓰다·서명하다)에서 이어진다. [publish](https://www.etymonline.com/word/publish) · [subscribe](https://www.etymonline.com/word/subscribe) | 발행자는 토픽에 메시지를 보내고 구독자는 해당 이름의 토픽에서 받는다. |
| `echo` | 그리스어 `ēkhō`(반향)에서 이어졌다. [echo 어원](https://www.etymonline.com/word/echo) | `ros2 topic echo`는 토픽을 구독해 받은 메시지를 터미널에 보여준다. |
| `service` / `action` | 서비스는 요청을 처리해 돌려주는 일, 액션은 수행할 동작이라는 뜻으로 읽는다. | 서비스의 요청·응답과 액션의 목표·진행 피드백·결과를 비교한다. |
| `DDS` / `QoS` / `domain` | Data Distribution Service / Quality of Service / 영역. | DDS 기반 검색 영역과 메시지 전달 규칙은 다른 설정이다. 도메인이 같아도 QoS가 맞지 않으면 데이터 수신이 어려울 수 있다. |
| `rclpy` / `spin` | ROS Client Library의 Python 구현 이름이다. spin은 ‘돌다’라는 영어다. | `rclpy.spin()`은 콜백을 처리한다. Nav2 `Spin`은 로봇 회전 액션의 이름이다. |
| `pkg` / `run` / `launch` | package의 줄임말, 실행하다, 출발시키다. | `ros2 run`은 패키지의 실행 항목을 시작하고 `ros2 launch`는 설정 파일에 정의된 프로그램 구성을 시작한다. |
| `msg` / `srv` / `param` | message / service / parameter의 줄임말이다. | 메시지·서비스 인터페이스와 노드 설정값을 조회한다. `ros2 interface show`로 계약의 필드를 읽는다. |
| `ament` / `colcon` / `rosdep` | `ament`는 ROS 패키지 빌드·설치 체계의 이름이다. `colcon`은 *collective construction*, `rosdep`의 dep는 dependency를 가리킨다. [colcon 문서](https://colcon.readthedocs.io/en/released/) | 의존성을 설치하고 패키지를 빌드한 뒤 `install/setup.bash`를 불러와 실행 항목을 노출한다. |

## 로봇과 관제

| 용어 | 어원 또는 이름 풀이 | 실습에서 하는 일 |
|---|---|---|
| `TF` / `frame` / `pose` | transform(변환), 기준 틀, 자세. | 프레임은 좌표의 기준이다. 포즈에는 그 기준에서의 위치와 방향이 함께 있다. |
| `odometry` / `LiDAR` | odometer의 `hodos`는 그리스어로 길, `-meter`는 측정을 뜻한다. LiDAR는 Light Detection and Ranging이다. [odometer 어원](https://www.etymonline.com/word/odometer) | 오도메트리는 움직임을 누적해 위치 변화를 추정한다. 라이다는 센서 기준 방향별 거리를 측정한다. |
| `yaw` / `quaternion` | yaw는 좌우로 머리를 돌리는 각도다. quaternion은 넷과 관련된 이름이며 ROS에서는 회전을 표현하는 `x,y,z,w` 네 값을 사용한다. | 수평면 회전을 숫자로 입력하고 그 회전이 TF와 목표 포즈에 어떻게 들어가는지 본다. |
| `RViz` / `URDF` / `Xacro` | ROS Visualization, Unified Robot Description Format, XML Macro에서 온 이름이다. | 모델 설명과 토픽 데이터를 화면에 표시한다. Xacro는 반복되는 로봇 설명을 줄이는 데 쓴다. |
| `SLAM` / `AMCL` / `Nav2` | Simultaneous Localization and Mapping, Adaptive Monte Carlo Localization, Navigation2. | 지도를 만드는 과정, 기존 지도에서 위치를 추정하는 과정, 목표로 주행하는 과정을 나눈다. |
| `costmap` / `keepout` / `waypoint` | cost + map, keep out(들어가지 말다), way + point(경유점). | 계획에 쓰는 비용 지도, 회피해야 하는 구역, 경유 좌표를 각각 읽는다. |
| `PID` / `FSM` | Proportional–Integral–Derivative / Finite State Machine. | PID는 제어 오차를 줄이는 기법이다. 상태 머신은 작업을 단계로 나누고 전이 조건을 정한다. |
| `CV` / `HSV` / `Optical Flow` | Computer Vision, Hue–Saturation–Value, 영상에서 보이는 움직임의 흐름. | 이미지 메시지를 영상 행렬로 바꾼 뒤 색·윤곽·프레임 간 변화를 관찰한다. |
| `FMS` / `FIFO` | Fleet Management System / First In, First Out. | 여러 로봇 작업과 교차로 통행을 관리하며, 대기열은 먼저 들어온 요청부터 본다. |
| `HTTP` / `API` / `poll` | Hypertext Transfer Protocol / Application Programming Interface. poll은 상태를 되풀이해 묻는다는 뜻으로 쓴다. | Worker가 위치와 결과를 보고하고 응답에서 다음 명령을 읽는다. |
| `worker` / `endpoint` | 작업을 처리하는 일꾼, end + point(끝점). | Worker는 서버의 명령을 실제 Nav2 액션으로 바꾼다. `endpoint_a`는 출발·복귀 좌표다. |
| `GET` / `POST` / `curl` | GET은 가져오기, POST는 보내기다. curl은 URL로 데이터를 전송하는 CLI 이름이다. | 상태를 읽고, 요청 본문으로 작업을 등록한다. 실습은 로컬 모의 서버를 대상으로 한다. |

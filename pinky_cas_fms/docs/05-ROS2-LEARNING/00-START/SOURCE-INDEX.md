# 강의 HTML 출처표

[학습 시작](../README.md) · [용어와 명령 풀이](GLOSSARY.md)

강의 번호는 파일명에서, 강의 제목과 슬라이드 번호는 HTML에서 확인했다. 페이지 번호는 PDF 쪽수가 아닌 HTML 하단의 슬라이드 번호다. 이 HTML 묶음에는 이 표에서 사용할 슬라이드별 고정 링크가 없어서 원본 파일을 연 뒤 페이지 표시를 따라간다.

이 폴더에서 아래 명령으로 원본을 열거나, 이 컴퓨터에서 클릭할 수 있는 링크 목록을 만든다. 다른 경로에 HTML이 있으면 `--root`에 `ROS2`, `SLAM_Nav2`, `Pinky`가 들어 있는 폴더를 지정한다.

```bash
python3 source_links.py --open ROS2-02
python3 source_links.py --html
python3 source_links.py --check
```

`--html`이 출력한 경로를 브라우저에서 열면 된다. GitHub에서도 각 강의 ID와 정확한 파일명, 관련 슬라이드, 실습 경로를 확인할 수 있다.

## ROS 2 · 22개

### ROS2-01

**01 ROS2를 위한 Ubuntu 환경설정 & 터미널 bashrc 그리고 리눅스 익숙해지기~**

- 원본 `ROS2/present_01_ROS2를_위한_Ubuntu_환경설정_터미널_bashrc_그리고_리눅스_익숙해지기.html`
- 찾아볼 슬라이드 16, 25, 30, 35, 43번. Jazzy 환경을 셸마다 불러오는 이유와 bashrc·alias를 익힌다.
- 연결 실습 [01-PYTHON-TERMINAL](../01-PYTHON-TERMINAL/README.md)

### ROS2-02

**02 ROS 기초명령~**

- 원본 `ROS2/present_02_ROS_기초명령.html`
- 찾아볼 슬라이드 17, 35, 50, 65, 72번. 노드가 가진 연결을 살피고 토픽·서비스·액션을 CLI에서 비교한다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-03

**03 패키지 만들고 토픽 다루기~**

- 원본 `ROS2/present_03_패키지_만들고_토픽_다루기.html`
- 찾아볼 슬라이드 16, 26, 32, 37, 42번. 패키지·빌드·설치 환경의 관계와 구독 콜백·실행 진입점을 연결한다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-04

**04 메시지 정의 만들고 토픽과 서비스에서 다루기~**

- 원본 `ROS2/present_04_메시지_정의_만들고_토픽과_서비스에서_다루기.html`
- 찾아볼 슬라이드 5, 17, 69, 81, 120번. 메시지와 서비스의 필드 계약, 인터페이스 생성·조회 과정을 읽는다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-05

**05 액션 익숙해지기~**

- 원본 `ROS2/present_05_액션_익숙해지기.html`
- 찾아볼 슬라이드 5, 11, 24, 63, 68번. 액션의 목표·피드백·결과를 구분하고 Nav2 결과 해석에 연결한다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-06

**06 파라미터 다루기~**

- 원본 `ROS2/present_06_파라미터_다루기.html`
- 찾아볼 슬라이드 5, 11, 23, 42, 48번. 노드 파라미터 조회·YAML 적용과 설정 변경 콜백의 차이를 익힌다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-07

**07 디버그와 관찰을 위한 도구들, 그리고 roslaunch~**

- 원본 `ROS2/present_07_디버그와_관찰을_위한_도구들_그리고_roslaunch.html`
- 찾아볼 슬라이드 5, 30, 47, 65, 73번. 로그, rqt_plot, rosbag, launch 중 어떤 도구가 어떤 문제를 보여주는지 구분한다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-08

**TF로 좌표계와 자세(pose) 발행하기**

- 원본 `ROS2/present_08_TF로_좌표계와_자세pose_발행하기.html`
- 찾아볼 슬라이드 6, 12, 20, 34, 38번. 프레임 ID·시각·변환이 담긴 메시지를 위치와 자세에 연결한다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-09

**Child frame 하나 추가해보자!!**

- 원본 `ROS2/present_09_Child_frame_하나_추가해보자.html`
- 찾아볼 슬라이드 4, 7, 13, 27번. 부모에 자식 프레임을 붙이고 회전을 쿼터니언으로 표현하는 예제다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-10

**TF frame을 구독하고 좌표계 사이의 정보를 활용하는 법 !!**

- 원본 `ROS2/present_10_TF_frame을_구독하고_좌표계_사이의_정보를_활용하는_법.html`
- 찾아볼 슬라이드 4, 18, 20, 28번. Buffer와 Listener가 받은 TF로 두 프레임 사이 변환을 읽는다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-11

**TF frame의 작업 결과를 rviz2에서 시각화하기 !!**

- 원본 `ROS2/present_11_TF_frame의_작업_결과를_rviz2에서_시각화하기.html`
- 찾아볼 슬라이드 8, 17, 31, 43번. Marker·PoseStamped·Path가 RViz에 어떤 데이터를 그리는지 비교한다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-12

**하나의 노드에서 서로 다른 도메인ID에 접근 !!**

- 원본 `ROS2/present_12_하나의_노드에서_서로_다른_도메인ID에_접근.html`
- 찾아볼 슬라이드 3, 12, 14, 22번. 도메인 격리와 같은 PC 한정 검색을 구분한다. 강의의 다중 프로세스 예제를 FMS의 로봇별 Worker와 비교한다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-13

**하나의 노드에서 서로 다른 domain id의 turtlesim을 다뤄보자.!**

- 원본 `ROS2/present_13_하나의_노드에서_서로_다른_domain_id의_turtlesim을_다뤄보자.html`
- 찾아볼 슬라이드 4, 14, 19, 33, 39번. 서로 다른 도메인의 turtlesim과 토픽·서비스·액션을 함께 본다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-14

**ros domain bridge를 이용해서 다른 domain id에 접근해보자.!**

- 원본 `ROS2/present_14_ros_domain_bridge를_이용해서_다른_domain_id에_접근해보자.html`
- 찾아볼 슬라이드 4, 11, 13, 17, 25, 29번. 브리지가 의도적으로 토픽을 전달하는 방식과 QoS·이름 변경을 읽는다.
- 연결 실습 [02-ROS2](../02-ROS2/README.md)

### ROS2-15

**01 [주행제어기] 특정한 위치? 각도?에 멈추게 하는것_26.03**

- 원본 `ROS2/present_15_주행제어기_특정한_위치_각도에_멈추게_하는것_2603.html`
- 찾아볼 슬라이드 21, 31, 47, 52번. 각도 오차를 정규화하고 허용오차를 바꿨을 때 떨림이 생기는 이유를 관찰한다.
- 연결 실습 [05-FMS](../05-FMS/README.md)

### ROS2-16

**02 [주행제어기] PID 제어기란? 원하는 곳에 제발 멈추게 해보기~**

- 원본 `ROS2/present_16_주행제어기_PID_제어기란_원하는_곳에_제발_멈추게_해보기.html`
- 찾아볼 슬라이드 5, 26, 31, 47번. PID의 역할과 목표 오차를 그래프로 관찰하는 예제다.
- 연결 실습 [05-FMS](../05-FMS/README.md)

### ROS2-17

**03 [주행제어기] 위치를 제어하는 PID 제어기는 어떻게?~**

- 원본 `ROS2/present_17_주행제어기_위치를_제어하는_PID_제어기는_어떻게.html`
- 찾아볼 슬라이드 12, 20, 28, 45번. 내적으로 앞뒤를 판정하는 예제를 FMS의 교차로 이탈 방향 판단에 연결한다.
- 연결 실습 [05-FMS](../05-FMS/README.md)

### ROS2-18

**04 [주행제어기] 로봇의 주행 제어기를 상태별로 나눠서 제어하자~**

- 원본 `ROS2/present_18_주행제어기_로봇의_주행_제어기를_상태별로_나눠서_제어하자.html`
- 찾아볼 슬라이드 12, 20, 27, 34, 70번. 회전·이동 단계를 분리하는 상태 머신을 FMS 작업 단계와 비교한다.
- 연결 실습 [05-FMS](../05-FMS/README.md)

### ROS2-19

**19 ROS2와 OpenCV - CV Bridge ~**

- 원본 `ROS2/present_19_ROS2와_OpenCV_-_CV_Bridge.html`
- 찾아볼 슬라이드 4, 11, 25, 41, 68번. 카메라 토픽, CV Bridge 변환, 해상도와 전송량 관계를 읽는다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-20

**20 HSV 컨버터_**

- 원본 `ROS2/present_20_HSV_컨버터_.html`
- 찾아볼 슬라이드 11, 21, 25, 30, 44번. HSV 채널 보정 전후의 이미지 토픽을 rqt로 확인하는 예제다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-21

**21 Canny edge ros2 node 만들기_**

- 원본 `ROS2/present_21_Canny_edge_ros2_node_만들기_.html`
- 찾아볼 슬라이드 5, 13, 21, 29, 42번. 영상 입력과 에지 출력 사이의 노드·파라미터·launch 연결을 읽는다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### ROS2-22

**22 Optical Flow ros2 node 만들기~**

- 원본 `ROS2/present_22_Optical_Flow_ros2_node_만들기.html`
- 찾아볼 슬라이드 4, 16, 19, 22, 28번. 이전·현재 프레임을 비교해 픽셀의 움직임을 추정하는 처리 흐름을 읽는다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

## SLAM·Nav2 · 7개

### NAV-01

**01 ROS2 Description PKG for Mobile Robot**

- 원본 `SLAM_Nav2/present_01_ROS2_Description_PKG_for_Mobile_Robot.html`
- 찾아볼 슬라이드 22, 33, 43, 68, 77, 86번. 로봇 모델과 센서 링크를 URDF/Xacro로 기술하고, 모델 보기와 모델 게시를 구분한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-02

**02 ROS2 Gazebo PKG**

- 원본 `SLAM_Nav2/present_02_ROS2_Gazebo_PKG.html`
- 찾아볼 슬라이드 5, 12, 15, 18, 28, 35번. Gazebo의 센서·구동 플러그인과 ROS–Gazebo 브리지의 역할을 구분한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-03

**03 ROS2 SLAM map building**

- 원본 `SLAM_Nav2/present_03_ROS2_SLAM_map_building.html`
- 찾아볼 슬라이드 7, 9, 11, 19, 21, 23번. SLAM Toolbox로 주행하며 지도를 만들고 저장된 이미지·YAML을 확인한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-04

**04 Localization**

- 원본 `SLAM_Nav2/present_04_Localization.html`
- 찾아볼 슬라이드 16, 20, 24, 35, 40, 45번. 지도 서버·AMCL·라이프사이클과 RViz 초기 위치 설정을 연결한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-05

**05 Navigation PKG 다뤄보기**

- 원본 `SLAM_Nav2/present_05_Navigation_PKG_다뤄보기.html`
- 찾아볼 슬라이드 4, 6, 8, 10, 14번. 시뮬레이션에서 초기 위치, 목표 입력, 경로 표시와 팽창 반경을 확인한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-06

**06 Python으로 Nav2 다뤄보기**

- 원본 `SLAM_Nav2/present_06_Python으로_Nav2_다뤄보기.html`
- 찾아볼 슬라이드 9, 13, 17, 31, 35, 40번. BasicNavigator의 액션 방식과 목표 토픽 방식을 비교하고 완료 결과를 읽는다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### NAV-07

**07 ROS2 Nav2 PKG 설정**

- 원본 `SLAM_Nav2/present_07_ROS2_Nav2_PKG_설정.html`
- 찾아볼 슬라이드 15, 25, 45, 56, 67, 77, 88, 99번. Nav2 실행 구성, AMCL, 제어기, 비용 지도, 행동 플러그인을 분리해서 읽는다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

## Pinky · 8개

### PINKY-01

**PinkyPro를 소개합니다.**

- 원본 `Pinky/01_present_PinkyPro를_소개합니다.html`
- 찾아볼 슬라이드 5, 10번. Pinky Pro 플랫폼과 다중 로봇 관제 과제를 소개한다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### PINKY-02

**Pinky 환경 설정**

- 원본 `Pinky/02_present_Pinky_환경_설정.html`
- 찾아볼 슬라이드 4, 21, 26, 48번. 로봇 준비, 원격 터미널, 의존성, Bringup을 연결한다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### PINKY-03

**PinkyPro로 맵 작성하기**

- 원본 `Pinky/03_present_PinkyPro로_맵_작성하기.html`
- 찾아볼 슬라이드 4, 5, 7, 10, 13, 14번. 실물 지도 작성의 Bringup·SLAM·저속 주행·저장 순서를 확인한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### PINKY-04

**PinkyPro 내비게이션으로 주행하기**

- 원본 `Pinky/04_present_PinkyPro_내비게이션으로_주행하기.html`
- 찾아볼 슬라이드 4, 6, 10, 14, 18번. Nav2를 띄워 초기 위치를 맞추고 클릭한 지도 좌표와 AMCL 위치를 관찰한다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### PINKY-05

**PinkyPro 주피터로 내비게이션 하기**

- 원본 `Pinky/05_present_PinkyPro_주피터로_내비게이션_하기.html`
- 찾아볼 슬라이드 7, 9, 11, 17, 19, 24, 26번. 노트북 셀에서 방향을 변환하고, 단일 목표·경유점·결과·종료를 다룬다.
- 연결 실습 [04-SLAM-NAV2](../04-SLAM-NAV2/README.md)

### PINKY-06

**PinkyPro LCD 사용하기**

- 원본 `Pinky/06_present_PinkyPro_LCD_사용하기.html`
- 찾아볼 슬라이드 8, 13, 22, 37, 42번. LCD 객체로 문자·GIF·카메라 이미지를 내보내는 예제다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### PINKY-07

**PinkyPro LCD 와 LED를 ROS2로 다루기**

- 원본 `Pinky/07_present_PinkyPro_LCD_와_LED를_ROS2로_다루기.html`
- 찾아볼 슬라이드 3, 4, 7, 8, 11번. 표정·LED 서비스의 노드, 요청값, 응답 확인을 다룬다.
- 연결 실습 [03-PINKY](../03-PINKY/README.md)

### PINKY-08

**Flask 사용해보기**

- 원본 `Pinky/08_present_Flask_사용해보기.html`
- 찾아볼 슬라이드 4, 7, 8, 10, 11, 15번. Flask 카메라 스트림으로 서버와 HTTP 클라이언트 관계를 살펴본다.
- 연결 실습 [05-FMS](../05-FMS/README.md)

## 출처 확인 범위

37개 파일의 슬라이드 1,800개에서 제목·텍스트·코드 요소를 번호순으로 추출해 검토했다. 텍스트 대신 화면이나 코드 이미지가 들어 있는 강의는 필수 실습에 필요한 이미지도 선별해 확인했다. 내장 영상과 모든 스크린샷을 재생·판독하는 검토는 이 출처표의 범위에 포함되지 않는다. `sources.json`의 SHA-256은 분석 시점 HTML을 식별한다.

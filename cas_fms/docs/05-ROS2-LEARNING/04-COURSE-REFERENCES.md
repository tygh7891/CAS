# 참고한 HTML 강의와 프로젝트 적용 범위

[학습 홈](README.md)

강의 파일은 노트북의 `~/dev_ws/ROS2/docs`, `~/dev_ws/SLAM-Nav2`, `~/dev_ws/Pinky`에 있다. 링크는 현재 노트북의 디렉터리 구조를 기준으로 한다.

## ROS2

| 참고한 강의 | 프로젝트와 연결되는 내용 |
| --- | --- |
| [1강 · Ubuntu 환경과 터미널](../../../../../dev_ws/ROS2/docs/present_01_ROS2를_위한_Ubuntu_환경설정_터미널_bashrc_그리고_리눅스_익숙해지기.html) · [2강 · ROS 기초 명령](../../../../../dev_ws/ROS2/docs/present_02_ROS_기초명령.html) | `source`로 ROS 환경을 읽고 `ros2 node`, `ros2 topic`, `ros2 action`으로 실행 상태를 확인한다. |
| [3강 · 패키지와 토픽](../../../../../dev_ws/ROS2/docs/present_03_패키지_만들고_토픽_다루기.html) · [4강 · 메시지와 서비스](../../../../../dev_ws/ROS2/docs/present_04_메시지_정의_만들고_토픽과_서비스에서_다루기.html) | 패키지, 발행·구독과 요청·응답을 구분한다. 실습에서 `/scan`과 `/odom`을 읽는다. |
| [5강 · 액션](../../../../../dev_ws/ROS2/docs/present_05_액션_익숙해지기.html) | 목표 전송, 결과, 취소 개념을 `navigate_to_pose`와 `spin`에 적용한다. |
| [6강 · 파라미터](../../../../../dev_ws/ROS2/docs/present_06_파라미터_다루기.html) · [7강 · 디버그와 실행](../../../../../dev_ws/ROS2/docs/present_07_디버그와_관찰을_위한_도구들_그리고_roslaunch.html) | 가상 시간, YAML 설정, `launch` 파일을 이해하고 현재 실행된 노드와 설정값을 확인한다. |
| [8강 · TF 발행](../../../../../dev_ws/ROS2/docs/present_08_TF로_좌표계와_자세pose_발행하기.html) · [10강 · TF 구독](../../../../../dev_ws/ROS2/docs/present_10_TF_frame을_구독하고_좌표계_사이의_정보를_활용하는_법.html) · [11강 · RViz에서 TF 보기](../../../../../dev_ws/ROS2/docs/present_11_TF_frame의_작업_결과를_rviz2에서_시각화하기.html) | `map`, `odom`, `base_footprint`를 구분하고 지도 기준 위치를 읽는다. |
| [12강 · 도메인 ID](../../../../../dev_ws/ROS2/docs/present_12_하나의_노드에서_서로_다른_도메인ID에_접근.html) · [13강 · 두 도메인 실습](../../../../../dev_ws/ROS2/docs/present_13_하나의_노드에서_서로_다른_domain_id의_turtlesim을_다뤄보자.html) · [14강 · domain_bridge](../../../../../dev_ws/ROS2/docs/present_14_ros_domain_bridge를_이용해서_다른_domain_id에_접근해보자.html) | 두 로봇이 같은 토픽 이름을 사용할 때 도메인으로 분리하는 원리를 참고했다. 강의의 `domain_bridge`는 비교 자료다. 이 프로젝트는 두 Worker가 각 도메인에서 직접 통신한다. |

## SLAM-Nav2

| 참고한 강의 | 프로젝트와 연결되는 내용 |
| --- | --- |
| [1강 · 로봇 모델 패키지](../../../../../dev_ws/SLAM-Nav2/present_01_ROS2_Description_PKG_for_Mobile_Robot.html) · [2강 · Gazebo 패키지](../../../../../dev_ws/SLAM-Nav2/present_02_ROS2_Gazebo_PKG.html) | URDF/Xacro로 로봇 모델을 만들고 Gazebo에 배치하는 방식, 가상 라이다와 ROS 2를 연결하는 방식을 참고했다. |
| [3강 · SLAM 맵 작성](../../../../../dev_ws/SLAM-Nav2/present_03_ROS2_SLAM_map_building.html) | `slam_toolbox`로 지도 데이터를 만드는 과정을 참고했다. 프로젝트 실행에서는 공유된 맵을 재사용한다. |
| [4강 · 위치 추정](../../../../../dev_ws/SLAM-Nav2/present_04_Localization.html) · [5강 · 내비게이션 패키지](../../../../../dev_ws/SLAM-Nav2/present_05_Navigation_PKG_다뤄보기.html) | 저장한 맵을 MapServer로 읽고 AMCL에서 위치를 추정한다. RViz의 현재 위치 지정과 목적지 지정을 구분한다. |
| [6강 · Python으로 Nav2 다루기](../../../../../dev_ws/SLAM-Nav2/present_06_Python으로_Nav2_다뤄보기.html) | 강의는 `BasicNavigator`로 목표·상태·취소를 다룬다. 프로젝트의 Worker는 `rclpy`의 `ActionClient`로 같은 종류의 Nav2 Action을 직접 호출한다. |
| [7강 · Nav2 패키지 설정](../../../../../dev_ws/SLAM-Nav2/present_07_ROS2_Nav2_PKG_설정.html) | 위치 추정, 경로 계획, 주행 제어를 나눠 실행하는 설정을 참고했다. |

## Pinky

| 참고한 강의 | 프로젝트와 연결되는 내용 |
| --- | --- |
| [2강 · Pinky 환경 설정](../../../../../dev_ws/Pinky/02_present_Pinky_환경_설정.html) | 실물 드라이버 실행과 ROS 2 도메인 설정을 확인했다. |
| [3강 · PinkyPro로 맵 작성](../../../../../dev_ws/Pinky/03_present_PinkyPro로_맵_작성하기.html) | YAML·이미지로 저장되는 지도 파일의 배경 자료다. |
| [4강 · PinkyPro 내비게이션 주행](../../../../../dev_ws/Pinky/04_present_PinkyPro_내비게이션으로_주행하기.html) · [5강 · 주피터에서 내비게이션](../../../../../dev_ws/Pinky/05_present_PinkyPro_주피터로_내비게이션_하기.html) | 저장된 맵으로 Nav2를 실행하고 현재 위치를 읽는 과정을 참고했다. |
| [8강 · Flask 사용](../../../../../dev_ws/Pinky/08_present_Flask_사용해보기.html) | HTTP 서버와 클라이언트 역할을 참고했다. 교차로 진입권과 상태 보고를 처리하는 FMS API는 프로젝트에서 구현했다. |

## 팀 자료와 구현 기록

- **[원문 요약]** 팀 제안서와 CAS A1 연결 방식은 기존 문서에서 원문 링크로 확인한다. [프로젝트 계획](../00-PROJECT/PROJECT-PLAN.md) · [관제 설계와 연동 계약](../04-ENGINEERING/FMS-ARCHITECTURE.md)
- **[공유 자료]** 장윤호님이 제공한 [기본 맵 설정](../../maps/fleet_world_new.yaml)과 [진입 제한 마스크 설정](../../maps/fleet_x_keepout_new.yaml)을 사용했다. 두 YAML에 지정된 PGM 파일은 같은 폴더에 있다.
- **[프로젝트 구현·검증 기록]** 두 대를 한 Gazebo 공간에 배치하는 설정, 교차로 진입권, 위치 보고 중단·복구, 실물 읽기 전용 모드는 프로젝트 구현이다. [구현 요약](README.md#지금까지-한-작업) · [실물 연결 모드 검증 결과](../02-TESTING/REAL-MODE.md#노트북-검증-결과)
- **[현장 실습]** 도메인별로 노트북 Worker를 연결해 실제 센서를 읽고, 노트북에서 MapServer·AMCL을 실행했다. 엔코더 읽기 전용 처리와 Nav2 속도 출력 분리는 프로젝트 점검에 적용한 구성이다. [센서 수신](03-PHYSICAL-READONLY-LAB.md) · [지도와 Nav2](05-FIELD-NAV2-CHECK.md) · [Dynamixel 엔코더 읽기](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/api_reference/python/python_groupbulkread/) · [Nav2 Keepout Filter](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/)

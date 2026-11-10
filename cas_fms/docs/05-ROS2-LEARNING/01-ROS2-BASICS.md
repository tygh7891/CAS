# ROS 2 기초와 FMS 연결 구조

[학습 홈](README.md) · [다음 실습 · Gazebo](02-GAZEBO-FMS-LAB.md)

## 로봇 한 대의 프로그램을 나눠 보기

ROS는 *Robot Operating System*의 약자다. ROS 2는 라이다, 모터 제어, 위치 추정, 경로 계획처럼 역할이 다른 프로그램이 메시지를 주고받는 데 쓰는 도구 모음이다. 각 역할을 수행하는 실행 단위를 **노드**라고 부른다. 노드와 실행 설정을 배포하는 단위는 **패키지**다. 여러 노드를 같은 설정으로 켤 때는 `launch` 파일을 사용한다. [ROS2 2강 · 기초 명령](../../../../../dev_ws/ROS2/docs/present_02_ROS_기초명령.html) · [ROS2 3강 · 패키지와 토픽](../../../../../dev_ws/ROS2/docs/present_03_패키지_만들고_토픽_다루기.html) · [ROS2 7강 · 실행과 디버그](../../../../../dev_ws/ROS2/docs/present_07_디버그와_관찰을_위한_도구들_그리고_roslaunch.html)

| 용어 | 기억하기 쉬운 예 | 이 프로젝트에서 보는 예 |
| --- | --- | --- |
| 토픽(topic) | 라디오 채널처럼 데이터가 계속 올라온다. 듣는 쪽은 관심 채널을 구독한다. | `/scan`은 라이다 거리 배열, `/odom`은 바퀴 움직임을 바탕으로 추정한 위치와 속도, `/cmd_vel`은 속도 명령이다. |
| 서비스(service) | 한 번 요청하면 한 번 응답한다. | ROS 2의 상태 조회나 설정 질의에 쓰인다. FMS의 HTTP API는 별도의 통신 인터페이스다. |
| 액션(action) | 오래 걸리는 작업의 목표를 보내고 진행 상황과 최종 결과를 받는다. 실행 중 취소도 요청할 수 있다. | `navigate_to_pose`는 목표 위치로 이동하고 `spin`은 제자리에서 회전한다. |
| 파라미터(parameter) | 실행 중인 노드에 적용되는 설정값이다. | `use_sim_time`은 가상 시간 사용 여부를 정한다. Nav2의 목표 허용 오차도 파라미터다. |

[ROS2 4강 · 메시지와 서비스](../../../../../dev_ws/ROS2/docs/present_04_메시지_정의_만들고_토픽과_서비스에서_다루기.html) · [ROS2 5강 · 액션](../../../../../dev_ws/ROS2/docs/present_05_액션_익숙해지기.html) · [ROS2 6강 · 파라미터](../../../../../dev_ws/ROS2/docs/present_06_파라미터_다루기.html)

## 로봇이 지도에서 자기 위치를 아는 방법

**TF**는 좌표계 사이의 변환을 다룬다. 같은 `(0, 0)`도 지도 원점과 로봇 중심에서 각각 다른 곳이다. `map → odom → base_footprint`를 따라가면 지도 기준의 로봇 위치를 얻을 수 있다. `map`은 팀이 공유하는 지도 좌표계이고, `odom`은 로봇이 움직인 거리를 계속 쌓아 가는 좌표계다. `base_footprint`는 로봇 몸체를 바닥에 투영한 기준점이다. 바퀴에서 계산한 위치는 오차가 쌓일 수 있다. **AMCL**은 저장된 맵과 라이다 관측을 비교해 `map`에서 로봇이 어디에 있는지 추정한다. [ROS2 8강 · TF 발행](../../../../../dev_ws/ROS2/docs/present_08_TF로_좌표계와_자세pose_발행하기.html) · [ROS2 10강 · TF 구독](../../../../../dev_ws/ROS2/docs/present_10_TF_frame을_구독하고_좌표계_사이의_정보를_활용하는_법.html) · [SLAM-Nav2 4강 · 위치 추정](../../../../../dev_ws/SLAM-Nav2/present_04_Localization.html)

**SLAM**은 *Simultaneous Localization and Mapping*의 약자다. 움직이는 동안 자기 위치를 추정하고 동시에 지도를 만든다. 이 프로젝트에서는 팀원이 저장한 맵을 MapServer로 불러온다. **Nav2**는 이 지도와 로봇 위치를 바탕으로 경로를 계획하고, 컨트롤러로 바퀴에 전달할 속도 명령을 계산한다. RViz의 **2D Pose Estimate**는 현재 위치와 방향의 초기 추정치를 지정한다. **Nav2 Goal**은 이동할 목적지를 지정한다. [SLAM-Nav2 3강 · 맵 작성](../../../../../dev_ws/SLAM-Nav2/present_03_ROS2_SLAM_map_building.html) · [SLAM-Nav2 5강 · 내비게이션](../../../../../dev_ws/SLAM-Nav2/present_05_Navigation_PKG_다뤄보기.html) · [Pinky 4강 · 저장한 맵으로 주행](../../../../../dev_ws/Pinky/04_present_PinkyPro_내비게이션으로_주행하기.html)

| 파일 또는 화면 | 역할 |
| --- | --- |
| `fleet_world_new.pgm`과 `.yaml` | PGM의 각 픽셀은 지도 셀이다. YAML은 이미지 파일명과 해상도, 원점을 지정한다. 이 맵은 픽셀당 1cm다. |
| `fleet_x_keepout_new.pgm`과 `.yaml` | X자 통로 바깥의 진입 제한을 지정한다. Nav2의 KeepoutFilter가 경로 계획과 주행에 반영한다. |
| Gazebo 공간(SDF) | 가상 로봇이 움직이고 가상 라이다가 벽을 감지하는 공간이다. 이 프로젝트는 맵의 점유 셀 위치에 벽을 만들고 X자 마스크를 바닥에 표시한다. |
| RViz | 맵, 라이다, 좌표계, 계획 경로 같은 ROS 2 데이터를 시각화한다. Gazebo에서 볼 수 있는 움직임을 ROS 2 데이터와 대조하는 데 쓴다. |

[SLAM-Nav2 1강 · 로봇 모델](../../../../../dev_ws/SLAM-Nav2/present_01_ROS2_Description_PKG_for_Mobile_Robot.html) · [SLAM-Nav2 2강 · Gazebo](../../../../../dev_ws/SLAM-Nav2/present_02_ROS2_Gazebo_PKG.html) · [ROS2 11강 · RViz로 TF 보기](../../../../../dev_ws/ROS2/docs/present_11_TF_frame의_작업_결과를_rviz2에서_시각화하기.html)

## 두 대를 구분하고 교차로 순서를 정하는 방법

**ROS 2 도메인**을 통신 그룹 번호로 생각하면 된다. 두 로봇 모두 `/scan`과 `/odom`이라는 이름을 쓰므로, 각 Worker와 대상 로봇을 같은 `ROS_DOMAIN_ID`로 묶어 분리한다. 이 프로젝트는 Worker 프로세스를 로봇마다 하나씩 실행한다. 가상 모드는 `114`와 `130`, 실물 연결의 기본값은 `14`와 `30`이다. **Gazebo Bridge**는 가상 라이다와 주행 명령을 Gazebo와 ROS 2 사이에서 전달한다. 강의에서 다룬 `domain_bridge`는 ROS 2 도메인 사이의 전달을 다룬다. [ROS2 12강 · 도메인 ID](../../../../../dev_ws/ROS2/docs/present_12_하나의_노드에서_서로_다른_도메인ID에_접근.html) · [ROS2 13강 · 두 도메인 실습](../../../../../dev_ws/ROS2/docs/present_13_하나의_노드에서_서로_다른_domain_id의_turtlesim을_다뤄보자.html) · [ROS2 14강 · domain_bridge](../../../../../dev_ws/ROS2/docs/present_14_ros_domain_bridge를_이용해서_다른_domain_id에_접근해보자.html)

```text
PyQt 화면 ↔ Flask FMS 서버 ↔ 로봇별 Worker ↔ Nav2 ↔ 센서·모터 또는 Gazebo
          HTTP + JSON      HTTP + JSON        ROS 2
```

화면은 시작·취소 요청을 서버에 보낸다. 서버는 교차로 진입 순서를 정하고, Worker는 그 단계에 맞는 Nav2 목표를 보낸다. 두 대가 대기점에 도착하면 한 대만 통과 허가를 받는다. 앞 로봇이 빠져나온 사실을 최신 위치로 확인한 뒤 다음 로봇이 출발한다. 위치 확인이 끊기면 허가를 유지하고 다음 진입을 보류한다. 로봇은 각자의 센서를 사용해 위치와 주행을 처리한다. [Pinky 8강 · Flask](../../../../../dev_ws/Pinky/08_present_Flask_사용해보기.html) · [SLAM-Nav2 6강 · Python으로 목표와 취소 다루기](../../../../../dev_ws/SLAM-Nav2/present_06_Python으로_Nav2_다뤄보기.html) · [FMS 코드 구조](../04-ENGINEERING/FMS-ARCHITECTURE.md)

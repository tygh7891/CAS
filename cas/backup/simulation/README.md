# B2 — 하나의 Gazebo 공간과 Pinky 두 대

현재 단계는 연결 점검용 가상 공간입니다. 수령한 SLAM 지도·X 마스크와 같은 공간이 아니며, Nav2·중앙 서버·GUI의 주행 연결은 아직 없습니다.

## 준비 결과

- Gazebo Harmonic 8.15.0, ROS2 Jazzy의 ros_gz 연결 패키지 확인.
- rosdep check: pinky_description·pinky_gz_sim의 시스템 의존성 충족. 추가 설치 없음.
- 두 패키지를 ~/CAS_sim_ws에 빌드 완료. 저장소의 로봇 원본은 변경하지 않음.
- prepare.py가 원본 xacro를 읽어 생성물에서만 링크·관절·센서·TF·명령 이름을 로봇별로 통일. 카메라·IMU·램프는 이번 점검에서 제외.
- 생성 파일: ~/CAS_sim_ws/generated/{robot_1.urdf,robot_2.urdf,bridge.yaml,connection_test.sdf}
- 하나의 물리 공간 안에 robot_1과 robot_2를 서로 떨어진 위치에 둠. 물리 충돌은 같은 Gazebo 서버에서 계산.

## PC 터미널 1 — Gazebo 실행

```bash
bash ~/CAS/cas/backup/simulation/run_sim.sh
```

시뮬레이터 실행은 사용자가 보는 터미널에서 진행합니다. 스크립트는 모델 파일을 재생성한 뒤 Gazebo 창과 브리지·로봇 상태 발행기를 함께 시작합니다. 두 로봇을 띄우기 위해 같은 명령을 두 번 실행하지 마세요.

실물과의 분리: 이 스크립트 내부의 ROS_DOMAIN_ID=84, localhost 통신, GZ_PARTITION=cas_independent_b2, GZ_IP=127.0.0.1을 사용합니다. 다른 터미널의 도메인 14/30이나 로봇 설정을 변경하지 않습니다. ROS_LOCALHOST_ONLY deprecated 경고가 나타날 수 있으나 현재 Jazzy에서 적용되는 설정입니다.

원본의 gz_frame_id 확장 태그가 SDF 표준 태그가 아니라 복사한다는 변환 경고가 나올 수 있습니다. 그 자체로 생성 실패는 아닙니다. 실제 센서 프레임은 아래 점검으로 확인합니다.

## PC 터미널 2 — 센서·명령 수신 경로 조회만

Gazebo 창이 열리고 두 로봇이 보이면 새 PC 터미널에서:

```bash
bash ~/CAS/cas/backup/simulation/check_sim.sh
```

15초 동안 /clock과 각 로봇의 odom·scan·joint_states·tf를 구독하고, cmd_vel 브리지 구독자도 조회합니다. 이 점검은 이동 명령을 보내지 않습니다.

정상 결과:

```text
B2 SENSOR CHECK PASSED (SIMULATION ONLY)
```

두 로봇의 /robot_1/*, /robot_2/* 토픽과 robot_1/..., robot_2/... 프레임을 확인합니다. ROS /clock은 하나만 브리지합니다. odom 원점은 Gazebo의 생성 위치와 같다고 가정하지 않으며 map 정합은 다음 Nav2 단계에서 확인합니다.

종료: 터미널 1에서 Ctrl+C. 점검 스크립트는 자동 종료합니다. 외부 실물 프로그램에는 정지 명령을 보내지 않습니다.

## 코드 준비만 검사 (PC 터미널)

```bash
source /opt/ros/jazzy/setup.bash
source ~/CAS_sim_ws/install/local_setup.bash
/usr/bin/python3 ~/CAS/cas/backup/simulation/prepare.py --output ~/CAS_sim_ws/generated
/usr/bin/python3 ~/CAS/cas/backup/simulation/test_generated.py
```

오프라인 모델 변환·정적 검사 4개·실행 파일 문법과 LaunchDescription 생성 검사 통과. 실제 Gazebo 시작·렌더링·센서 메시지 수신은 사용자 실행 확인 전이므로 완료로 간주하지 않습니다. 소프트웨어 렌더링 등 추가 조정이 필요하면 실행 로그를 보고 결정합니다.

## 재현용 빌드 명령 (PC 터미널)

다른 PC에서 시스템 의존성이 준비된 경우:

```bash
source /opt/ros/jazzy/setup.bash
colcon --log-base ~/CAS_sim_ws/log build \\
  --base-paths ~/CAS/pinky_description ~/CAS/pinky_gz_sim \\
  --packages-select pinky_description pinky_gz_sim \\
  --build-base ~/CAS_sim_ws/build --install-base ~/CAS_sim_ws/install \\
  --executor sequential --cmake-args -DBUILD_TESTING=OFF
```

기본 경로는 ~/CAS_sim_ws이며 별도 설치 위치는 CAS_SIM_WS 환경 변수로 지정할 수 있습니다. 정적 test_generated.py는 기본 경로를 사용합니다.

## 근거와 다음 단계

Gazebo ROS 브리지는 토픽별 메시지 타입·방향을 지정하며, 두 로봇의 토픽 이름을 명시적으로 분리합니다. DiffDrive의 frame_id·child_frame_id·tf_topic도 구분했습니다.

- https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md
- https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1DiffDrive.html

다음은 실제 사용자 실행·센서 검사입니다. 통과 후 수령 지도의 벽 배치와 일치하는 공간·시작 위치를 준비하고 Nav2로 넘어갑니다. keepout 마스크의 통행 의미는 팀원 확인 전 적용하지 않습니다.

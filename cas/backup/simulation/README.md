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

## B2 지도 대응 프로필 (연결 시험 공간과 별도)

사용자가 확인한 정책: 원본 허용 마스크의 흰 픽셀(화면의 파란 X)이 통행 가능, 강조되지 않은 흰 내부는 금지, X 중앙은 공유존이다. 원본 map/ 파일은 읽기만 한다.

### PC 터미널 1 — 지도 대응 Gazebo

기존 시험 공간을 실행한 터미널에서 먼저 Ctrl+C로 종료한 뒤:

```bash
bash ~/CAS/cas/backup/simulation/run_map_sim.sh
```

도메인84·localhost·Gazebo partition은 기존 시험과 동일하므로 두 Gazebo 세션을 동시에 실행하지 않는다. generated_map에 생성하고, 기존 generated 연결 시험 공간은 보존한다.

- 지도 점유 픽셀만 정확히 직사각형으로 분할·병합해 0.30m 높이의 충돌 도형으로 만든다. 2D 지도에서 얻을 수 없는 실제 벽 높이는 가상 공간용 가정값이다.
- 내부 금지 영역에는 물리 벽을 만들지 않는다. 파란 통로와 노란 공유존 후보는 시각 표시만 있고 충돌 도형이 없다.
- 로봇은 좌측 하단 1 후보와 우측 하단 2 후보에 생성하며 이동 명령은 발행하지 않는다. 후보 좌표는 운용 확정이 아니다.
- 중앙 후보는 두 대각 통로의 회귀 직선 교점에서 추정한다. 목적지·시작 후보는 지도 자유 공간과 허용 통로 내 반경 0.12m 이상 여유를 요구하며, 중앙까지의 직선 구간에서 반경 0.10m+0.005m 여유를 샘플링 검사한다. 이는 실제 footprint·회전·Nav2 경로 검증을 대체하지 않는다.
- 대기점 후보는 공유존(0.30m 정사각형) 바깥에서 모의 반경0.10m+여유0.02m를 확보한 후보다. 최종 공유존 크기·대기점은 B3에서 검증한다.

### PC 터미널 2 — 센서 조회

```bash
bash ~/CAS/cas/backup/simulation/check_sim.sh
```

15초 후 모든 센서·프레임·시계 검사가 통과하는지 확인한다. 이 검사만으로 지도 위치 추정·Nav2 주행·통행 제한이 검증된 것은 아니다.

### PC 터미널 3 — 미승인 후보 지도 화면

기존 CAS GUI 창을 닫은 뒤:

```bash
bash ~/CAS/cas/backup/simulation/view_map_candidates.sh
```

통행 허용 영역 체크박스를 켜면 파란 X와 A·B·1·2 후보, W1·W2 대기점, 노란 중앙 공유존 후보가 보인다. 작업 명령은 계속 잠겨 있고 실제 Gazebo 로봇 상태는 아직 이 GUI에 연결하지 않는다.

### Nav2 통행 제한 마스크 초안

`~/CAS_sim_ws/generated_map/nav2_keepout_draft.yaml` 및 PGM을 생성하지만 Nav2에는 아직 적용하지 않는다. `negate: 0`의 trinary에서 흰색은 자유0, 검정은 점유100이므로 원본의 허용 흰색을 반전하지 않는다. 별도 초안에서는 원본 X 허용 영역 중 기본 지도에서도 자유인 픽셀만 흰색으로 남기고, 실제 벽·미확인·금지 영역은 검정으로 한다. 원본 지도·마스크와 별개 파일이다.

이전 설명에서 제안했던 단순 마스크 반전은 사용하지 않는다. 원본 흰색을 금지로 뒤집으면 사용자 정책과 반대가 된다. Nav2 Keepout은 OccupancyGrid 의미를 따르며, B3에서 global/local costmap 적용과 footprint 경계 검증이 필요하다.

- https://docs.nav2.org/rolling/tutorials/general_tutorials/navigation2_with_keepout_filter/navigation2_with_keepout_filter/

### 검사와 산출물

지도 프로필 정적 검사 6개·기존 지도/서버/GUI 검사 17개 통과. 수령 지도와 마스크는 Git 추적하지 않고 별도 전달받는다. 생성물도 저장소 밖 ~/CAS_sim_ws/generated_map에 두며 코드와 설명만 작업 브랜치에 올린다.

`scenario.candidates.json`: 미승인 좌표·공유존 후보·원본 지도 fingerprint.
`map_profile_report.json`: 원본 경로·가정값·벽 도형 수·통행 픽셀 수·keepout 미적용 기록.

```bash
python3 ~/CAS/cas/backup/simulation/test_map_profile.py
```

다른 지도 파일은 CAS_MAP_YAML·CAS_MASK_YAML 환경 변수로 지정할 수 있다. X 형태가 아니거나 여유거리·후보 경로 검사를 통과하지 못하면 생성기를 보완하거나 수동 후보를 준비해야 하며 임의 좌표로 강행하지 않는다. 이번 프로필의 Gazebo 사용자 실행 확인은 아직 대기 중이다.

### B3: Nav2 준비 확인 (이동 출력 차단)

지도 월드가 실행 중인 PC의 새 터미널에서:

```bash
bash ~/CAS/cas/backup/simulation/run_nav2_preview.sh
```

다른 PC 터미널에서:

```bash
bash ~/CAS/cas/backup/simulation/check_nav2_preview.sh
```

도메인 84에 로봇별 AMCL, 지도 서버, 전역/지역 costmap의 keepout 필터,
Nav2 Action 서버를 생성합니다. 초기 위치는 생성된 Gazebo 월드의 spawn pose를 사용합니다.
속도 출력은 `/<robot>/nav2_preview_cmd_vel`에서 끝나며 Gazebo의 cmd_vel과 연결되지 않습니다.
확인 스크립트는 lifecycle, TF, Action 발견 및 cmd_vel 발행자 부재를 검사하며 목표를 보내지 않습니다.
이 검사는 통로 준수 주행이나 공유존 제어의 검증이 아닙니다. 후보 좌표 승인, 필터 실제 적용 확인,
경로 생성 검증, 주행 및 회전 검증은 이후 단계입니다. GUI 작업 명령은 계속 잠겨 있습니다.
반경 0.10m, 속도 0.08m/s, 목표 허용 오차 0.04m는 시뮬레이션 초기 설정입니다.

#### 시작점/작업점 배치

지도 이미지 기준 왼쪽 짧은 변의 위/아래가 `1`/`2`, 오른쪽 짧은 변의
위/아래가 `A`/`B`입니다. `1→B`, `2→A`가 중앙에서 교차합니다.
대기점은 각 출발점에서 공유존으로 접근하는 왼쪽 팔에 생성합니다.
배치 변경 후에는 기존 Nav2와 Gazebo를 종료하고, 지도 Gazebo → Nav2 →
확인 도구 순서로 재실행해야 월드의 spawn pose와 AMCL 초기 위치가 일치합니다.

### 경로만 계산하기 (주행 명령 없음)

지도 Gazebo와 Nav2 preview가 켜져 있고 B3 확인이 통과한 상태에서 PC의 다른 터미널:

```bash
bash ~/CAS/cas/backup/simulation/check_paths.sh
```

`ComputePathToPose`로 현재 추정 위치에서 robot_1→B, robot_2→A 경로를 요청합니다.
NavigateToPose, Spin, cmd_vel은 전송하지 않습니다. 주행 출력 차단 설정은 그대로 둡니다.
지도/후보 fingerprint와 경로 frame, 시작/도착 오차, 전체 선분의 통로 포함 여부,
원형 반경 0.10m의 보수적 여유 공간 및 중앙 공유존 통과를 검사합니다.
여유 공간은 각 금지 픽셀 사각형의 경계까지 실제 거리를 계산하고,
샘플 사이의 간격 절반을 차감한 보수적 하한입니다.
따라서 경계에 가까운 유효 경로도 실패할 수 있습니다. 실패를 무시해 주행하지 않습니다.
결과 JSON 및 경로 그림(1번 파랑, 2번 빨강)은 `~/CAS_sim_ws/generated_map/path_checks/`에 저장됩니다.
이 검사는 시간 충돌, 대기점 정지, 권한 획득/반납, 회전/동역학, 실제 로봇 안전성을 검증하지 않습니다.
좌표 후보의 승인 상태와 GUI 명령 잠금도 바꾸지 않습니다.

### 공유존 정지·권한 제어 준비

`mission_routes.py`는 출발→대기 / 대기→이탈 / 이탈→작업점의 세 구간을 만듭니다.
이전에 통과한 동일 지도 Nav2 전체 경로 위에서 대기·이탈점을 선택합니다.
기존 GUI 후보 대기점과 별개로 반경 0.10m 바깥 최소 0.08m 여유를 둡니다.
실행 중인 월드나 GUI 좌표를 변경하지 않습니다. 후보 상태는 미승인으로 유지됩니다.

Gazebo와 Nav2 preview를 그대로 둔 PC의 새 터미널에서:

```bash
bash ~/CAS/cas/backup/simulation/check_paths.sh --segments
```

동일 지도에서 통과한 최신 전체 경로를 대기점·이탈점에서 그대로 분할하여
여섯 구간을 검사합니다. 구간마다 Nav2 경로를 새로 계산하지 않습니다.
JSON reference_report와 path_source에 원본과 분할 방식을 기록합니다.
분할 구간을 이어 붙이면 원본 전체 경로와 정확히 같습니다. 실제 주행 성공을 뜻하지 않습니다. 접근/이탈 구간은 몸체와
공유존 사이에도 목표 오차 이상의 여유가 있어야 통과합니다. 그림의 wait/exit
표시와 JSON `mission_routes`가 다음 연결 단계의 후보입니다.

`zone_coordinator.py`는 ROS 입출력 없는 별도 관측 기반 제어 핵심입니다.
Nav2 성공 결과 후 새 속도 관측으로 0.3초 정지 확인 → 진입 요청 → 단일 권한 →
통과 관측 및 이탈점 도착/정지 확인 → 권한 해제 → 목적지 이동 → 회전 → 정지 확인입니다.
관측이 1초 이상 오래되거나 비허가 진입/명령 실패가 생기면 취소 의도를 생성하고
진행을 보류하며 권한을 유지합니다. 이전 명령 결과나 반복된 source stamp는 반영하지 않습니다.
권한 요청은 확인된 대기 순서, 같은 tick은 robot ID 순서입니다.

**현재 제한:** 이 핵심은 검증된 구간을 따르는 FOLLOW_PATH 명령 의도만 생성합니다.
주행 연결은 NavigateToPose 재계획이 아닌 FollowPath Action을 사용할 예정입니다. 실시간 Nav2 Worker 전송,
취소 확인, 관측 시각/TF/odom 동기화, 서버 상실 시 정지와 GUI 연결은 아직 연결 전입니다.
경로 재계획/복구 동작이 허가 없이 공유존을 침범하지 못하도록 제한하는 작업도 필요합니다.
따라서 아직 주행 출력 차단을 해제하지 않습니다. 여섯 구간 확인 결과 후 연결합니다.


경계에 붙는 분할 경로를 줄이기 위해 NavFn의 Dijkstra 모드를 사용합니다
(`use_astar: false`). 반경 0.10m나 목표 허용 오차는 줄이지 않습니다.
경로 검사는 접촉 수준의 여유를 통과 처리하지 않습니다. 설정 변경 후에는
Nav2 preview를 재시작하고 구간 경로 검사를 다시 실행해야 합니다.

### 실시간 Worker 준비 확인 (읽기 전용)

Gazebo와 Nav2 preview를 켜 둔 PC의 새 터미널에서:

```bash
bash ~/CAS/cas/backup/simulation/check_workers.sh
```

고정 대기 시간 없이 최대 25초 내 준비 조건이 1초 연속 유지되면 종료합니다.
2초마다 로봇별 위치, 관측 나이, odom 속도, Action 준비 상태를 터미널에 표시합니다.
`~/CAS_sim_ws/generated_map/worker_checks/`에 JSON 결과를 저장합니다.

`nav2_worker.py`는 PC의 로봇별 Worker입니다. 로봇별 TF 버퍼와 odom으로
같은 source 시각의 map 위치를 조회합니다. 반복/역행/미래/오래된 odom 시각은
유효 관측으로 갱신하지 않습니다. FollowPath는 좌표를 보존하고 각 경로의 접선 방향을
목표 자세로 사용합니다. Action 접수와 완료를 구분하고 Nav2 결과 코드까지 확인합니다.
취소가 접수 응답보다 먼저 발생하면, 뒤늦게 수락된 목표에도 취소를 요청합니다.

기본 `allow_actions=False`로 명령 전송이 잠겨 있고, 확인 도구는 이를 해제하지 않습니다.
`MissionCoordinator.start()`도 호출하지 않습니다. FollowPath/Spin 접속 여부, 초기 위치,
정지 속도, 최신 관측, 실제 cmd_vel 발행자 부재를 확인합니다. 목표나 속도를 보내지 않습니다.
검사 통과는 실시간 관측/인터페이스 준비만 뜻하며 이동·권한 인계 성공이 아닙니다.

아직 중앙 제어가 만든 명령을 Worker로 전달하는 실행 루프, 속도 출력 연결과 독립 감시 정지,
실주행 경로 이탈 감시, 취소 완료·최종 정지의 종합 확인 및 GUI 연동은 준비 전입니다.
이를 연결하고 검증하기 전에는 실물이나 Gazebo cmd_vel에 출력 연결을 추가하지 않습니다.

### Gazebo 실제 주행: 중앙 제어 + Worker + 별도 속도 감시

**이 명령은 가상 로봇 두 대를 움직입니다.** 지도 Gazebo와 Nav2 preview를
유지하고, 다른 PC 터미널에서 실행합니다. 시작 위치 확인과 인터페이스 준비는 자동입니다.

```bash
bash ~/CAS/cas/backup/simulation/run_mission.sh --start
```

원본 Nav2 preview 설정은 변경하지 않습니다. 별도 프로세스 `sim_velocity_relay.py`만
`/<robot>/nav2_preview_cmd_vel`을 Gazebo의 `/<robot>/cmd_vel`로 연결합니다.
로컬 domain 84 외에는 실행을 거부하며, 실물 14/30용 실행 기능은 없습니다.
기존 속도 발행자나 다른 진행 중 Action이 있으면 시작을 보류합니다.

터미널에 COMMAND, ZONE_REQUESTED, ZONE_GRANTED, ZONE_RELEASED, 상태와 위치가 표시됩니다.
각 로봇은 검증된 접근 경로→대기점 도착 및 0.3초 정지→순차 진입 허가→이탈점 도착/정지와
몸체 이탈 확인→목적지 이동→한 바퀴 회전→정지 확인으로 진행합니다.
현재 단계는 이탈점에서도 정지 확인합니다. 추후 연속 주행 최적화와 구분합니다.
회전 후 목적지에 남으며 출발점 복귀는 없습니다.

별도 감시 프로세스는 단조 시계 기준 0.25초 권한 임대와 0.15초 최신 속도 명령을 요구합니다.
임대가 만료되면 정지 상태를 유지하고 자동 재시작하지 않습니다. 명령이 바뀌면 이전 속도는 버립니다.
속도 상한은 0.08m/s, 0.4rad/s입니다. 실행 루프는 관측 지연, 경로 오차 2.5cm 초과,
추정 몸체-금지 영역 거리 10cm 미만, 로봇 간 거리 22cm 미만, 비허가 공유존 진입을 감시합니다.
실제 주행 오차와 정지 거리는 이 첫 주행 결과로 확인해야 합니다.

`Ctrl+C`는 취소를 요청하고 속도를 차단한 뒤 정지를 확인합니다.
오류 시 점유권은 해제하지 않으며 로그에 남습니다. 최종 로그에서 FINAL_STOP confirmed와
MISSION PASSED 여부를 확인합니다. 오류/중간 정지 후에는 초기 위치가 아니므로 바로 재실행하지 말고
로그를 검토한 뒤 월드와 Nav2를 초기화합니다. 로그는 `~/CAS_sim_ws/generated_map/mission_logs/`에 저장됩니다.

한 프로세스만 죽으면 별도 속도 감시가 0속도를 발행할 수 있지만, 감시 프로세스까지 함께 강제 종료되는
상황의 정지는 이 구성으로 보장하지 않습니다. 실물용 드라이버 watchdog과 별도 검증이 필요합니다.
GUI는 아직 지도 검토 모드이며 이번 실행 상태는 터미널에서 확인합니다.

#### 주행 전 전체 연결만 확인

```bash
bash ~/CAS/cas/backup/simulation/run_mission.sh --check-only
```

별도 감시 프로세스까지 실행하지만 작업/이동/회전 목표를 전송하지 않고 0속도만 출력합니다.
준비 확인 후 감시 프로세스까지 정리하고 종료합니다. 기존 읽기 전용 Worker 검사와 달리
속도 출력 연결 자체를 포함하므로, 다른 속도 발행자가 있으면 실행을 거부합니다.
PREFLIGHT_STATUS에는 관측 수신/거부 수, clock-odom 시차, 감시 상태를 2초마다 표시합니다.
감시 갱신은 별도 송신 스레드에서 처리하되, 실행 루프의 진행 신호가 0.15초 이상
끊기면 갱신하지 않습니다. 독립 송신 스레드가 멈춘 실행 루프를 대신하여 권한을 연장하지 않습니다.


#### 몸체 크기 기준 일치

`robot_radius: 0.10`은 경로 검사와 공유존 판정에 쓰는 여유 포함 원형 반경입니다.
Nav2의 기본 `footprint_padding`을 중복 적용하지 않도록 전역/지역 costmap 모두
`footprint_padding: 0.0`을 명시합니다. 이전에는 기본 padding 0.01m가 각 축에
더해져 발행된 몸체 최대 반경이 약 0.11414m였습니다. 이 설정 변경은 충돌 검사를
비활성화하지 않으며, 실제 로봇 외형 측정과 여유 반경 검증을 대체하지 않습니다.
Nav2 재시작 후 `inspect_costmaps.sh`에서 적용값과 발행된 몸체를 다시 확인합니다.

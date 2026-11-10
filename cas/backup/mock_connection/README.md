# A2 — PC 내부 모의 명령 연결 시험

실제 로봇 연결 없이 도메인 14/30 분리, Nav2 타입의 모의 Action 접수·완료·취소를 시험합니다.

## 범위와 제한

- 모든 프로그램은 PC 터미널에서 실행합니다. SSH 접속 불필요.
- ROS_LOCALHOST_ONLY=1, ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST를 프로그램 내부에서 적용하며 Fast DDS를 사용합니다. 외부 peer/서버 설정은 자식 프로그램 환경에서 제거합니다. 사용자 쉘이나 로봇 설정을 수정하지 않습니다.
- 명령 이름은 /cas_mock/navigate_to_pose 및 /cas_mock/spin입니다. 실제 /navigate_to_pose·/spin은 사용하지 않으며 /cmd_vel을 발행하지 않습니다.
- 로봇별 프로그램은 같은 Action 이름을 쓰되 도메인으로 분리합니다. 각 도메인의 /cas_mock/identity 응답과 이동 피드백 프레임에 담긴 robot_id를 확인합니다.
- 시뮬레이션은 시간 경과로 성공을 반환할 뿐, Nav2 경로계획·물리적 주행·충돌 회피·지도·실제 회전 정확도를 검증하지 않습니다.
- 설치된 NavigateToPose·Spin 메시지 타입을 재사용하지만 실제 로봇의 Action 가용성 확인은 별도로 남습니다.

## PC 터미널 1 — 가상 로봇 1

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/mock_connection/mock_robot.py --robot robot_1
```

READY가 보이면 그대로 켜둡니다. 도메인은 프로그램이 14로 지정합니다.

## PC 터미널 2 — 가상 로봇 2

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/mock_connection/mock_robot.py --robot robot_2
```

READY가 보이면 그대로 켜둡니다. 도메인은 프로그램이 30으로 지정합니다.

## PC 터미널 3 — 두 로봇 시험

```bash
source /opt/ros/jazzy/setup.bash
python3 ~/CAS/cas/backup/mock_connection/test_connection.py
```

각 로봇에 이동 성공 → 회전 성공 → 새 이동의 중도 취소 순서로 요청합니다. 두 도메인 시험은 별도 자식 프로세스로 실행됩니다. 서버 로그에는 해당 로봇의 요청과 결과가 보이고, 시험 터미널에는 로봇별 PASS가 보입니다. 완료 시 ALL PASSED가 출력되어야 합니다.

FAIL이 나오면 세 터미널의 로그를 보존하고 원인을 확인합니다. 반복 실행 전 이전 시험이 종료됐는지 확인하세요. 무응답 시 유한한 대기 시간 뒤 실패 처리합니다. 서버를 종료하려면 각 서버 터미널에서 Ctrl+C를 누릅니다.

## 초기 검사 상태

PC 파일 문법 검사 완료. 실제 사용자 실행을 통한 모의 통신 시험은 아직 미실시입니다. 실물 A2 완료가 아닙니다.

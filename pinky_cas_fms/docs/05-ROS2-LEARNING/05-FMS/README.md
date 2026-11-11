# 05 · 한 대 왕복에서 두 대 통행권으로

[학습 목차](../README.md) · [강의 출처표](../00-START/SOURCE-INDEX.md) · [용어](../00-START/GLOSSARY.md)

**목표** · 작업 접수, 이동 명령, 교차로 예약, 실제 진입·이탈, 작업 완료를 각각 설명한다. Mac에서도 Python과 HTTP로 전체 흐름을 흉내 낸 뒤 CAS의 파일과 함수를 읽는다.

| 필요한 이론 | HTML 원본에서 볼 슬라이드 |
|---|---|
| 각도 오차·PID·내적·상태 머신 | [ROS2-15](../00-START/SOURCE-INDEX.md#ros2-15) 31·52번, [ROS2-16](../00-START/SOURCE-INDEX.md#ros2-16) 5·31·47번, [ROS2-17](../00-START/SOURCE-INDEX.md#ros2-17) 12·20번, [ROS2-18](../00-START/SOURCE-INDEX.md#ros2-18) 12·20·70번 |
| 토픽·서비스·액션·도메인 | [ROS2-05](../00-START/SOURCE-INDEX.md#ros2-05) 5·68번, [ROS2-10](../00-START/SOURCE-INDEX.md#ros2-10) 4·18번, [ROS2-12](../00-START/SOURCE-INDEX.md#ros2-12) 3·22번, [ROS2-13](../00-START/SOURCE-INDEX.md#ros2-13) 14·33번 |
| 다중 로봇 관제, Nav2 결과와 HTTP | [PINKY-01](../00-START/SOURCE-INDEX.md#pinky-01) 10번, [NAV-06](../00-START/SOURCE-INDEX.md#nav-06) 9·13·17·40번, [PINKY-08](../00-START/SOURCE-INDEX.md#pinky-08) 4·7·10·11번 |

## A · Mac 또는 Ubuntu에서 작업 단계 실습

```bash
python3 05-FMS/fleet_lab.py --robots 1
python3 05-FMS/fleet_lab.py --robots 2 --pause-first-exit
```

한 대 로그에서는 `GRANT → ENTER → RELEASE → SPIN → RETURN → COMPLETED`의 흐름을 찾는다. 복귀 때에도 `GRANT`와 `RELEASE`가 한 번 더 있다. 두 대 로그에서는 아래 순서를 찾아본다.

```text
GRANT robot_1 OUTBOUND
ENTER robot_1 OUTBOUND
HOLD robot_1 OUTBOUND: 이탈 미확인
RELEASE robot_1 OUTBOUND
...
GRANT robot_2 OUTBOUND
```

[fleet_lab.py](fleet_lab.py)의 `SharedZone.grant()`는 앞선 예약이 남아 있으면 대기열을 꺼내지 않는다. `see_exit()`는 진입을 관측했는지와 목적지 쪽 이탈을 확인한다. `--pause-first-exit`은 이탈 보고가 들어오기 전 상태를 로그 한 줄로 보여준다. 이 예제는 이벤트를 순서대로 만든다. 실제 로봇의 시간, 위치, 네트워크는 CAS에서 Worker 보고와 Nav2 액션으로 처리한다.

- **FIFO**는 *First In, First Out*이다. 통행권을 먼저 요청한 로봇이 앞에 선다.
- **State Machine**은 상태와 전이 규칙을 모은다. 교차로에 들어가기 전과 들어간 후에는 이탈을 판단할 조건이 다르다.
- ROS2-17 12·20번의 **내적**을 떠올린다. 목적지 방향이 오른쪽일 때, 교차로 중심에서 오른쪽으로 나간 좌표는 내적이 양수이고 왼쪽으로 후퇴한 좌표는 음수다. 실제 코드는 양수 여부와 교차로 겹침 여부를 함께 본다.

## B · HTTP로 작업을 등록하고 상태 읽기

PINKY-08에서는 Flask 카메라 서버로 HTTP 클라이언트와 서버를 연결한다. 아래는 표준 라이브러리로 같은 요청·응답 개념을 연습하는 코드다. 서버가 이미지 대신 작업 상태 JSON을 돌려준다.

```bash
# Mac 또는 Ubuntu 터미널 1
python3 05-FMS/http_lab.py
```

```bash
# 같은 컴퓨터 터미널 2
curl -fsS http://127.0.0.1:8766/api/state
curl -i -H 'Content-Type: application/json' \
  -d '{"robot_id":"robot_1","spin_count":1}' \
  http://127.0.0.1:8766/api/jobs
curl -fsS http://127.0.0.1:8766/api/state | python3 -m json.tool
```

처음에는 `pending: []`이다. 두 번째 응답의 HTTP 상태는 **202**, 본문은 **QUEUED**다. 마지막 조회에는 작업 하나가 보인다. `curl -d`는 본문을 보내므로 여기서는 POST 요청이 된다. `spin_count`에 -1을 넣으면 HTTP 400이 표시된다. [http_lab.py](http_lab.py)의 `do_POST()`에서 입력을 검증하고 큐에 넣는 부분을 찾아본 뒤 터미널 1을 Ctrl+C로 종료한다.

## C · 실제 CAS 파일과 함수 따라가기

이 표의 링크는 이 브랜치의 소스 위치다. 위 실습과 같은 개념이 실제 코드에서는 어디에 있는지 찾는다.

| 질문 | 실제 소스에서 볼 곳 |
|---|---|
| GUI에서 누른 로봇 ID와 회전 횟수는 어디로 가나? | [fms_gui/main.py · MainWindow.enqueue():243](../../../../fms_gui/main.py#L243) → [fms_server/main.py · POST /api/jobs:43](../../../../fms_server/main.py#L43) → [job_manager.py · enqueue():28](../../../../fms_server/job_manager.py#L28) |
| 어떤 조건에서 바로 가고, 어떤 조건에서 대기점으로 가나? | [core.py · FMS._start():104](../../../../fms_server/core.py#L104) → [FMS._request_leg():79](../../../../fms_server/core.py#L79) |
| 교차로를 비운 것을 누가 확인하나? | [core.py · FMS._exited_on_goal_side():117](../../../../fms_server/core.py#L117) → [zone_manager.py · observe():47](../../../../fms_server/zone_manager.py#L47) → [core.py · FMS._grant_queued():139](../../../../fms_server/core.py#L139) |
| Worker가 읽은 위치와 명령은 어디서 만나는가? | [worker.py · Worker._sample_tf():61](../../../../pinky_fms/pinky_fms/worker.py#L61) → [Worker._tick():76](../../../../pinky_fms/pinky_fms/worker.py#L76) ↔ [core.py · FMS.worker_poll():201](../../../../fms_server/core.py#L201) |
| 서버 명령은 어떤 액션이 되는가? | [worker.py · Worker._apply_server_command():101](../../../../pinky_fms/pinky_fms/worker.py#L101) → [Worker._on_result():164](../../../../pinky_fms/pinky_fms/worker.py#L164) → [core.py · FMS._receive_result():158](../../../../fms_server/core.py#L158) |

CAS 기본 설정은 한 대 활성화다. 두 대는 [config.yaml의 active_robots와 경로](../../../../fms_server/config.yaml#L8), 서로의 최신 위치, 별도 Worker가 갖춰져야 한다. [서버의 통행권 인계 테스트](../../../../fms_server/tests/test_core.py#L70)에서는 선행 로봇의 주행 목표가 아직 진행 중이어도 실제 이탈 위치를 확인하면 다음 로봇에게 예약이 넘어간다.

**최종 확인 문제**

1. HTTP 202를 받았는데 로봇이 아직 출발하지 않을 수 있는 조건을 두 가지 말한다.
2. 먼저 들어간 로봇이 진입 방향으로 다시 빠지면 예약을 풀어도 되는지, 코드 한 곳을 찾아 근거를 든다.
3. `rclpy.spin()`, Nav2 `Spin`, GUI의 회전 횟수 입력이 각각 어떤 역할인지 구분한다.

**답 확인** · 1번은 출발점 근접, 최신 위치, 대기시간, 교차로 차단 등의 조건을 찾아본다. 2번은 `_exited_on_goal_side()`와 `observe()`의 해제 조건을 함께 읽는다. 3번은 콜백 처리, 로봇 회전 액션, 반복할 횟수로 각각 구분한다.

# 관제 구조 및 Zone 동작

[문서 홈](../README.md) · [시연 및 시험 기록](../02-TESTING/TEST-PLAN.md)

## [원문 요약] 구성과 경계

```text
운영자 / 콘솔 또는 GUI
        ↕ 작업 요청, 상태, 이벤트
Fleet Manager
        ↕ 작업 지시, 진입권, 위치, 주행 결과, Heartbeat
Robot Agent 1                   Robot Agent 2 또는 Mock Agent
        ↕ Nav2 Action                    ↕ Nav2 Action (실물 연결 시)
Pinky Pro 1                     Pinky Pro 2
```

- **Fleet Manager**가 로봇 목록, 작업 상태, Zone별 유효 진입권, 관제 로그를 관리한다. 자동 할당과 장애 복구 판단은 P1에 추가한다.
- **Robot Agent**가 각 로봇의 Nav2 목표 전송·취소, 위치·속도·주행 결과 수집을 담당한다. P1에서는 중앙 연결 감시와 로컬 정지 절차를 추가한다.
- **Nav2**가 각 로봇의 경로 계획·주행 제어를 맡는다. 두 Robot Agent는 같은 인터페이스를 쓰고 로봇 ID와 네임스페이스로 구분한다. Mock도 같은 계약으로 상태와 결과를 제공한다.

원문의 구성과 채널명을 바탕으로 정리했다. [원문 §3](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.nmynvspw691)

## [원문 요약] ROS 2 통신 초안

| 채널 초안 | 용도 |
| --- | --- |
| `/fleet/tasks` | 작업 요청 |
| `/fleet/robots/status` | 로봇 상태 |
| `/fleet/zone/request`, `/fleet/zone/release` | Zone 진입권 및 해제 요청 |
| `/fleet/events` | 이벤트 로그 |
| `/robot_1`, `/robot_2`의 Nav2 Action | 각 로봇의 `NavigateToPose` |
| 양방향 Heartbeat (P1) | FMS와 로봇의 통신 감시 |

메시지 타입과 통신 이름은 실제 개발 환경을 확인한 뒤 확정한다. 두 로봇의 지도 좌표가 일치하는지 확인한 뒤 Zone을 적용한다. [원문 §3](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.nmynvspw691), [원문 §9](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.wys1zxozv9r7)

## [원문 요약] P0 · 고정 Zone 예약과 순차 통과

- 고정 Zone 1개와 Zone 밖 대기점 2개를 설정한다. FMS는 한 로봇에만 진입권을 주고 다른 로봇을 `WAITING` 상태로 둔다.
- 안전한 이탈을 확인한 뒤 점유권을 해제하고 다음 로봇에 진입을 허가한다. 통신, 위치 신뢰도, 로봇 후미 이탈 여부가 불확실하면 점유를 유지하고 수동 확인한다.
- 관제 화면이나 콘솔에 로봇 ID, 상태, 작업 진행, Zone 소유권, 이벤트를 표시한다.

[원문 §4~5](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.6pof2qrg7e10), [원문 §9](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.wys1zxozv9r7)

## [원문 요약] P1 · 작업 배정과 통신 장애

- 작업은 `PENDING → ASSIGNED → RUNNING → SUCCEEDED / FAILED`로 추적한다. 가용 로봇 중 거리 등 비용이 작은 로봇을 고른다.
- FMS와 Agent는 서로 Heartbeat를 감시한다. 단절 로봇이 Zone을 점유했을 가능성이 있으면 FMS가 Zone을 `BLOCKED`로 유지하고 다른 로봇의 진입을 보류한다.
- 중앙 연결을 잃은 Agent는 로컬에서 기존 Nav2 Goal 취소와 정지 절차를 수행한다. 시험에서 실제 속도와 정지를 확인한다.
- 재연결 후 위치·속도·작업·예약권을 다시 대조한다. 단절 이전의 오래된 명령은 무시한다. 운영자가 승인하면 현재 상태에 맞춰 작업을 다시 지시하거나 이탈 확인 후 Zone을 해제한다.

연결 이상은 `SUSPECT` 또는 `LOST`로 감지한다. Heartbeat 주기·타임아웃·정지 판정 기준은 장비 점검과 실측 후 합의한다. [원문 P1](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.xqqvhi9mdlgd), [원문 §5~7](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.rjvsfnihz3gc)

## [원문 요약] P2 · 경로 중첩 후보

`ComputePathToPose`로 얻은 두 `nav_msgs/Path`를 같은 지도 좌표계에서 비교한다. 로봇 외형과 안전 여유를 고려해 겹치는 공간을 임시 Zone 후보로 표시한다. 경로가 갱신돼도 기존 점유권이나 허가를 강제로 해제하지 않는다. 시간 여유와 P0/P1 결과를 보고 후보 표시에서 실제 진입 제어까지 연동할지 결정한다. [원문 P2](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.3nsygdomupp5)

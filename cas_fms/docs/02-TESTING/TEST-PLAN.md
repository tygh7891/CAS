# 시연 및 시험 기록

[문서 홈](../README.md) · [관제 구조 및 Zone 동작](../01-DESIGN/FLEET-DESIGN.md)

## [원문 요약] 시작 전 확인

- 두 로봇의 ID, 네임스페이스, TF, 지도 기준점과 위치가 맞는지 확인한다. 각 로봇의 Goal 수락·완료·실패 수신과 수동 정지 수단을 점검한다.
- 고정 Zone 경계와 Zone 밖 대기점 2개를 설정한다.
- 통신 차단 시험은 바퀴를 들어 올리거나 제한된 시험 구역에서 로컬 정지 동작을 먼저 확인한다. Goal 취소 응답과 별도로 실제 로봇의 속도와 정지를 확인한다. 실물 정지를 확인할 수 없으면 장애를 유발하는 자동 주행 시험을 중단한다.
- Day 1까지 두 대 동시 Nav2 주행이 불안정하면 실물 1대 + Mock 구성으로 Zone 로직을 검증한다.

[원문 §5](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.63398ssk3bn6), [원문 §9](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.wys1zxozv9r7)

## [원문 요약] 시나리오와 판정

| ID | 단계 | 수행 방법 | 판정 근거 |
| --- | --- | --- | --- |
| S1 | P0 | 두 로봇에 서로 다른 목표를 주고 개별 주행을 관제한다. | 로봇 ID별 위치·작업 상태·Goal 결과와 물리적 주행을 확인한다. |
| S2 | P0 | 반대 방향에서 같은 Zone의 진입을 요청한다. 먼저 허가받은 로봇이 완전히 벗어나면 다른 로봇이 통과한다. | 한 로봇만 허가받고 상대는 대기하는지, 이탈 후 충돌 없이 순차 통과하는지 확인한다. |
| S3 | P1 | 통제된 환경에서 Zone 안 로봇의 통신을 차단한다. | 마지막 Heartbeat, `LOST`, `BLOCKED`, 정지 명령과 실제 속도를 기록한다. 장애 중 다른 로봇에 허가가 발급되는지 확인한다. |
| S4 | P1 | 통신을 복구한 뒤 위치·속도·작업·예약권을 대조하고, 운영자 승인 후 조치한다. | 승인 전 자동 재출발, 오래된 명령의 실행, 점유 확인 전 잠금 해제의 발생 여부를 기록한다. |
| S5 | P2 · 선택 | 서로 다른 목표의 경로를 수집하고 중첩 후보를 검출한다. | 후보가 지도 또는 로그에 표시되는지 확인한다. 주행 제어까지 연동했다면 기존 점유권을 유지한 채 진입 순서를 제어하는지 확인한다. |

원문의 임시 반복 계획은 S1/S2 각 10회다. K1의 예약 경합 시험 목표는 10회 이상이다. S3/S4는 안전 조건을 충족한 뒤 제한적으로 반복한다. [원문 §6](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.jktln7f8nag8), [원문 §7](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.9oujfy34nd36)

## [원문 요약] 지표

| ID | 지표 | 집계 방법 |
| --- | --- | --- |
| K1 | 중복 유효 진입권 | 동일 Zone에 서로 다른 로봇의 유효 예약권이 겹친 건수와 경합 시험 횟수를 기록한다. 목표는 0건이다. |
| K2 | 작업 완료율 | 성공 작업 수 ÷ 요청 작업 수 × 100(%). 정상과 장애 시험을 분리한다. |
| K3 | 평균 대기시간 | Zone 요청부터 허가 발급까지 걸린 시간을 평균한다. |
| K4 | 장애 감지 지연 | 마지막 유효 Heartbeat 수신부터 `LOST` 판단까지 걸린 초를 기록한다. Heartbeat 주기·타임아웃도 남긴다. |
| K5 | 정지 반응 | 장애 검출부터 속도가 정지 기준 이하가 될 때까지 걸린 시간과 추가 이동거리를 기록한다. 오도메트리로 측정했으면 오차 가능성을 남긴다. |
| K6 | 복구 안정성 | 승인 전 자동 재출발과 위험한 잠금 해제의 건수를 각각 기록한다. 목표는 각각 0건이다. |
| K7 | 작업 배정 효과 · 선택 | 동일 환경과 작업 세트에서 수동·순번 배정 대비 거리 기반 배정의 총 작업시간·이동거리 변화율을 비교한다. |

감지·정지 허용치는 실제 속도와 제동 실험을 바탕으로 확정한다. 지표에는 시험 횟수나 작업 수 같은 분모를 함께 남긴다. P2에서는 별도로 고정 Zone과 동적 Zone의 대기시간·총 작업시간을 비교한다. [원문 §7](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.9oujfy34nd36), [원문 P2](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.3nsygdomupp5)

## [원문 요약] 공통 로그 필드

`timestamp`, `robot_id`, `task_id`, `zone_id`, `state_before`, `state_after`, `event_type`, `reservation_id`, `position(x,y,yaw)`, `speed`, `reason`을 남긴다. [원문 §7](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.9oujfy34nd36)

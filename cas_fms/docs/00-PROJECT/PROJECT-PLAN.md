# 제안서 분석 및 3일 계획

[문서 홈](../README.md)

## [원문 요약] 프로젝트 목표

Pinky Pro 2대가 각자 Nav2로 이동하는 동안, 중앙 Fleet Manager가 로봇 상태를 관제하고 좁은 통로나 교차로에 해당하는 공유 Zone의 진입 순서를 조정한다. 3일 시연의 최소 성과는 **실물 2대의 독립 주행, 중앙 명령과 상태 표시, 고정 Zone 1개에서 순차 통과**다. 원문 작성 시점에 실물 2대는 확보 예정이었다. [원문 §1~2](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.15pd6uwkqjnl)

## [원문 요약] 범위와 우선순위

| 우선순위 | 범위 | 확인할 결과 |
| --- | --- | --- |
| P0 · 필수 | 두 로봇을 같은 지도 좌표계에 연결하고, 각 로봇의 Nav2 명령·결과와 수동 정지를 확인한다. 고정 Zone 1개, 바깥 대기점 2개, 배타적 진입권, 이탈 확인과 다음 진입 허가를 구현한다. 콘솔 또는 간단한 화면에 상태와 로그를 표시한다. | 두 로봇이 구분되고 같은 Zone을 순차 통과한다. 예약 경합 시험 10회 이상에서 중복 유효 허가 0건을 목표로 한다. |
| P1 · P0 이후 | 가용 로봇에 거리 등 단순 비용으로 자동 배정하고 작업 큐와 상태 전이를 관리한다. 양방향 Heartbeat, 로봇의 로컬 정지, 불확실한 점유 유지, 운영자 승인 복구를 추가한다. | 단절된 로봇의 점유 가능성이 있는 Zone에 추가 진입권을 발급하지 않는다. 정지와 복구를 실측하고 승인 전 자동 재출발 여부를 기록한다. |
| P2 · 선택 | 두 Nav2 계획 경로를 같은 지도에서 비교해 임시 Zone 후보를 찾는다. 경로 변경 시 후보를 갱신하고 고정 Zone과 대기시간·총 작업시간을 비교한다. | 중첩 후보를 지도나 로그에 표시한다. 시간이 부족하면 오프라인 경로 비교 시연으로 마칠 수 있다. |

범위를 줄일 때는 P2를 먼저 덜어내고, P1 자동 배정을 단순화한다. 관제 UI는 콘솔까지 줄일 수 있다. 고급 지도 UI, 영상 스트리밍, YOLO, 배터리 최적화, Open-RMF 전체 통합, MPC 구현은 원문 기본 범위에서 제외했다. [원문 §4](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.6pof2qrg7e10), [원문 §9](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.wys1zxozv9r7)

## [원문 요약] 일별 계획과 중단선

| 시점 | 목표와 중단선 |
| --- | --- |
| Day 1 | 로봇 네트워크와 좌표계를 확인하고 오전에 작업·상태·Zone 인터페이스를 합의한다. 기본 관제와 고정 Zone 예약·대기·해제를 연결한다. 종료까지 실물 2대 동시 주행이 불안정하면 실물 1대 + Mock 1대로 전환하고 실물 문제를 따로 해결한다. |
| Day 2 | 자동 배정과 통신 장애 대응을 구현한다. 실물 정지를 확인할 수 없으면 자동 주행 실험을 중단한다. |
| Day 3 | 여유가 있으면 경로 중첩 후보를 시연한다. 시간에 따라 오프라인 비교로 줄이거나 P2를 생략할 수 있다. |

[원문 §5](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.63398ssk3bn6), [원문 §8](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.a1hcp6gnine2), [원문 §9](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.wys1zxozv9r7)

## [원문 요약] 개발 참고자료

- 실습 환경, 맵 작성, Nav2, ROS 2 통신 자료는 팀에서 공유한 강의자료를 기준으로 확인한다. [원문 §11](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.9tr9gah48qhh)
- 장비와 패키지 확인에 사용하는 원문 링크다. [Pinky Pro 제품 정보](https://pinklab.art/pinky-pro/), [Pinky Pro ROS 2 코드](https://github.com/pinklab-art/pinky_pro)
- 작업 배정·교통관제 개념의 원문 참고 링크다. [Open-RMF 데모](https://github.com/open-rmf/rmf_demos), [MRTA 논문](https://doi.org/10.1177/0278364904045564), [CBS 논문](https://doi.org/10.1016/j.artint.2014.11.006)

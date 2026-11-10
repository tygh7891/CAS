# Pinky Fleet Coordinator 문서

**[원문 요약]** 3명이 ROS 2 기반으로 Pinky Pro 2대를 관제하는 3일 프로젝트다. 원문은 2026-11-09 기준 팀 논의용 제안서 v0.1이다. [원본 Google Docs](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?pli=1&tab=t.0#heading=h.8gdv5ip8wajs)

## 표기 기준

- **[원문 요약]** Google Docs 제안서에 있는 내용을 요약하거나 재배치한 부분이다. 해당 절의 링크를 붙였다.
- **[사용자 요청]** 사용자가 요청한 작업과 범위를 요약한 부분이다.
- **[문서 이력]** 이 Markdown 문서의 작성·수정·반영 기록이다.

**[문서 이력]** 2026-11-10에 Google Docs 제안서를 주제별 Markdown 문서로 정리했다.

## 문서 목록

| 문서 | 언제 보는가 |
| --- | --- |
| [00-PROJECT · 제안서 분석 및 3일 계획](00-PROJECT/PROJECT-PLAN.md) | 범위, 우선순위, 일별 완료 기준을 정할 때 |
| [01-DESIGN · 관제 구조 및 Zone 동작](01-DESIGN/FLEET-DESIGN.md) | 중앙 관제와 로봇의 인터페이스, 진입·해제 조건을 맞출 때 |
| [02-TESTING · 시연 및 시험 기록](02-TESTING/TEST-PLAN.md) | 시연 시나리오, 안전 조건, 평가 지표를 확인할 때 |
| [02-TESTING · 로컬 가상 시연](02-TESTING/LOCAL-DEMO.md) | 공유 지도와 가상 Worker로 FMS를 실행할 때 |
| [02-TESTING · 핑키프로 실물 연결 모드](02-TESTING/REAL-MODE.md) | 노트북에서 실물 ROS 2 연결을 읽기 전용으로 확인하거나 장비 설정을 준비할 때 |
| [03-COLLABORATION · 역할과 결정 기록](03-COLLABORATION/TEAM-LOG.md) | 원문의 역할 초안과 협의 항목을 확인할 때 |
| [03-COLLABORATION · 사용자 요청 기록](03-COLLABORATION/REQUEST-LOG.md) | 문서화 요청의 요약과 반영 내역을 확인할 때 |
| [04-ENGINEERING · FMS 팀 개발 기준](04-ENGINEERING/README.md) | 구현과 리뷰에 적용할 설계 패턴, 모듈화, DDD, Python 코딩 표준을 확인할 때 |
| [05-ROS2-LEARNING · ROS 2 실습과 참고 강의](05-ROS2-LEARNING/README.md) | 프로젝트 진행 사항을 확인하고 Gazebo 시연과 실물 읽기 전용 연결을 직접 재현할 때 |

# 역할과 결정 기록

[문서 홈](../README.md) · [사용자 요청 기록](REQUEST-LOG.md)

## [원문 요약] 프로젝트 인원과 역할

원문 개요의 팀 인원은 3명이고, §8의 역할 초안에는 A와 B가 명시돼 있다. [원문 개요](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.8gdv5ip8wajs), [원문 §8](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.a1hcp6gnine2)

| 구분 | 역할 |
| --- | --- |
| A · 중앙 FMS 및 관제 | 작업 큐, Zone 관리, 예약권·상태 머신, 작업 배정, 운영자 화면과 로그, KPI 집계 |
| B · Robot Agent 및 실물 통합 | 로봇 네트워크·네임스페이스·맵 정합, Nav2 Action 호출·취소, 위치·속도·Heartbeat 수집, 로컬 정지 점검 |
| 공동 작업 | Day 1 오전 인터페이스 합의, 통합·안전 시험, 역할 교차 검토, 발표 데모 |

## [원문 요약] 팀에서 정할 항목

| 협의 항목 | 팀 결정 |
| --- | --- |
| 실물 Pinky Pro 2대와 개발 PC의 확보 시점 | |
| 실습 맵, 고정 Zone 위치, 대기 위치 | |
| 관제 방식(PyQt / Flask / 콘솔) | PyQt. [FMS 팀 개발 기준](../04-ENGINEERING/README.md) |
| 담당 A 및 담당 B 배정 | |
| P0에서 빼거나 추가할 항목 | |
| P1 통신 장애·안전 정지 시험 가능 여부 | |
| P2 동적 Zone 구현 결정 시점 | |
| 최종 성공 기준(KPI 및 시험 횟수) | |

[원문 §10](https://docs.google.com/document/d/1vWgq_dIW6BwtLp2fPreUjuKNVwoWXNPH3rt5cHtMWDY/edit?tab=t.0#heading=h.63lvv6u4axpd)

## 변경 기록

| 구분 | 날짜 | 변경 내용 | 이유 | 우선순위 | 담당 | 승인 |
| --- | --- | --- | --- | --- | --- | --- |
| [원문 요약] | 2026-11-09 | 원문 제안서 v0.1 | 고정 Zone에서 시작해 장애 대응, 동적 Zone으로 확장 | P0~P2 | 원문 | 협의 전 |
| [문서 이력] | 2026-11-10 | 원문 제안서를 팀 공유용 Markdown으로 정리 | [REQ-001](REQUEST-LOG.md) 반영 | 문서화 | Codex | — |

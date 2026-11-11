# 검증 기록

검증일은 2026년 11월 12일이다. Mac Studio의 arm64 Python 3.12 환경에서 로컬 예제와 자료 구조를 확인했다.

| 확인한 항목 | 결과 |
|---|---|
| HTML 원본 | 바로 아래 37개(22·7·8)를 번호순으로 처리했다. 분석 전후의 SHA-256이 37/37 일치했다. |
| HTML 내용과 위치 | 슬라이드 1,800개에서 제목·텍스트·코드 요소를 추출했다. 화면 위주 강의에서 관련 이미지 75개를 선별해 OCR 결과를 검토했다. 인용한 슬라이드 번호는 HTML의 실제 페이지 표시와 대조했다. |
| 링크 | 강의 ID·실습 문서 링크와 실제 CAS 코드 위치를 확인했다. 로컬 링크 목록 37개 모두 이 Mac의 HTML 파일로 해석됐다. |
| Python·Bash | Python 파일을 구문 검사하고 Bash 스크립트와 문서 명령을 `bash -n`으로 검사했다. |
| Mac에서 실행한 예제 | 위치 JSON, 프레임 좌표 계산, 지도 셀과 목표 포즈 계산, Nav2 설정 사본 생성, 한 대 왕복과 두 대 통행권 로그, 로컬 HTTP 요청을 확인했다. HTTP 202·400·404도 확인했다. |
| CAS 기존 테스트 | 통행권 인계, 진입 관측 없이 해제하지 않기, 출발 쪽으로 후퇴할 때 예약 유지, 두 대 모드의 위치 보고 요구사항을 확인하는 4개가 통과했다. 테스트 클라이언트 의존성 경고 1개가 있었다. |

## 바로 다시 확인하기

CAS 저장소 루트에서 시작한다.

```bash
cd pinky_cas_fms/docs/05-ROS2-LEARNING
python3 00-START/source_links.py --check
python3 01-PYTHON-TERMINAL/pose_report.py
python3 03-PINKY/frame_math.py --yaw-deg -90
python3 04-SLAM-NAV2/map_goal.py
python3 05-FMS/fleet_lab.py --robots 2 --pause-first-exit
```

첫 명령은 원본이 있는 컴퓨터에서 실행한다. 다른 경로라면 `--root`로 세 강의 폴더의 상위 경로를 지정한다. Python·HTTP 예제의 관찰 기준은 각 실습에 있으며, Ubuntu에서 따라 할 실습은 [ROS 2](../02-ROS2/README.md), [Pinky](../03-PINKY/README.md), [SLAM·Nav2](../04-SLAM-NAV2/README.md)에 나눠 적었다.

## 강의실에서 확인할 항목

Mac 검증 환경에는 ROS 2 CLI가 없었다. 실제 ROS 2 노드 발견·DDS 도메인 격리·RViz·Gazebo·Nav2와 Pinky 센서 실측은 강의실에서 확인해야 한다. 관련 Python 예제는 구문 검사까지 수행했다. 실습 결과는 ‘받은 메시지’, ‘확인한 프레임’, ‘예상과 달랐던 동작’을 한 줄씩 기록하면 다시 복습할 때 사용할 수 있다.

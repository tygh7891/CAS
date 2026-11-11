# ROS 2부터 CAS FMS까지

목표는 관제 화면에서 작업을 등록한 뒤 **서버가 통행권을 결정하고, Worker가 Nav2에 이동·회전을 전달하는 흐름**을 직접 설명하는 것이다. 처음에는 Python과 화면 속 거북이로 같은 개념을 연습한다. 각 단계의 확인 문제를 통과한 뒤 다음 단계로 이동한다.

처음 시작할 때는 Ubuntu 24.04 노트북에서 Jazzy 설치 여부를 확인하고 기본 패키지와 학습 브랜치를 준비한다. [강의실 Ubuntu 설치와 환경 설정](00-START/UBUNTU.md)

| 순서 | 실습 | 어디서 | 통과 기준 |
|---|---|---|---|
| 01 | [터미널·Python·JSON](01-PYTHON-TERMINAL/README.md) | Ubuntu 터미널 | 입력 숫자 하나를 바꾸고 어느 출력이 달라질지 예측한다. |
| 02 | [ROS 2 노드·토픽·서비스·액션·도메인](02-ROS2/README.md) | 강의실 Ubuntu + Jazzy | 같은 도메인에서 수신을 확인하고, 서비스 응답과 액션 결과를 구분한다. |
| 03 | [Pinky 센서·TF·RViz](03-PINKY/README.md) | Ubuntu 좌표 계산·RViz, 준비된 Pinky 센서 읽기 | 프레임 기준으로 위치를 읽고, 위치·방향·라이다 거리의 차이를 설명한다. |
| 04 | [SLAM·위치 추정·Nav2](04-SLAM-NAV2/README.md) | Ubuntu 지도 읽기와 Gazebo 실습 | 지도·초기 위치·목표·실행 결과를 구분하고 목표 한 건을 관찰한다. |
| 05 | [한 대 왕복에서 두 대 통행권까지](05-FMS/README.md) | Ubuntu Python·HTTP 실습 | 통행권이 이탈 관측 뒤 넘어가는 이유를 로그와 실제 소스에서 설명한다. |

**지금 시작할 일**은 01의 `pose_report.py`를 실행하고 `x` 값을 바꿔보는 것이다. 강의실에서는 02의 통신 실습을 먼저 하고, 장비가 없을 때는 03의 좌표 계산, 04의 지도 읽기, 05의 로컬 모의 실습을 이어서 할 수 있다. 03~05의 선택 실습은 필수 흐름을 설명한 뒤에 살펴본다.

## 실행 경로

Ubuntu 준비 문서의 경로에 CAS를 받았다면 새 터미널마다 아래 명령으로 학습 폴더에 들어간다. 다른 경로에 CAS가 있다면 그 저장소의 `pinky_cas_fms/docs/05-ROS2-LEARNING`에 들어간다.

```bash
cd "$HOME/cas-study-ws/src/CAS/pinky_cas_fms/docs/05-ROS2-LEARNING"
pwd
/usr/bin/python3 --version
```

`pwd`에 학습 폴더가 표시되면 각 단계의 명령을 실행한다. 로컬 Python 예제는 표준 라이브러리를 사용한다. 출처 확인 도구는 Python 3.11 이상이 필요하며, 04단계의 Nav2 설정 사본 도구에는 PyYAML이 필요하다. ROS 예제는 Jazzy 환경을 불러온 뒤 Ubuntu의 시스템 Python으로 실행한다.

## 찾아보기

- [강의 원본 37개·슬라이드 번호와 열기 명령](00-START/SOURCE-INDEX.md)
- [영어 용어·어원·명령 이름 풀이](00-START/GLOSSARY.md)
- [검증 범위와 다시 확인하는 법](00-START/VERIFICATION.md)

실습 코드는 새로 작성한 학습용 예제다. 본문에 적힌 예상 출력은 관찰 기준이며 시간, 시퀀스, 좌표 등은 환경마다 달라질 수 있다.

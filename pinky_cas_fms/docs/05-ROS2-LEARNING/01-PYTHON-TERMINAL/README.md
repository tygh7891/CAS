# 01 · 터미널에서 Python 위치 보고서 실행하기

[학습 목차](../README.md) · [용어](../00-START/GLOSSARY.md) · [강의 출처표](../00-START/SOURCE-INDEX.md)

**목표** · 내가 있는 폴더를 확인하고, 명령으로 넣은 값이 함수와 JSON 출력까지 어떻게 전달되는지 설명한다.

## 강의에서 볼 곳

출처표의 **[ROS2-01](../00-START/SOURCE-INDEX.md#ros2-01) 25·30·35·43번**에서 Bash 시작 파일, 별칭, ROS 환경을 불러오는 명령을 본다. Python·JSON 부분은 뒤에서 FMS의 상태 응답을 읽기 위해 추가한 입문 실습이다. ROS 설치가 필요한 경우에는 ROS2-01의 설치 부분과 [Jazzy Ubuntu 설치 문서](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Installation/Ubuntu-Install-Debs.rst)를 함께 본다.

## Mac 또는 Ubuntu · 터미널 하나

[학습 폴더](../README.md#실행-경로)에서 아래 명령을 실행한다.

```bash
pwd
ls 01-PYTHON-TERMINAL
python3 01-PYTHON-TERMINAL/pose_report.py --help
python3 01-PYTHON-TERMINAL/pose_report.py --x 3 --y 4 --yaw-deg 90
```

예상 출력에서 `pose.x_m`은 `3.0`, `pose.y_m`은 `4.0`, `yaw_rad`는 약 `1.5708`, 원점까지의 거리는 `5.0`이다. 프로그램은 한 줄을 출력하고 종료한다.

`pwd`는 현재 작업 폴더를 알려준다. `python3`가 [pose_report.py](pose_report.py)를 읽으면 `main()`이 인수를 숫자로 바꿔 `make_report()`에 전달한다. 함수가 딕셔너리를 돌려주면 `json.dumps()`가 텍스트로 만든다. 서버의 위치 응답도 필드 이름과 단위를 보고 같은 방식으로 읽을 수 있다.

## 바꿔 보기

`x`만 0으로 바꾸면 원점까지의 거리가 4 m로 줄고 방향은 그대로다. 먼저 결과를 적은 뒤 실행해 확인한다. `--x hello`를 넣으면 숫자로 바꿀 수 없어 인수 오류가 표시된다.

- `pwd`는 *print working directory*, `cd`는 *change directory*다.
- `return`은 함수 호출자에게 값을 돌려준다. `print`는 사람이 보는 곳에 출력한다.
- `JSON`은 *JavaScript Object Notation*이다. 이 실습의 JSON 키는 예제 전용이다. 실제 FMS 상태의 `pose`는 `x`, `y`, `yaw`를 쓴다.

**통과 기준** · `--yaw-deg 0`으로 바꿨을 때 어떤 값만 달라질지 예측하고 설명한다. 강의실 터미널에서 `source /opt/ros/jazzy/setup.bash`를 실행한 뒤 `printenv ROS_DISTRO`가 `jazzy`를 보이면 [02 ROS 2 통신](../02-ROS2/README.md)으로 간다.

# 강의실 Ubuntu 노트북 준비

[학습 목차](../README.md) · [강의 출처표](SOURCE-INDEX.md)

Ubuntu 24.04 데스크톱과 ROS 2 Jazzy를 기준으로 한다. 노트북의 터미널을 Bash로 열고 아래 순서대로 진행한다.

## 1. 운영체제와 ROS 2 확인

```bash
. /etc/os-release
printf '%s (%s)\n' "$PRETTY_NAME" "$VERSION_CODENAME"
dpkg --print-architecture
test -r /opt/ros/jazzy/setup.bash && printf 'Jazzy 설치 경로 있음\n'
```

`Ubuntu 24.04`와 `noble`을 확인한다. Jazzy의 Ubuntu 패키지는 `amd64`와 `arm64`에 제공된다. [04단계의 CAS 시뮬레이션 빌드](../04-SLAM-NAV2/README.md#b--ubuntu에서-gazebo와-nav2-준비)는 `amd64` 노트북을 기준으로 설명한다. 다른 Ubuntu 버전이면 노트북의 배포판에 맞는 ROS 2 설치 절차를 먼저 확인한다. `Jazzy 설치 경로 있음`이 나오면 2번에서 필요한 패키지만 확인한다. [ROS 2 Jazzy Ubuntu 설치 문서](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Installation/Ubuntu-Install-Debs.rst)

### ROS 2 APT 저장소 등록 · 처음 설치할 때

강의실 노트북에 ROS 2 APT 저장소가 등록돼 있으면 이 부분을 건너뛴다. `apt-cache policy ros-jazzy-desktop`으로 설치 후보가 표시되는지 확인할 수 있다. 저장소를 처음 등록할 때 Ubuntu 24.04에서 아래를 실행한다. [ROS 2 APT 저장소 공식 절차](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Installation/_Apt-Repositories.rst)

```bash
sudo apt update
sudo apt install ca-certificates curl python3 software-properties-common
sudo add-apt-repository -y universe
```

```bash
ROS_APT_TAG="$(curl -fsSL \
  https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest |
  /usr/bin/python3 -c 'import json, sys; print(json.load(sys.stdin)["tag_name"])')"
ROS_APT_DEB="$(mktemp --suffix=.deb)"
test -n "$ROS_APT_TAG" && \
  curl -fL -o "$ROS_APT_DEB" \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_TAG}/ros2-apt-source_${ROS_APT_TAG}.noble_all.deb" && \
  sudo dpkg -i "$ROS_APT_DEB" && sudo apt update
apt-cache policy ros-jazzy-desktop
```

설치 후보에 버전 번호가 표시되면 2번으로 간다.

## 2. 기본 실습 패키지 설치

```bash
sudo apt update
sudo apt install git curl python3 ros-jazzy-desktop \
  ros-jazzy-turtlesim ros-jazzy-rqt-graph
source /opt/ros/jazzy/setup.bash
printenv ROS_DISTRO
/usr/bin/python3 --version
/usr/bin/python3 -c 'import rclpy, std_msgs.msg, sensor_msgs.msg'
ros2 pkg executables turtlesim
ros2 pkg executables tf2_ros
ros2 pkg executables rviz2
```

`ROS_DISTRO`는 `jazzy`여야 한다. Python 가져오기 명령은 성공하면 출력 없이 끝난다. 실행 항목 목록에서 `turtlesim_node`, `static_transform_publisher`, `tf2_echo`, `rviz2`를 확인한다. Gazebo와 Nav2 및 빌드 도구는 [04단계 준비](../04-SLAM-NAV2/README.md#b--ubuntu에서-gazebo와-nav2-준비)에서 설치한다. [Jazzy turtlesim 설치와 확인](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Beginner-CLI-Tools/Introducing-Turtlesim/Introducing-Turtlesim.rst)

## 3. 학습 브랜치 가져오기

아래 문서에서는 `~/cas-study-ws/src/CAS`를 CAS 경로로 사용한다. 다른 경로에 이미 있다면 기존 저장소를 사용하고 이후 명령의 경로를 맞춘다.

```bash
# CAS가 아직 없을 때
mkdir -p "$HOME/cas-study-ws/src"
git clone --branch feature/pinky_cas_fms \
  https://github.com/tygh7891/CAS.git "$HOME/cas-study-ws/src/CAS"
```

이미 CAS가 있다면 그 저장소에서 아래를 실행한다. 기존 변경이 있으면 먼저 `git status`에서 내용을 확인한다.

```bash
git status --short --branch
git fetch origin
git switch feature/pinky_cas_fms
git pull --ff-only origin feature/pinky_cas_fms
```

## 4. 새 터미널을 열 때

각 실습의 터미널마다 먼저 학습 폴더로 이동한다. `pwd`의 마지막 폴더가 `05-ROS2-LEARNING`인지 확인한다. 이 위치에서 단계별 명령을 실행한다.

```bash
cd "$HOME/cas-study-ws/src/CAS/pinky_cas_fms/docs/05-ROS2-LEARNING"
pwd
```

02단계의 토픽 실습, 03단계의 정적 TF, 04단계의 Gazebo는 같은 노트북에서 진행한다. 아래 스크립트는 현재 터미널에 Jazzy를 불러오고 DDS 검색을 같은 컴퓨터로 제한한다. 통신을 비교할 때는 02단계에서 터미널 한 곳에만 `52`를 사용한다.

```bash
source 02-ROS2/lab_env.bash 51
printenv ROS_DISTRO ROS_DOMAIN_ID ROS_AUTOMATIC_DISCOVERY_RANGE
```

세 줄에 `jazzy`, `51`, `LOCALHOST`가 표시된다. 실물 Pinky 센서를 읽을 때는 03단계에서 로봇과 같은 도메인으로 새 터미널을 준비한다. ROS 예제는 `/usr/bin/python3`로 실행한다. [Jazzy DDS 검색 범위](https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst)

첫 실행은 [01 Python 위치 보고서](../01-PYTHON-TERMINAL/README.md)부터 시작한다. 원본 강의를 Ubuntu에도 갖고 있다면 `source_links.py --root`에 세 강의 폴더의 상위 경로를 지정할 수 있다. [원본 열기](SOURCE-INDEX.md)

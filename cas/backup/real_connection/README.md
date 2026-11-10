# C. 1차 목표 실물 연결 준비

B6 종단 시나리오는 사용자 GUI 관찰 기준 두 로봇 모두 작업 완료를 확인했습니다.
사용자 요청에 따라 추가 B7 예외 주입 시험은 보류하고 C 단계로 진행합니다.
두 실물 로봇은 사용자 확인 기준 모두 시험에 사용할 수 있습니다.
REAL_NAV2 연결기는 아직 미구현이며 domain84 시뮬레이션 설정을 실물에 재사용하지 않습니다.

## C2/C3 읽기 전용 현황 수집

[PC 터미널]에서 아래 명령을 실행합니다. 기존 시뮬레이션 관제 GUI는 종료해 모드를 구분하세요.

```bash
bash ~/CAS/cas/backup/real_connection/check_robots.sh
```

기존 합의의 domain14=robot_1, domain30=robot_2를 임시 기준으로 각각 조회합니다.
명령/속도 publisher나 Action client를 만들지 않습니다. 노드/토픽/Action 서버·속도 명령 발행자,
odom/scan/TF/지도 메타데이터 및 use_sim_time/프레임/지도 경로 파라미터를 읽습니다.
GetParameters 서비스만 호출하며 Goal·Spin·Cancel·설정 변경은 하지 않습니다.
미발견은 연결/구동 점검이 필요하다는 뜻이며 실물 식별·주행 준비 완료를 뜻하지 않습니다.
로봇·PC 시계가 다르면 pc_wall_minus_source_s도 달라지므로 단독으로 통신 지연을 판정하지 않습니다.
지도 메시지의 source stamp는 마지막 지도 갱신 시각이며 센서 freshness로 해석하지 않습니다.

로그는 이 폴더 logs/에 로컬 저장되며 Git에서 제외합니다. 비밀번호는 저장하지 않습니다.
이 결과로 C1의 로봇별 domain/토픽/Action/프레임/use_sim_time=false 프로필을 확정한 뒤
실물용 Worker/상태·제어 연결기를 구현합니다. 실물 지도/초기 위치/몸체 크기/정지 방법은
현재 장비와 팀원 설정으로 확인해야 합니다. 시뮬레이션 후보를 그대로 실물 목표로 쓰지 않습니다.

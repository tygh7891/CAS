"""한 대 왕복과 두 대 통행권 인계를 로그로 보는 모의 실습."""

import argparse
from collections import deque


class SharedZone:
    def __init__(self):
        self.waiting = deque()
        self.owner = None
        self.entered = False

    def request(self, robot, leg):
        self.waiting.append((robot, leg))

    def grant(self):
        # 현재 예약이 있는 동안에는 FIFO의 다음 요청을 꺼내지 않는다.
        if self.owner is not None or not self.waiting:
            return None
        self.owner = self.waiting.popleft()
        self.entered = False
        return self.owner

    def see_entry(self, robot, leg):
        if self.owner == (robot, leg):
            self.entered = True

    def see_exit(self, robot, leg, *, outside_on_goal_side):
        # 예약 소유자, 실제 진입, 목적지 쪽 이탈이 모두 확인돼야 권한을 푼다.
        if self.owner != (robot, leg) or not self.entered or not outside_on_goal_side:
            return False
        self.owner = None
        self.entered = False
        return True


def simulate(robot_count, pause_first_exit):
    zone = SharedZone()
    for number in range(1, robot_count + 1):
        robot = f"robot_{number}"
        zone.request(robot, "OUTBOUND")
        yield f"WAIT {robot} OUTBOUND"

    while zone.waiting:
        robot, leg = zone.grant()
        yield f"GRANT {robot} {leg}"
        zone.see_entry(robot, leg)
        yield f"ENTER {robot} {leg}"

        if pause_first_exit and (robot, leg) == ("robot_1", "OUTBOUND"):
            # 이번 차례에서는 이탈 보고가 없다. 다음 요청을 기다리게 한다.
            yield f"HOLD {robot} {leg}: 이탈 미확인"

        if not zone.see_exit(robot, leg, outside_on_goal_side=True):
            raise RuntimeError("이탈 확인 실패")
        yield f"RELEASE {robot} {leg}"
        if leg == "OUTBOUND":
            yield f"SPIN {robot}"
            zone.request(robot, "RETURN")
            yield f"WAIT {robot} RETURN"
        else:
            yield f"COMPLETED {robot}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robots", type=int, choices=(1, 2), default=1)
    parser.add_argument("--pause-first-exit", action="store_true")
    args = parser.parse_args()
    for event in simulate(args.robots, args.pause_first_exit):
        print(event)


if __name__ == "__main__":
    main()

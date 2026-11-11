from concurrent.futures import ThreadPoolExecutor
from math import ceil, floor, hypot, remainder, tau
from typing import Any

import pytest
from PyQt5.QtGui import QImage

from fms_geometry import Pose
from fms_settings import DemoPreset, Scenario, load_scenario
from mock_worker import MockRobot
from pinky_fms_server.application import FleetService
from pinky_fms_server.domain import Zone
from pinky_fms_server.http import create_app


class A1Demo:
    def __init__(
        self,
        *,
        demo_mode: bool = False,
        real_mode: bool = False,
        motion_enabled: bool = True,
    ) -> None:
        self.now = 10.0
        self.scenario = load_scenario()
        self.service = FleetService(
            self.scenario,
            lambda: self.now,
            demo_mode=demo_mode,
            real_mode=real_mode,
            motion_enabled=motion_enabled,
        )
        self.client = create_app(self.service).test_client()
        self.robots = {
            robot_id: MockRobot(
                route.start, self.scenario.zone, self.scenario.robot_radius_m
            )
            for robot_id, route in self.scenario.routes.items()
        }

    def tick(self, skip: str | None = None, *, slow: str | None = None) -> None:
        self.now += 0.1
        for robot_id, robot in self.robots.items():
            if robot_id == skip:
                continue
            robot.advance(0.025 if robot_id == slow else 0.1)
            response = self.client.post(
                f"/api/workers/{robot_id}/poll", json=robot.observe(self.now)
            )
            assert response.status_code == 200, response.get_json()
            robot.receive_poll(response.get_json())

    def start(self) -> str:
        self.tick()
        response = self.client.post("/api/run", json={"request_id": "start-a1"})
        assert response.status_code == 202
        return response.get_json()["run_id"]

    def status(self) -> dict[str, Any]:
        return self.client.get("/api/status").get_json()

    def wait_for_first_crossing(self) -> str:
        for _ in range(60):
            self.tick()
            owner = self.status()["zone_owner"]
            if owner and self.service.zone.overlaps(self.robots[owner].pose):
                return owner
        raise AssertionError("A robot did not enter the shared Zone")

    def wait_for_completion(self) -> dict[str, Any]:
        for _ in range(200):
            self.tick()
            state = self.status()
            if all(robot["task_state"] == "SUCCEEDED" for robot in state["robots"]):
                return state
        raise AssertionError("The A1 scenario did not complete")


def test_zone_grants_once_and_releases_only_after_entry_and_exit() -> None:
    scenario = load_scenario()
    zone = Zone(scenario.zone, scenario.robot_radius_m)
    first_route = scenario.routes["robot_1"]
    zone.request("robot_1")
    zone.request("robot_1")
    zone.request("robot_2")
    first = zone.grant()
    assert first is not None and first.robot_id == "robot_1"
    assert zone.grant() is None
    assert not zone.release(first.reservation_id, first_route.exit)
    zone.observe(first.reservation_id, Pose(0.23, -0.35, 0))
    assert not zone.release(first.reservation_id, Pose(0.23, -0.35, 0))
    assert zone.release(first.reservation_id, first_route.exit)
    second = zone.grant()
    assert second is not None and second.robot_id == "robot_2"
    assert not zone.release(first.reservation_id, first_route.exit, canceled=True)


def test_real_read_only_mode_reports_positions_and_rejects_start() -> None:
    demo = A1Demo(real_mode=True, motion_enabled=False)
    demo.tick()
    state = demo.status()
    assert state["real_mode"] and not state["motion_enabled"]
    assert all(robot["connected"] and robot["pose"] for robot in state["robots"])
    assert not state["can_start"]
    assert (
        demo.client.post("/api/run", json={"request_id": "read-only"}).status_code
        == 409
    )
    assert demo.status()["run_id"] is None


def test_battery_and_sensors_can_be_reported_before_the_first_pose() -> None:
    demo = A1Demo(real_mode=True, motion_enabled=False)
    report = {
        "session_id": "read-only",
        "telemetry_only": True,
        "telemetry": {
            "at_s": demo.now,
            "scan_at_s": demo.now,
            "odom_at_s": demo.now,
            "percent": {"value": 78.0, "at_s": demo.now},
            "voltage": {"value": 7.8, "at_s": demo.now},
        },
    }
    path = "/api/workers/robot_1/poll"
    reply = demo.client.post(path, json=report)
    assert reply.get_json()["command"] is None
    robot = demo.status()["robots"][0]
    assert robot["pose"] is None and not robot["connected"]
    assert robot["scan_received"] and robot["odom_received"]
    assert robot["battery_percent"] == 78.0 and robot["battery_voltage"] == 7.8
    assert not robot["battery_stale"] and not demo.status()["can_start"]

    demo.now += 16
    report["telemetry"]["at_s"] = demo.now
    assert demo.client.post(path, json=report).status_code == 200
    robot = demo.status()["robots"][0]
    assert robot["battery_stale"] and robot["battery_age_s"] == 16
    assert not robot["scan_received"] and not robot["odom_received"]


@pytest.mark.parametrize("preset", tuple(DemoPreset))
def test_demo_preset_resets_and_preserves_exclusive_access(preset: DemoPreset) -> None:
    demo = A1Demo(demo_mode=True)
    demo.tick()
    response = demo.client.post(
        "/api/run", json={"request_id": "preset", "preset": preset}
    )
    assert response.status_code == 202
    assert demo.status()["resetting"]
    blocked_during_dropout = False
    terminal = "CANCELED" if preset == DemoPreset.CANCEL else "SUCCEEDED"
    for _ in range(300):
        demo.tick()
        state = demo.status()
        assert (
            sum(
                demo.service.zone.overlaps(robot.pose) for robot in demo.robots.values()
            )
            <= 1
        )
        if state["paused_robot_id"]:
            assert state["paused_robot_id"] == state["zone_owner"]
            assert state["zone_blocked"] and len(state["zone_waiting"]) == 1
            blocked_during_dropout = True
        if all(robot["task_state"] == terminal for robot in state["robots"]):
            break
    else:
        pytest.fail(f"{preset} did not reach {terminal}")
    events = [event["kind"] for event in state["events"]]
    assert events[:3] == ["scenario", "resetting", "depart"]
    assert state["can_start"]
    if preset == DemoPreset.CANCEL:
        assert state["zone_blocked"] and events.count("zone_granted") == 1
    else:
        crossings = 4 if preset == DemoPreset.NORMAL else 2
        assert not state["zone_owner"] and events.count("zone_granted") == crossings
    if preset == DemoPreset.DROPOUT:
        assert blocked_during_dropout
        second_grant = events.index("zone_granted", events.index("zone_granted") + 1)
        assert events.index("location_resumed") < second_grant


@pytest.mark.parametrize("staggered", (False, True))
def test_round_trip_keeps_the_leading_goal_and_restores_start(staggered: bool) -> None:
    demo = A1Demo(demo_mode=True)
    demo.tick()
    assert (
        demo.client.post(
            "/api/run", json={"request_id": "round-trip", "preset": DemoPreset.NORMAL}
        ).status_code
        == 202
    )
    leader = None
    leader_goal = None
    leader_cleared = False
    waiting = set()
    for _ in range(350):
        demo.tick(slow="robot_2" if staggered and not leader_cleared else None)
        state = demo.status()
        owner = state["zone_owner"]
        if not leader_cleared:
            if leader is None and owner:
                leader = owner
                leader_goal = demo.robots[leader].command_id
                assert demo.robots[leader].motion is not None
            if leader and owner == leader:
                robot = demo.robots[leader]
                assert robot.command_id == leader_goal and not robot.held
            elif leader:
                leader_cleared = True
            waiting.update(state["zone_waiting"])
        for robot_id, robot in demo.robots.items():
            if demo.service.zone.overlaps(robot.pose):
                assert owner == robot_id
        if all(robot["task_state"] == "SUCCEEDED" for robot in state["robots"]):
            break
    else:
        pytest.fail("Round trip did not complete")

    assert leader is not None and leader_cleared
    if staggered:
        assert leader == "robot_1" and not waiting
    else:
        assert waiting == set(demo.robots) - {leader}
    for robot_id, robot in demo.robots.items():
        start = demo.scenario.routes[robot_id].start
        assert robot.motion is None and robot.pose.distance_to(start) < 1e-9
        assert abs(remainder(robot.pose.yaw_rad - start.yaw_rad, tau)) < 1e-9


def test_round_trip_waits_for_revocation_acknowledgement(monkeypatch) -> None:
    demo = A1Demo(demo_mode=True)
    demo.tick()
    assert (
        demo.client.post(
            "/api/run", json={"request_id": "round-trip", "preset": DemoPreset.NORMAL}
        ).status_code
        == 202
    )
    leader = demo.wait_for_first_crossing()
    robot = demo.robots[leader]
    receive = robot.receive_poll
    blocked = False

    def delay_revocation(reply: dict[str, Any]) -> None:
        nonlocal blocked
        command = reply["command"]
        if (
            command
            and command["command_id"] == robot.command_id
            and not command["reservation_id"]
        ):
            blocked = True
            return
        receive(reply)

    monkeypatch.setattr(robot, "receive_poll", delay_revocation)
    for _ in range(60):
        demo.tick()
        if blocked:
            break
    assert blocked and not demo.service.zone.overlaps(robot.pose)
    for _ in range(5):
        demo.tick()
        assert demo.status()["zone_owner"] == leader

    monkeypatch.setattr(robot, "receive_poll", receive)
    demo.tick()
    assert demo.status()["zone_owner"] == leader
    demo.tick()
    assert demo.status()["zone_owner"] in (set(demo.robots) - {leader})


def test_real_run_requires_verified_worker_readiness_and_start_heading() -> None:
    demo = A1Demo(real_mode=True)
    demo.tick()
    robot = demo.robots["robot_1"]
    demo.now += 0.1
    report = robot.observe(demo.now)
    report.update(ready=False, detail="map mismatch")
    response = demo.client.post("/api/workers/robot_1/poll", json=report)
    assert response.status_code == 200
    assert demo.status()["robots"][0]["detail"] == "map mismatch"
    assert not demo.status()["can_start"]

    start = demo.scenario.routes["robot_1"].start
    robot.pose = Pose(start.x_m, start.y_m, start.yaw_rad + 0.3)
    demo.tick()
    assert not demo.status()["can_start"]
    robot.pose = start
    demo.tick()
    assert demo.status()["can_start"]


def test_real_mode_rejects_action_success_away_from_the_wait_point() -> None:
    demo = A1Demo(real_mode=True)
    demo.start()
    demo.tick()
    robot = demo.robots["robot_1"]
    robot.result = "SUCCEEDED"
    robot.motion = None
    demo.tick()
    state = demo.status()
    assert state["robots"][0]["error_code"] == "WAYPOINT_NOT_REACHED"
    assert state["robots"][0]["task_state"] == "FAILED"
    assert state["zone_owner"] is None


def test_a1_http_scenario_serializes_crossing_and_waits_for_spin() -> None:
    demo = A1Demo()
    run_id = demo.start()
    replay = demo.client.post("/api/run", json={"request_id": "start-a1"})
    assert replay.status_code == 202 and replay.get_json()["run_id"] == run_id
    assert demo.client.post("/api/run", json={"request_id": "extra"}).status_code == 409
    owners = set()
    seen_waiting = False
    spinning = set()
    for _ in range(200):
        demo.tick()
        state = demo.status()
        if state["zone_owner"]:
            owners.add(state["zone_owner"])
        inside = [
            robot_id
            for robot_id, robot in demo.robots.items()
            if demo.service.zone.overlaps(robot.pose)
        ]
        assert len(inside) <= 1
        if inside:
            assert state["zone_owner"] == inside[0]
        seen_waiting |= bool(state["zone_waiting"])
        for robot in state["robots"]:
            if robot["phase"] == "SPINNING":
                spinning.add(robot["robot_id"])
                assert robot["task_state"] == "RUNNING"
            if robot["task_state"] == "SUCCEEDED":
                assert robot["robot_id"] in spinning
                assert demo.robots[robot["robot_id"]].motion is None
        if all(robot["task_state"] == "SUCCEEDED" for robot in state["robots"]):
            assert owners == spinning == set(demo.robots)
            assert seen_waiting and state["zone_owner"] is None
            return
    raise AssertionError("The A1 scenario did not complete")


def test_concurrent_arrivals_have_only_one_crossing_command() -> None:
    demo = A1Demo()
    demo.start()
    demo.tick()
    demo.now += 0.1
    reports = {}
    for robot_id, robot in demo.robots.items():
        robot.pose = demo.scenario.routes[robot_id].wait
        robot.motion = None
        robot.result = "SUCCEEDED"
        reports[robot_id] = robot.observe(demo.now)
    app = demo.client.application

    def arrive(robot_id: str) -> dict[str, Any] | None:
        with app.test_client() as client:
            response = client.post(
                f"/api/workers/{robot_id}/poll", json=reports[robot_id]
            )
            assert response.status_code == 200
            return response.get_json()["command"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        commands = [command for command in pool.map(arrive, reports) if command]
    assert len(commands) == 1 and commands[0]["reservation_id"]
    state = demo.status()
    assert len(state["zone_waiting"]) == 1
    assert state["zone_owner"] != state["zone_waiting"][0]


def test_demo_restarts_only_after_both_robots_confirm_their_start() -> None:
    demo = A1Demo(demo_mode=True)
    first_run = demo.start()
    assert demo.wait_for_completion()["can_start"]
    second_robot_end_pose = demo.robots["robot_2"].pose
    payload = {"request_id": "restart-a1"}
    response = demo.client.post("/api/run", json=payload)
    assert response.status_code == 202
    second_run = response.get_json()["run_id"]
    assert second_run != first_run
    assert demo.client.post("/api/run", json=payload).get_json()["run_id"] == second_run
    for _ in range(2):
        demo.tick(skip="robot_2")
    state = demo.status()
    assert state["resetting"] and not state["can_start"]
    assert demo.robots["robot_1"].pose == demo.scenario.routes["robot_1"].start
    assert demo.robots["robot_1"].motion is None
    assert demo.robots["robot_2"].pose == second_robot_end_pose
    demo.tick()
    demo.tick()
    state = demo.status()
    assert not state["resetting"]
    assert all(robot["phase"] == "TO_WAIT" for robot in state["robots"])
    assert all(
        robot.pose == demo.scenario.routes[rid].start
        for rid, robot in demo.robots.items()
    )
    assert demo.wait_for_completion()["run_id"] == second_run


def test_demo_allows_retry_after_a_reset_failure() -> None:
    demo = A1Demo(demo_mode=True)
    first_run = demo.start()
    demo.wait_for_completion()
    assert demo.client.post("/api/run", json={"request_id": "reset"}).status_code == 202
    demo.tick()
    demo.robots["robot_1"].result = "FAILED"
    demo.tick()
    state = demo.status()
    assert state["reset_failed"] and state["can_start"] and not state["resetting"]
    assert all(robot["task_id"].startswith(first_run) for robot in state["robots"])
    response = demo.client.post("/api/run", json={"request_id": "reset-retry"})
    assert response.status_code == 202
    demo.tick()
    demo.tick()
    state = demo.status()
    assert not state["reset_failed"] and not state["resetting"]
    assert all(robot["phase"] == "TO_WAIT" for robot in state["robots"])


def test_stale_report_cannot_clear_zone_or_refresh_pose() -> None:
    demo = A1Demo()
    demo.start()
    owner = demo.wait_for_first_crossing()
    last_pose = demo.robots[owner].observe(demo.now)
    for _ in range(15):
        demo.tick(skip=owner)
    response = demo.client.post(f"/api/workers/{owner}/poll", json=last_pose)
    assert response.status_code == 200
    state = demo.status()
    assert state["zone_owner"] == owner and state["zone_blocked"]
    assert state["zone_waiting"] == [robot for robot in demo.robots if robot != owner]
    assert not next(robot for robot in state["robots"] if robot["robot_id"] == owner)[
        "connected"
    ]


def test_demo_location_pause_keeps_reservation_until_fresh_exit() -> None:
    demo = A1Demo(demo_mode=True)
    demo.start()
    owner = demo.wait_for_first_crossing()
    waiting = next(robot_id for robot_id in demo.robots if robot_id != owner)
    assert demo.status()["location_pause_target"] == owner
    path = "/api/demo/location-reporting"
    assert (
        demo.client.post(path, json={"robot_id": waiting, "paused": True}).status_code
        == 409
    )
    assert (
        demo.client.post(path, json={"robot_id": owner, "paused": True}).status_code
        == 200
    )
    last_observation = demo.service.observations[owner]
    for _ in range(50):
        demo.tick()
    assert demo.robots[owner].location_paused
    assert demo.robots[owner].pose.distance_to(demo.scenario.routes[owner].exit) < 0.02
    assert demo.service.observations[owner] == last_observation
    state = demo.status()
    assert state["zone_owner"] == owner and state["zone_blocked"]
    assert state["zone_waiting"] == [waiting]
    assert (
        demo.client.post(path, json={"robot_id": owner, "paused": False}).status_code
        == 200
    )
    demo.tick()
    state = demo.status()
    assert state["zone_owner"] == owner and state["zone_blocked"]
    assert not demo.robots[owner].location_paused
    demo.tick()
    state = demo.status()
    assert state["zone_owner"] == waiting and not state["zone_blocked"]
    assert all(
        r["task_state"] == "SUCCEEDED" for r in demo.wait_for_completion()["robots"]
    )


def test_worker_can_receive_cancel_while_location_reporting_is_paused() -> None:
    demo = A1Demo(demo_mode=True)
    run_id = demo.start()
    owner = demo.wait_for_first_crossing()
    path = "/api/demo/location-reporting"
    assert (
        demo.client.post(path, json={"robot_id": owner, "paused": True}).status_code
        == 200
    )
    demo.tick()
    cancel = {"run_id": run_id, "request_id": "cancel-paused"}
    assert demo.client.post("/api/cancel", json=cancel).status_code == 202
    demo.tick()
    assert demo.robots[owner].result == "CANCELED" and demo.robots[owner].motion is None
    state = demo.status()
    assert state["zone_owner"] == owner and state["zone_blocked"]
    assert (
        next(r for r in state["robots"] if r["robot_id"] == owner)["task_state"]
        == "CANCELING"
    )
    assert (
        demo.client.post(path, json={"robot_id": owner, "paused": False}).status_code
        == 200
    )
    demo.tick()
    demo.tick()
    assert demo.status()["zone_owner"] == owner
    assert all(r["task_state"] == "CANCELED" for r in demo.status()["robots"])


def test_cancel_stops_both_robots_and_preserves_occupied_zone() -> None:
    demo = A1Demo()
    run_id = demo.start()
    owner = demo.wait_for_first_crossing()
    payload = {"run_id": run_id, "request_id": "cancel-a1"}
    assert demo.client.post("/api/cancel", json=payload).status_code == 202
    assert all(robot["task_state"] == "CANCELING" for robot in demo.status()["robots"])
    demo.tick()
    demo.tick()
    assert demo.client.post("/api/cancel", json=payload).status_code == 202
    state = demo.status()
    assert all(robot["task_state"] == "CANCELED" for robot in state["robots"])
    assert state["zone_owner"] == owner and state["zone_blocked"]
    assert not state["can_start"]


def test_mock_restart_clears_canceled_reservation_after_reset_confirmation() -> None:
    demo = A1Demo(demo_mode=True)
    run_id = demo.start()
    owner = demo.wait_for_first_crossing()
    payload = {"run_id": run_id, "request_id": "cancel-a1"}
    assert demo.client.post("/api/cancel", json=payload).status_code == 202
    demo.tick()
    demo.tick()
    assert demo.status()["zone_owner"] == owner
    response = demo.client.post("/api/run", json={"request_id": "restart-canceled"})
    assert response.status_code == 202
    demo.tick(skip=owner)
    demo.tick(skip=owner)
    assert demo.status()["zone_owner"] == owner
    assert demo.status()["resetting"]
    demo.tick()
    demo.tick()
    assert demo.status()["zone_owner"] is None
    assert not demo.status()["resetting"]


def test_http_validates_requests_and_worker_identity() -> None:
    demo = A1Demo()
    assert demo.client.post("/api/run", json={}).status_code == 400
    assert demo.client.post("/api/workers/unknown/poll", json={}).status_code == 404
    demo.tick()
    pose = demo.robots["robot_1"].observe(demo.now)
    pose["session_id"] = "other-worker"
    assert demo.client.post("/api/workers/robot_1/poll", json=pose).status_code == 409


def _check_map_routes(scenario: Scenario) -> None:
    world = QImage(str(scenario.world.image))
    mask = QImage(str(scenario.keepout.image))
    assert not world.isNull() and world.size() == mask.size()
    res = scenario.world.resolution
    origin_x, origin_y, _ = scenario.world.origin
    radius = scenario.robot_radius_m / res
    for route in scenario.routes.values():
        poses = (route.start, route.wait, route.exit, route.goal)
        for start, end in zip(poses, poses[1:]):
            samples = ceil(start.distance_to(end) / (res / 4))
            for i in range(samples + 1):
                ratio = i / samples
                x = (start.x_m + (end.x_m - start.x_m) * ratio - origin_x) / res
                y = (
                    mask.height()
                    - (start.y_m + (end.y_m - start.y_m) * ratio - origin_y) / res
                )
                for row in range(floor(y - radius), ceil(y + radius)):
                    for col in range(floor(x - radius), ceil(x + radius)):
                        if hypot(col + 0.5 - x, row + 0.5 - y) <= radius:
                            assert mask.valid(col, row)
                            assert mask.pixelColor(col, row).red() == 255
                            assert world.pixelColor(col, row).red() == 254


def test_demo_routes_stay_inside_the_shared_map_mask() -> None:
    _check_map_routes(load_scenario())

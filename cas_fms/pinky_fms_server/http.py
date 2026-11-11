import argparse
from dataclasses import asdict
from math import isfinite
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request

from fms_geometry import Pose
from fms_settings import DEFAULT_SCENARIO, DemoPreset, load_scenario
from pinky_fms_server.application import (
    Conflict,
    FleetService,
    Observation,
    Reading,
    Telemetry,
)
from pinky_fms_server.domain import Result


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("Expected a nonempty string of at most 128 characters")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError("Expected a finite JSON number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError("Expected a finite JSON number") from error
    if not isfinite(number):
        raise ValueError("Expected a finite JSON number")
    return number


def _observation(data: dict[str, Any], session_id: str) -> Observation:
    pose = _object(data.get("pose"))
    sequence = data.get("sequence")
    stopped = data.get("stopped")
    ready = data.get("ready", True)
    detail = data.get("detail", "")
    observed_at_s = _number(data.get("observed_at_s"))
    if type(sequence) is not int or sequence < 0 or observed_at_s < 0:
        raise ValueError("Expected a nonnegative sequence and observation time")
    if type(stopped) is not bool:
        raise ValueError("Expected a stopped flag")
    if type(ready) is not bool or not isinstance(detail, str) or len(detail) > 128:
        raise ValueError("Invalid worker readiness")
    command_id = data.get("command_id")
    result = data.get("result")
    reservation_id = data.get("reservation_id")
    if (command_id is None) != (result is None):
        raise ValueError("Command ID and result must be provided together")
    return Observation(
        session_id,
        sequence,
        observed_at_s,
        Pose(*(_number(pose.get(axis)) for axis in ("x_m", "y_m", "yaw_rad"))),
        stopped,
        _text(command_id) if command_id is not None else None,
        Result(result) if result is not None else None,
        ready,
        detail,
        _text(reservation_id) if reservation_id is not None else None,
    )


def _telemetry(data: dict[str, Any]) -> Telemetry:
    sent_at_s = _number(data.get("at_s"))
    if sent_at_s < 0:
        raise ValueError("Invalid telemetry time")

    def timestamp(value: object) -> float | None:
        if value is None:
            return None
        stamp = _number(value)
        if not 0 <= stamp <= sent_at_s:
            raise ValueError("Invalid sample time")
        return stamp

    def reading(value: object, maximum: float) -> Reading | None:
        if value is None:
            return None
        sample = _object(value)
        amount = _number(sample.get("value"))
        stamp = timestamp(sample.get("at_s"))
        if not 0 <= amount <= maximum or stamp is None:
            raise ValueError("Invalid battery reading")
        return Reading(amount, stamp)

    return Telemetry(
        sent_at_s,
        timestamp(data.get("scan_at_s")),
        timestamp(data.get("odom_at_s")),
        reading(data.get("percent"), 100),
        reading(data.get("voltage"), 100),
    )


def create_app(service: FleetService) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4096

    @app.errorhandler(ValueError)
    def invalid_request(error: ValueError) -> tuple[Response, int]:
        return jsonify(error=str(error)), 400

    @app.errorhandler(Conflict)
    def conflict(error: Conflict) -> tuple[Response, int]:
        return jsonify(error=str(error)), 409

    @app.get("/api/status")
    def status() -> Response:
        return jsonify(service.status())

    @app.post("/api/run")
    def start() -> tuple[Response, int]:
        data = _object(request.get_json(silent=True))
        preset = DemoPreset(_text(data["preset"])) if "preset" in data else None
        run_id = service.start(_text(data.get("request_id")), preset)
        return jsonify(run_id=run_id, result="ACCEPTED"), 202

    @app.post("/api/cancel")
    def cancel() -> tuple[Response, int]:
        data = _object(request.get_json(silent=True))
        service.cancel(_text(data.get("run_id")), _text(data.get("request_id")))
        return jsonify(result="ACCEPTED"), 202

    @app.post("/api/demo/location-reporting")
    def demo_location_reporting() -> Response:
        data = _object(request.get_json(silent=True))
        paused = data.get("paused")
        if type(paused) is not bool:
            raise ValueError("Expected a paused flag")
        service.set_location_paused(_text(data.get("robot_id")), paused)
        return jsonify(result="ACCEPTED")

    @app.post("/api/workers/<robot_id>/poll")
    def worker_poll(robot_id: str) -> Response | tuple[Response, int]:
        if robot_id not in service.scenario.routes:
            return jsonify(error="Unknown robot"), 404
        data = _object(request.get_json(silent=True))
        session_id = _text(data.get("session_id"))
        telemetry = (
            _telemetry(_object(data["telemetry"])) if "telemetry" in data else None
        )
        telemetry_only = data.get("telemetry_only", False)
        if type(telemetry_only) is not bool or (
            telemetry_only and (telemetry is None or "pose" in data)
        ):
            raise ValueError("Invalid telemetry-only report")
        observation = (
            None
            if telemetry_only
            or (data.get("pose") is None and data.get("location_paused") is True)
            else _observation(data, session_id)
        )
        return jsonify(
            asdict(
                service.poll(
                    robot_id,
                    session_id,
                    observation,
                    telemetry,
                    telemetry_only=telemetry_only,
                )
            )
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local CAS FMS HTTP server")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    service = FleetService(load_scenario(args.scenario))
    create_app(service).run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()

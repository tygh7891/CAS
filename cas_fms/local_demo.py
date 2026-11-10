import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from threading import Thread
from time import sleep

from werkzeug.serving import make_server

from fms_settings import DEFAULT_SCENARIO, load_scenario
from pinky_fms_server.application import FleetService
from pinky_fms_server.http import create_app


def run_demo(
    scenario_path: Path,
    port: int,
    *,
    worker_envs: dict[str, dict[str, str]] | None = None,
    dependencies: Sequence[subprocess.Popen[bytes]] = (),
    headless: bool = False,
    real_mode: bool = False,
    motion_enabled: bool = True,
) -> int:
    scenario_path = scenario_path.resolve()
    scenario = load_scenario(scenario_path)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    program_dir = Path(__file__).resolve().parent
    workers: list[subprocess.Popen[bytes]] = []
    gui: subprocess.Popen[bytes] | None = None
    if real_mode:
        worker_module = "real_worker"
        worker_flags = ["--enable-motion"] if motion_enabled else []
        mode = "실물 주행" if motion_enabled else "실물 연결 점검 · 읽기 전용"
    else:
        worker_module = "gazebo_worker" if worker_envs else "mock_worker"
        worker_flags = []
        mode = "Gazebo" if worker_envs else "가상 로봇"
    with make_server(
        "127.0.0.1",
        port,
        create_app(
            FleetService(
                scenario,
                demo_mode=not real_mode,
                real_mode=real_mode,
                motion_enabled=motion_enabled,
            )
        ),
        threaded=True,
    ) as server:
        server_url = f"http://127.0.0.1:{server.server_port}"
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            for robot_id in scenario.routes:
                workers.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            worker_module,
                            "--server",
                            server_url,
                            "--robot",
                            robot_id,
                            "--scenario",
                            str(scenario_path),
                            *worker_flags,
                        ],
                        cwd=program_dir,
                        env=worker_envs[robot_id] if worker_envs else None,
                    )
                )
            print(f"CAS FMS {mode}: {server_url}", flush=True)
            if not headless:
                command = [
                    sys.executable,
                    "-m",
                    "pinky_fms_gui",
                    "--server",
                    server_url,
                    "--scenario",
                    str(scenario_path),
                ]
                command.extend(("--simulation-name", mode))
                gui = subprocess.Popen(command, cwd=program_dir)
            while gui is None or gui.poll() is None:
                for process in (*workers, *dependencies):
                    if process.poll() is not None:
                        logging.error("FMS process exited: %s", process.args[:4])
                        return 1
                sleep(0.2)
            return gui.returncode
        finally:
            children = workers if gui is None else [gui, *workers]
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for child in children:
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            server.shutdown()
            thread.join()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CAS A1 local simulation")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    raise SystemExit(run_demo(args.scenario, args.port))


if __name__ == "__main__":
    main()

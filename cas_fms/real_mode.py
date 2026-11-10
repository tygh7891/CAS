import argparse
import os
from pathlib import Path

from fms_settings import require_verified_layout
from local_demo import run_demo

REFERENCE_SCENARIO = Path(__file__).with_name("gazebo_scenario.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the laptop FMS for physical Pinkys"
    )
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--robot-1-domain", type=int, default=14)
    parser.add_argument("--robot-2-domain", type=int, default=30)
    parser.add_argument(
        "--local-only", action="store_true", help="Use local ROS for testing"
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--enable-motion", action="store_true")
    args = parser.parse_args()
    domains = (args.robot_1_domain, args.robot_2_domain)
    if len(set(domains)) != 2 or any(not 0 <= value <= 232 for value in domains):
        parser.error("The two robots need distinct ROS_DOMAIN_ID values from 0 to 232")
    if args.enable_motion:
        if args.scenario is None:
            parser.error("Motion needs an explicit, site-verified --scenario")
        try:
            require_verified_layout(args.scenario)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    env = dict(os.environ)
    env.pop("ROS_LOCALHOST_ONLY", None)
    env["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "LOCALHOST" if args.local_only else "SUBNET"
    if args.local_only:
        env["ROS_STATIC_PEERS"] = ""
    worker_envs = {
        f"robot_{number}": dict(env, ROS_DOMAIN_ID=str(domain))
        for number, domain in enumerate(domains, start=1)
    }
    try:
        raise SystemExit(
            run_demo(
                args.scenario or REFERENCE_SCENARIO,
                args.port,
                worker_envs=worker_envs,
                headless=args.headless,
                real_mode=True,
                motion_enabled=args.enable_motion,
            )
        )
    except KeyboardInterrupt:
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()

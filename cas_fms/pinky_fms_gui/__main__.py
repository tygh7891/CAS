import argparse
import signal
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from fms_settings import DEFAULT_SCENARIO, load_scenario
from pinky_fms_gui.presentation import FmsPresenter
from pinky_fms_gui.views import FmsView


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the CAS FMS window")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--simulation-name", default="가상 로봇")
    args = parser.parse_args()
    application = QApplication([])
    application.setApplicationName("CAS FMS")
    view = FmsView(load_scenario(args.scenario), args.simulation_name)
    signal.signal(signal.SIGINT, lambda *_: application.quit())
    FmsPresenter(view, args.server)
    view.show()
    raise SystemExit(application.exec_())


if __name__ == "__main__":
    main()

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from latencylab_ui.icon_resolver import get_app_icon_path
from latencylab_ui.main_window import MainWindow
from latencylab_ui.run_controller import RunController
from latencylab_ui.theme import Theme, apply_theme


def run_app(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LatencyLab")
    app.setOrganizationName("LatencyLab")

    # Set before any window is created so every window and dialog inherits it.
    icon_path = get_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    apply_theme(app, Theme.DARK)

    controller = RunController()
    # Ensure we don't tear down while a simulation worker thread is still running.
    app.aboutToQuit.connect(controller.shutdown)
    window = MainWindow(run_controller=controller)
    # Default width provides enough horizontal space for the docked Distributions
    # panel while keeping the left-side Run/Summary/Critical Path panel readable.
    window.resize(1400, 720)
    window.show()

    return app.exec()

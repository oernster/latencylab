from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from latencylab_ui.main_window import MainWindow
from latencylab_ui.run_controller import RunController
from latencylab_ui.theme import Theme, apply_theme


def run_app(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LatencyLab")
    app.setOrganizationName("LatencyLab")
    apply_theme(app, Theme.DARK)

    controller = RunController()
    # Ensure we don't tear down while a simulation worker thread is still running.
    app.aboutToQuit.connect(controller.shutdown)
    window = MainWindow(run_controller=controller)
    window.resize(1100, 720)
    window.show()

    return app.exec()


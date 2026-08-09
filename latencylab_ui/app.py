from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from latencylab.version import __version__
from latencylab_ui.icon_resolver import get_app_icon_path
from latencylab_ui.main_window import MainWindow
from latencylab_ui.run_controller import RunController
from latencylab_ui.single_instance import (
    InstanceServer,
    another_instance_is_running,
    raise_window,
)
from latencylab_ui.theme import Theme, apply_theme
from latencylab_ui.update_check import install_update_check
from latencylab_ui.update_core import UpdateService, platform_key_for
from latencylab_ui.update_github import GitHubReleaseSource
from latencylab_ui.wheel_guard import install_wheel_guard
from latencylab_ui.windows_identity import claim_app_identity

# What a second copy returns after handing its request to the first. Zero
# because nothing went wrong: the user asked for LatencyLab and is about to be
# looking at it.
ALREADY_RUNNING_EXIT_CODE = 0


def run_app(argv: list[str] | None = None) -> int:
    # Before the first window exists, so every window it creates is filed under
    # the same identity the installer put on the shortcut.
    claim_app_identity()

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LatencyLab")
    app.setOrganizationName("LatencyLab")

    # Asked after QApplication exists, because the answer travels over Qt's own
    # socket, and before any window is built, because the whole point is not to
    # build a second one.
    if another_instance_is_running():
        return ALREADY_RUNNING_EXIT_CODE

    # Set before any window is created so every window and dialog inherits it.
    icon_path = get_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    apply_theme(app, Theme.DARK)

    # Application-wide, and held on the app, because the composer creates and
    # destroys controls as the model is edited.
    app._wheel_guard = install_wheel_guard(app)

    controller = RunController()
    # Ensure we don't tear down while a simulation worker thread is still running.
    app.aboutToQuit.connect(controller.shutdown)
    window = MainWindow(run_controller=controller)
    install_update_check(
        window,
        UpdateService(
            GitHubReleaseSource(), __version__, platform_key_for(sys.platform)
        ),
    )
    # Default width provides enough horizontal space for the docked Distributions
    # panel while keeping the left-side Run/Summary/Critical Path panel readable.
    window.resize(1400, 720)
    window.show()

    # Held on the window so its lifetime is the window's, and started only once
    # there is a window worth raising.
    window._instance_server = InstanceServer(lambda: raise_window(window))

    return app.exec()

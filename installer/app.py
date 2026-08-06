"""Entry point for the LatencyLab setup program.

    LatencyLabSetup.exe              install
    LatencyLabSetup.exe --uninstall  remove

The uninstall flag is what the Apps and Features entry invokes, which is why
one executable does both jobs and why the installer keeps a copy of itself
beside the installation.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from installer.constants import APP_NAME, ICON_ICO_NAME, UNINSTALL_FLAG
from installer.paths import payload_asset
from installer.theme import STYLESHEET
from installer.window import InstallerWindow


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    uninstalling = UNINSTALL_FLAG in arguments[1:]

    app = QApplication(arguments)
    app.setApplicationName(f"{APP_NAME} Setup")
    app.setOrganizationName(APP_NAME)

    icon = payload_asset(ICON_ICO_NAME)
    if icon is not None:
        app.setWindowIcon(QIcon(str(icon)))

    app.setStyleSheet(STYLESHEET)

    window = InstallerWindow(uninstalling=uninstalling)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

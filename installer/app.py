#!/usr/bin/env python3
"""LatencyLab installer: the entry point.

A self-contained PySide6 installer compiled into a single executable by
buildinstaller.py. It carries the built application bundle and the licence texts
as an embedded payload (staged under `payload/` by the build tooling) and offers
the full lifecycle:

- Install, upgrade, reinstall and repair the per-user application.
- Register the app in Windows Apps and features (the HKCU Uninstall key), so it
  appears as an installed program with a working Uninstall action.
- Uninstall, also runnable headlessly via `--uninstall`, which is how the
  registered UninstallString re-invokes a copy of this installer.
- Optional Desktop and Start Menu shortcuts, plus an optional launch on finish.

It never needs administrator rights: it deploys to
`%LOCALAPPDATA%\\Programs\\LatencyLab` and registers under HKCU. It is
deliberately standalone (it imports nothing from the `latencylab` packages) and
dependency-light: process detection uses `tasklist`, version comparison is a
plain tuple compare and shortcuts are written through the Windows scripting
host, so the onefile build pulls in nothing beyond PySide6 and the standard
library.

The installer is a second application. It is layered like one:

- `installer_logic` decides (pure, covered by the test suite).
- `installer_ops` acts (registry, processes, shortcuts, shell-outs).
- `installer_lifecycle` composes the two into install, repair and uninstall.
- `installer_bundle` reads the payload beside this binary.
- `installer_theme`, `installer_widgets` and `installer_window` are the Qt
  surface, outside the coverage gate exactly as the application's UI is.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QDialog

import installer_bundle as bundle
import installer_lifecycle as lifecycle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme
from installer_widgets import AppRunningDialog, UninstallDialog
from installer_window import InstallerWindow

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME


def _new_application(name: str) -> QApplication:
    """Create the QApplication with the installer's identity and style."""

    app = QApplication(sys.argv)
    # Pin Fusion: the native windows11 style paints over stylesheet borders, so
    # without this the themed buttons and the focus ring simply do not appear.
    app.setStyle("fusion")
    app.setApplicationName(name)
    app.setWindowIcon(bundle.app_icon())
    return app


def _run_uninstall_cli(args: argparse.Namespace) -> int:
    """Run the uninstall flow when invoked as the registered uninstaller."""

    _new_application(f"{APP_DISPLAY_NAME} Setup")
    if args.quiet:
        lifecycle.uninstall()
        return 0
    if UninstallDialog().exec() != QDialog.DialogCode.Accepted:
        return 0
    if ops.is_app_running():
        if AppRunningDialog("uninstall").exec() != QDialog.DialogCode.Accepted:
            return 0
    lifecycle.uninstall()
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the installer command line (used for the registered uninstaller)."""

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(logic.UNINSTALL_FLAG, dest="uninstall", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    """Run the installer GUI, unless invoked as the registered uninstaller."""

    ops.install_crash_logging()
    ops.set_app_user_model_id()
    args = _parse_args(sys.argv[1:])
    if args.uninstall:
        return _run_uninstall_cli(args)

    app = _new_application(theme.WINDOW_TITLE)
    window = InstallerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

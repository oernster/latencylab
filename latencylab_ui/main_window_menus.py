from __future__ import annotations

import platform
from collections.abc import Callable

import PySide6
from PySide6.QtWidgets import QMainWindow, QWidget

from latencylab.version import __version__

from latencylab_ui.about_dialog import AboutDialog, AboutDialogContent


def build_menus(
    window: QMainWindow,
    *,
    on_open_model: Callable[[], None],
    on_exit: Callable[[], None],
) -> None:
    """Create the app menu bar.

    Menu titles are part of the focus-cycle traversal.
    """

    file_menu = window.menuBar().addMenu("File")
    open_action = file_menu.addAction("Open model…")
    open_action.triggered.connect(on_open_model)
    file_menu.addSeparator()
    exit_action = file_menu.addAction("Exit")
    exit_action.triggered.connect(on_exit)

    help_menu = window.menuBar().addMenu("Help")
    about_action = help_menu.addAction("About…")
    about_action.triggered.connect(lambda: show_about_dialog(window))


def show_about_dialog(parent: QWidget) -> None:
    # IMPORTANT: do not use `exec()` (modal event loop). It can be fragile
    # under some test / CI environments and is unnecessary for an About dialog.
    dlg = AboutDialog(
        parent,
        content=AboutDialogContent(title="LatencyLab", emoji="⏱️", body=_about_text()),
    )

    # Keep a reference on the parent so the dialog isn't garbage-collected
    # immediately after showing.
    setattr(parent, "_about_dialog", dlg)

    dlg.open()


def _about_text() -> str:
    py_ver = platform.python_version()
    pyside_ver = getattr(PySide6, "__version__", "(unknown)")

    # Keep this as plain text so tests can easily assert substrings.
    return "\n".join(
        [
            f"Version: {__version__}",
            "Author: Oliver Ernster",
            "",
            f"Python: {py_ver}",
            f"PySide6 (Qt for Python): {pyside_ver}",
            "",
            "Credits:",
            "- Python (Python Software Foundation)",
            "- PySide6 (Qt for Python)",
        ]
    )


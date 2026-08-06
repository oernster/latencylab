"""A read-only viewer for the licence texts the setup program carries.

LatencyLab is split: the headless model is GPL-3.0 and the PySide6 front end is
LGPL-3.0. Both are shown here, plus the installer's own as-is notice, from one
parameterised dialog rather than three near-identical ones.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from installer.constants import CONTENT_MARGIN, CONTENT_SPACING

DIALOG_WIDTH = 640
DIALOG_HEIGHT = 620

FALLBACK_TEXT = (
    "The licence text was not bundled with this setup program.\n\n"
    "The full text is published with the source at "
    "https://github.com/oernster/latencylab"
)


def read_licence(path: Path | None) -> str:
    """The licence text; failing that, an explanation of why it is missing.

    A packaging slip must not be the difference between a dialog and a
    traceback, so this never raises.
    """

    if path is None:
        return FALLBACK_TEXT
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return FALLBACK_TEXT


class LicenceDialog(QDialog):
    def __init__(self, parent: QWidget, *, title: str, path: Path | None) -> None:
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setModal(True)
        self.resize(DIALOG_WIDTH, DIALOG_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN
        )
        root.setSpacing(CONTENT_SPACING)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        text.setFont(mono)
        text.setPlainText(read_licence(path))
        root.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

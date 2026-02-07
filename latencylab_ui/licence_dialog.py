from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


class LicenceDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setWindowTitle("UI Licence")
        # Text is long; allow resizing but remove maximize.
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setModal(True)

        # Start with a sensible size so the license is readable immediately.
        # (Still resizable by the user.)
        # Keep reasonably compact; wide dialogs are awkward on smaller screens.
        self.resize(591, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        # Wrap long lines so nothing is horizontally truncated.
        text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        text.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Use a readable, stable font for license text.
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        text.setFont(mono)
        text.setPlainText(_read_lgpl3_text())
        root.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


def _read_lgpl3_text() -> str:
    # The UI is LGPLv3; the text lives in latencylab_ui/LGPL3.txt.
    root = Path(__file__).resolve().parent
    licence_path = root / "LGPL3.txt"
    return licence_path.read_text(encoding="utf-8")


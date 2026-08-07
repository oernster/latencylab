from __future__ import annotations

"""The Guide: how to use the application, in the order you would need it.

Distinct from How to Read, which is about interpreting output and says nothing
about which button to press. This one is the other half: press this, then this,
and here is why you would pick that setting rather than the other one.

Non-modal, like How to Read and for the same reason: guidance you cannot keep
open beside the thing it describes is guidance you have to memorise first.

It wears the reading cycle, so a reader who opens it and does nothing is carried
down the page and back rather than left holding a scrollbar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from latencylab_ui.auto_scroller import attach
from latencylab_ui.first_stop_dialog import FirstStopDialog
from latencylab_ui.guide_text import GUIDE_HTML, GUIDE_TITLE

# Wider than How to Read, because this one carries numbered steps and bold run
# ins that wrap badly in a narrow column, and tall enough that a step and its
# reason are on screen together.
DIALOG_W = 680
DIALOG_H = 760


class GuideDialog(FirstStopDialog):
    """A page of guidance that reads itself."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("guide_dialog")
        self.setWindowTitle(GUIDE_TITLE)
        self.resize(DIALOG_W, DIALOG_H)

        # Guidance must not block the thing it is describing.
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        text = QTextBrowser(self)
        text.setReadOnly(True)
        # A QTextBrowser scrolls in PIXELS, which is what the reading cycle
        # needs; the plain-text widget scrolls in lines and the same gentle
        # drift becomes a whole line jumping at a time.
        text.setHtml(GUIDE_HTML)
        root.addWidget(text, 1)
        attach(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

"""The installer's shared widgets: the focus sink and the dialogs.

The dialogs are the three the lifecycle needs: a licence view, the ask to close
a running application before setup replaces its files, plus the uninstall
confirmation that names what is about to be removed.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import installer_bundle as bundle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME


def licence_view_width(view: QTextEdit, text: str) -> int:
    """Return the pixel width that shows the widest licence line in full.

    Licence texts arrive hard-wrapped, so wrapping them again reads badly. The
    dialog is sized to the content instead of to a guessed constant.
    """

    view.ensurePolished()
    metrics = view.fontMetrics()
    lines = text.splitlines() or [text]
    widest = max(metrics.horizontalAdvance(line) for line in lines)
    doc_margin = round(view.document().documentMargin())
    scrollbar = view.verticalScrollBar().sizeHint().width()
    chrome = theme.SIDES * (doc_margin + theme.TEXT_PADDING_PX + theme.BORDER_PX)
    return widest + scrollbar + chrome + theme.WIDTH_SAFETY_PX


class NeutralStart(QWidget):
    """A 0x0 focus sink so a window opens with nothing ringed.

    It leaves the tab chain as soon as focus moves on, so the cycle that
    follows holds only real controls.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class LicenceDialog(QDialog):
    """A themed, scrollable view of a licence text, sized to its content."""

    def __init__(
        self,
        licence_text: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        self._start = NeutralStart(self)
        layout.addWidget(self._start)
        self._started = False

        view = QTextEdit()
        view.setObjectName("LicenceView")
        view.setReadOnly(True)
        view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        view.setPlainText(licence_text)
        layout.addWidget(view)

        view_width = licence_view_width(view, licence_text)
        view.setMinimumWidth(view_width)
        self.resize(view_width + theme.SIDES * margin, theme.LICENCE_DIALOG_HEIGHT)

        close = QPushButton("Close")
        close.setObjectName("SecondaryAction")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._start.setFocus()


class AppRunningDialog(QDialog):
    """A themed ask to close the running app before setup continues.

    Retry re-checks the task list and accepts once the app is gone. A premature
    retry gets an immediate still-running notice rather than a silent no-op.
    """

    def __init__(self, action: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_DISPLAY_NAME} Setup")
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        self._start = NeutralStart(self)
        layout.addWidget(self._start)
        self._started = False

        message = QLabel(
            f"{APP_DISPLAY_NAME} is currently running. Close it, then choose "
            f"Retry to continue with the {action}."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self._notice = QLabel("")
        self._notice.setObjectName("StatusLine")
        self._notice.setWordWrap(True)
        layout.addWidget(self._notice)

        retry = QPushButton("Retry")
        retry.setObjectName("PrimaryAction")
        retry.clicked.connect(self._on_retry)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryAction")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(retry)
        layout.addLayout(row)

    def _on_retry(self) -> None:
        if ops.is_app_running():
            self._notice.setText(
                f"{APP_DISPLAY_NAME} is still running. Close it first."
            )
            return
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._start.setFocus()


class UninstallDialog(QDialog):
    """A small themed uninstall confirmation naming what will be removed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Uninstall {APP_DISPLAY_NAME}")
        self.setWindowIcon(bundle.app_icon())
        self.setStyleSheet(theme.STYLESHEET)

        layout = QVBoxLayout(self)
        margin = theme.DIALOG_MARGIN
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(theme.BUTTON_GAP)

        self._start = NeutralStart(self)
        layout.addWidget(self._start)
        self._started = False

        message = QLabel(
            f"Remove {APP_DISPLAY_NAME} and its shortcuts from this PC? Any "
            "models you have saved elsewhere are left alone."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        confirm = QPushButton("Uninstall")
        confirm.setObjectName("DangerAction")
        confirm.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryAction")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(confirm)
        layout.addLayout(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._start.setFocus()

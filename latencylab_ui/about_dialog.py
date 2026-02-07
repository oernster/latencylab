from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class AboutDialogContent:
    title: str
    emoji: str
    body: str


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget, *, content: AboutDialogContent) -> None:
        super().__init__(parent)
        # Keep short to avoid truncation on small dialogs / narrow screens.
        self.setWindowTitle("About")

        # About dialogs should not be maximizable (awkward UX for a small,
        # mostly-static content window), but must still be closable.
        #
        # On Windows, using a fixed-size dialog hint is the most reliable way to
        # remove the maximize button while keeping the close button.
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint, True)
        self.setSizeGripEnabled(False)

        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        title = QLabel(content.title)
        title.setObjectName("about_title")
        title.setTextFormat(Qt.TextFormat.PlainText)
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSizeF(max(10.0, title_font.pointSizeF() + 2.0))
        title.setFont(title_font)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(title)

        # IMPORTANT: our app theme sets a global stylesheet font-size in px
        # (see QWidget { font-size: ...px; } in latencylab_ui/theme.py).
        # Stylesheets can override fonts set via QFont point sizes, which makes
        # emoji scaling via pointSizeF unreliable. For a reliably huge emoji,
        # compute a pixel target from the *rendered* title metrics and apply a
        # per-widget stylesheet (font-size: Npx) to the emoji label.
        title.ensurePolished()
        title_px_height = max(1, title.fontMetrics().height())
        emoji_px = max(64, int(round(title_px_height * 4.0)))

        emoji = QLabel(content.emoji)
        emoji.setObjectName("about_emoji")
        emoji.setTextFormat(Qt.TextFormat.PlainText)
        emoji.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        emoji.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        emoji_font = QFont(emoji.font())
        # Prefer an emoji-capable font on Windows; other platforms will ignore
        # unknown families and fall back.
        emoji_font.setFamily("Segoe UI Emoji")
        emoji.setFont(emoji_font)

        # Force pixel sizing on this widget so it can't be clamped by the
        # global QWidget font-size rule.
        emoji.setStyleSheet(f"font-size: {emoji_px}px;")
        emoji.setMinimumWidth(int(emoji_px * 1.10))
        emoji.setMinimumHeight(int(emoji_px * 1.05))
        header.addWidget(emoji)

        root.addLayout(header)

        body = QLabel(content.body)
        body.setObjectName("about_body")
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setWordWrap(True)
        root.addWidget(body)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


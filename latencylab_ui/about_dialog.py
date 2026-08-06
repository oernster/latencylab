from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.icon_resolver import get_app_icon_path, get_app_icon_png_path

# The badge beside the title. Square, large enough to read as the product's
# mark rather than as decoration.
_BADGE_PX = 96


@dataclass(frozen=True)
class AboutDialogContent:
    title: str
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

        # The real generated icon, never a glyph painted from a font: the badge
        # here, the taskbar and the installer all have to be the same mark, which
        # only a file can guarantee.
        badge_path = get_app_icon_png_path(_BADGE_PX)
        if badge_path is not None:
            badge = QLabel()
            badge.setObjectName("about_icon")
            badge.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            )
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            badge.setPixmap(
                QPixmap(str(badge_path)).scaled(
                    _BADGE_PX,
                    _BADGE_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            header.addWidget(badge)

        icon_path = get_app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

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

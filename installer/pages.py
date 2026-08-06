"""The three pages of the setup program: choose, work, report.

Each page is a plain widget that owns its controls and exposes them to the
window. Nothing here starts work or touches the filesystem; the window does
that, so the sequence lives in one place.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from installer.constants import (
    APP_NAME,
    APP_TAGLINE,
    BADGE_PNG_NAME,
    BADGE_PX,
    CONTENT_MARGIN,
    CONTENT_SPACING,
    PROGRESS_MAX,
    PROGRESS_MIN,
)
from installer.paths import payload_asset


def _root_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(
        CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN
    )
    layout.setSpacing(CONTENT_SPACING)
    return layout


def _badge() -> QLabel | None:
    """The generated icon, never a glyph: the same mark the app itself uses."""

    path = payload_asset(BADGE_PNG_NAME)
    if path is None:
        return None

    label = QLabel()
    label.setPixmap(
        QPixmap(str(path)).scaled(
            BADGE_PX,
            BADGE_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )
    label.setFixedSize(BADGE_PX, BADGE_PX)
    return label


class WelcomePage(QWidget):
    """What is about to happen, where, plus the two choices about it."""

    def __init__(self, *, version: str, install_path: str) -> None:
        super().__init__()
        root = _root_layout(self)

        header = QHBoxLayout()
        header.setSpacing(CONTENT_SPACING)
        badge = _badge()
        if badge is not None:
            header.addWidget(badge)

        heading = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel(f"{APP_TAGLINE}\nVersion {version}")
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        root.addLayout(header)

        location = QLabel(f"It will be installed for you alone, in:\n{install_path}")
        location.setWordWrap(True)
        root.addWidget(location)

        no_admin = QLabel(
            "No administrator rights are needed and nothing outside your own "
            "user profile is changed."
        )
        no_admin.setObjectName("subtitle")
        no_admin.setWordWrap(True)
        root.addWidget(no_admin)

        self.desktop_shortcut = QCheckBox("Create a Desktop shortcut")
        self.desktop_shortcut.setChecked(True)
        self.start_menu_shortcut = QCheckBox("Add it to the Start Menu")
        self.start_menu_shortcut.setChecked(True)
        root.addWidget(self.desktop_shortcut)
        root.addWidget(self.start_menu_shortcut)

        root.addStretch()

        licences = QHBoxLayout()
        self.model_licence_button = QPushButton("Model licence (GPL-3.0)")
        self.ui_licence_button = QPushButton("UI licence (LGPL-3.0)")
        self.installer_licence_button = QPushButton("Installer notice")
        licences.addWidget(self.model_licence_button)
        licences.addWidget(self.ui_licence_button)
        licences.addWidget(self.installer_licence_button)
        licences.addStretch()
        root.addLayout(licences)


class ConfirmUninstallPage(QWidget):
    """Removal names exactly what it will delete, before it deletes anything."""

    def __init__(self, *, version: str, install_path: str) -> None:
        super().__init__()
        root = _root_layout(self)

        header = QHBoxLayout()
        header.setSpacing(CONTENT_SPACING)
        badge = _badge()
        if badge is not None:
            header.addWidget(badge)

        title = QLabel(f"Remove {APP_NAME}")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        detail = QLabel(
            f"{APP_NAME} {version} will be removed from:\n{install_path}\n\n"
            "Its Desktop and Start Menu shortcuts and its Apps and Features "
            "entry go with it. Any models you saved elsewhere are untouched."
        )
        detail.setWordWrap(True)
        root.addWidget(detail)

        root.addStretch()


class ProgressPage(QWidget):
    """The bar and the one line of text saying what it is doing."""

    def __init__(self) -> None:
        super().__init__()
        root = _root_layout(self)

        title = QLabel(f"Installing {APP_NAME}")
        title.setObjectName("title")
        root.addWidget(title)

        self.bar = QProgressBar()
        self.bar.setRange(PROGRESS_MIN, PROGRESS_MAX)
        self.bar.setValue(PROGRESS_MIN)
        root.addWidget(self.bar)

        self.status = QLabel("")
        self.status.setObjectName("subtitle")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        root.addStretch()

    def report(self, percent: int, message: str) -> None:
        self.bar.setValue(percent)
        self.status.setText(message)


class DonePage(QWidget):
    """The outcome, success or failure, in the user's own words."""

    def __init__(self) -> None:
        super().__init__()
        root = _root_layout(self)

        self.title = QLabel("")
        self.title.setObjectName("title")
        root.addWidget(self.title)

        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.detail)

        root.addStretch()

    def show_success(self, heading: str, detail: str) -> None:
        self.title.setText(heading)
        self.detail.setText(detail)

    def show_failure(self, detail: str) -> None:
        self.title.setText("Setup could not finish")
        self.detail.setText(detail)

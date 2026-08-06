"""The installer's header row: identity and the licence texts.

Everything else in the window is the install lifecycle. This is the part that is
not: the badge, the name, the version and the three texts a user may want to
read before committing to anything. Keeping it here leaves installer_window.py
holding one concern.

Nothing here holds state. Each function takes the window it belongs to, so the
dialogs are parented correctly without this module knowing what a window is.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

import installer_bundle as bundle
import installer_logic as logic
import installer_theme as theme
from installer_widgets import LicenceDialog

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME


def _show_licence(parent: QWidget, text: str, title: str) -> None:
    LicenceDialog(text, title, parent).exec()


def show_model_licence(parent: QWidget) -> None:
    _show_licence(
        parent,
        bundle.licence_text(logic.MODEL_LICENSE_FILE_NAME),
        f"{APP_DISPLAY_NAME} Model Licence (GPL-3.0)",
    )


def show_ui_licence(parent: QWidget) -> None:
    _show_licence(
        parent,
        bundle.licence_text(logic.UI_LICENSE_FILE_NAME),
        f"{APP_DISPLAY_NAME} UI Licence (LGPL-3.0)",
    )


def show_installer_licence(parent: QWidget) -> None:
    _show_licence(
        parent,
        bundle.installer_licence_text(),
        f"{APP_DISPLAY_NAME} Installer Notice",
    )


def _build_name_block() -> QWidget:
    """Build the name and version pair as a container of their own.

    Aligned directly against the header row, the version bottom-aligns to a row
    whose height is set by the much taller icon, and so lands well below the
    words it belongs to. Inside a container sized to the title, its bottom is
    the title's bottom, which is where it reads as a version.
    """

    name_block = QWidget()
    name_row = QHBoxLayout(name_block)
    name_row.setContentsMargins(0, 0, 0, 0)
    name_row.setSpacing(theme.HEADER_VERSION_GAP)

    title = QLabel(f"{APP_DISPLAY_NAME} Setup")
    title.setObjectName("HeaderTitle")
    name_row.addWidget(title)

    version = bundle.app_version()
    if version:
        version_label = QLabel(f"v{version}")
        version_label.setObjectName("HeaderVersion")
        # Centred on the title's line, not bottom-aligned: bottom alignment
        # hangs it below the words like a subscript.
        name_row.addWidget(version_label, 0, Qt.AlignmentFlag.AlignVCenter)
    return name_block


def build_header(parent: QWidget) -> QHBoxLayout:
    """Build the header row: icon, title and version, plus licence buttons."""

    header = QHBoxLayout()
    header.setSpacing(theme.HEADER_SPACING)

    icon = bundle.app_icon()
    if not icon.isNull():
        badge = QLabel()
        badge.setPixmap(icon.pixmap(QSize(theme.ICON_PX, theme.ICON_PX)))
        header.addWidget(badge)

    # Constrain BOTH axes. A vertical alignment alone leaves the container free
    # to stretch across the row, and the title label then absorbs the slack and
    # carries the version off to the right with it.
    header.addWidget(
        _build_name_block(),
        0,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    header.addStretch()

    for caption, handler in (
        ("Installer notice", show_installer_licence),
        ("Model licence (GPL-3.0)", show_model_licence),
        ("UI licence (LGPL-3.0)", show_ui_licence),
    ):
        button = QPushButton(caption)
        button.setObjectName("LicenceButton")
        button.clicked.connect(lambda _checked=False, call=handler: call(parent))
        header.addWidget(button)
    return header

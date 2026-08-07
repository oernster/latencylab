from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from latencylab_ui.icon_resolver import get_app_icon_png_path
from latencylab_ui.theme import Theme
from latencylab_ui.theme_toggle import ThemeToggle

TOOLBAR_BUTTON_PX = 34

# The application mark, in the middle of the bar. Painted from the generated
# icon set rather than an emoji glyph, so the mark in the bar, the mark in the
# taskbar, the mark on the shortcut and the mark in About are all one file.
TOP_BADGE_PX = 36

# Ask for a larger source and scale it down: downscaling a slightly-too-big icon
# looks better than upscaling a slightly-too-small one.
_BADGE_SOURCE_PX = 64

MARGIN_SIDE = 10
BUTTON_SPACING = 8


@dataclass(frozen=True, slots=True)
class TopBar:
    """The top bar and every control on it the window needs to reach later."""

    widget: QWidget
    save_log_btn: QPushButton
    distributions_btn: QPushButton
    how_to_read_btn: QPushButton
    compose_btn: QPushButton
    badge: QLabel
    theme_toggle: ThemeToggle


def _build_badge(parent: QWidget) -> QLabel:
    """The application mark, sized whether or not its file resolves.

    The size is fixed either way. A badge that collapses when the icon set is
    missing would silently move the thing it is supposed to centre.
    """

    badge = QLabel(parent)
    badge.setObjectName("top_app_badge")
    badge.setFixedSize(TOP_BADGE_PX, TOP_BADGE_PX)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    # Decoration, not a control: nothing can be done to it, so it is not on the
    # keyboard ring, and it must not swallow a click meant for what is behind it.
    badge.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    badge_path = get_app_icon_png_path(_BADGE_SOURCE_PX)
    if badge_path is not None:
        badge.setPixmap(
            QPixmap(str(badge_path)).scaled(
                TOP_BADGE_PX,
                TOP_BADGE_PX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    return badge


def _icon_button(
    glyph: str, *, tooltip: str, on_clicked: Callable[[], None]
) -> QPushButton:
    button = QPushButton(glyph)
    button.setToolTip(tooltip)
    button.setProperty("role", "icon-action")
    button.setFixedHeight(TOOLBAR_BUTTON_PX)
    button.clicked.connect(on_clicked)
    return button


def build_top_bar(
    parent: QWidget,
    *,
    on_save_log_clicked: Callable[[], None],
    on_show_distributions_clicked: Callable[[], None],
    on_show_how_to_read_clicked: Callable[[], None],
    on_toggle_model_composer_clicked: Callable[[], None],
    on_theme_changed: Callable[[Theme], None],
) -> TopBar:
    """Build the top bar: actions at the edges, the app badge dead centre.

    The badge is centred on the BAR, which a row of stretches cannot do. Three
    stretches centre it in the space LEFT OVER between the flanking groups, and
    those groups are nowhere near the same width, so the badge lands well right
    of centre (134px out of 1400, measured). Equalising two grid columns by
    stretch does not work either, because a column never shrinks below its own
    content.

    What does work is an overlay: the controls and the badge occupy the SAME
    grid cell, that cell is the whole bar, and the badge centres itself in it.
    """

    top_bar = QWidget(parent)
    grid = QGridLayout(top_bar)
    grid.setContentsMargins(MARGIN_SIDE, 0, MARGIN_SIDE, 0)

    controls = QWidget(top_bar)
    layout = QHBoxLayout(controls)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(BUTTON_SPACING)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    save_log_btn = _icon_button(
        "💾", tooltip="Export runs as zip…", on_clicked=on_save_log_clicked
    )
    layout.addWidget(save_log_btn, 0, Qt.AlignmentFlag.AlignTop)

    distributions_btn = _icon_button(
        "📊",
        tooltip="Show latency and critical-path distributions",
        on_clicked=on_show_distributions_clicked,
    )
    layout.addWidget(distributions_btn, 0, Qt.AlignmentFlag.AlignTop)

    how_to_read_btn = _icon_button(
        "ℹ️",
        tooltip="How to Read LatencyLab Output",
        on_clicked=on_show_how_to_read_clicked,
    )
    how_to_read_btn.setObjectName("how_to_read_btn")
    layout.addWidget(how_to_read_btn, 0, Qt.AlignmentFlag.AlignTop)

    compose_btn = QPushButton("Compose Model")
    compose_btn.setObjectName("compose_model_btn")
    compose_btn.setToolTip("Show/hide the Model Composer dock")
    # Checkable so the open composer is visible ON the button that opened it.
    compose_btn.setCheckable(True)
    compose_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    compose_btn.setFixedHeight(TOOLBAR_BUTTON_PX)
    compose_btn.clicked.connect(on_toggle_model_composer_clicked)
    layout.addWidget(compose_btn, 0, Qt.AlignmentFlag.AlignTop)

    layout.addStretch(1)

    theme_toggle = ThemeToggle(default=Theme.DARK, parent=parent)
    theme_toggle.theme_changed.connect(on_theme_changed)
    layout.addWidget(theme_toggle, 0, Qt.AlignmentFlag.AlignTop)

    badge = _build_badge(top_bar)

    grid.addWidget(controls, 0, 0)
    grid.addWidget(
        badge, 0, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
    )

    return TopBar(
        widget=top_bar,
        save_log_btn=save_log_btn,
        distributions_btn=distributions_btn,
        how_to_read_btn=how_to_read_btn,
        compose_btn=compose_btn,
        badge=badge,
        theme_toggle=theme_toggle,
    )

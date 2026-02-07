from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from latencylab_ui.focus_cycle import FocusCycleController
from latencylab_ui.main_window_bindings import connect_theme_toggle
from latencylab_ui.theme import Theme
from latencylab_ui.theme_toggle import ThemeToggle


def build_top_bar(
    parent: QWidget,
    *,
    focus_cycle: FocusCycleController,
    on_save_log_clicked: Callable[[], None],
) -> tuple[QWidget, QPushButton, QLabel, ThemeToggle]:
    top_bar = QWidget(parent)
    layout = QHBoxLayout(top_bar)
    layout.setContentsMargins(10, 0, 10, 0)
    layout.setSpacing(8)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    save_log_btn = QPushButton("💾")
    save_log_btn.setToolTip("Save log…")
    save_log_btn.setProperty("role", "icon-action")
    save_log_btn.clicked.connect(on_save_log_clicked)
    layout.addWidget(save_log_btn, 0, Qt.AlignmentFlag.AlignTop)

    clock = QLabel("⏱️")
    clock.setObjectName("top_clock_emoji")
    clock.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    clock.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    clock.setMinimumSize(36, 36)
    # Keep styling simple + deterministic. The layout align-top should align the
    # widget edge with the top of the icon buttons.
    # Emoji glyphs tend to have extra top/bottom font leading. A small negative
    # top margin aligns the *glyph* visually with the icon buttons.
    clock.setStyleSheet("font-size: 36px; padding: 0px; margin-top: -4px;")

    layout.addStretch(1)
    layout.addWidget(clock, 0, Qt.AlignmentFlag.AlignTop)
    layout.addStretch(1)

    theme_toggle = ThemeToggle(default=Theme.DARK, parent=parent)
    connect_theme_toggle(
        theme_toggle=theme_toggle,
        receiver=parent,
        focus_cycle=focus_cycle,
    )
    layout.addWidget(theme_toggle, 0, Qt.AlignmentFlag.AlignTop)

    return top_bar, save_log_btn, clock, theme_toggle


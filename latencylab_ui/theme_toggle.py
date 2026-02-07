from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from latencylab_ui.theme import Theme


class ThemeToggle(QWidget):
    """Two-button Light/Dark toggle."""

    theme_changed = Signal(Theme)

    def __init__(self, *, default: Theme = Theme.DARK, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._btn_light = QPushButton("☀")
        self._btn_light.setCheckable(True)
        self._btn_light.setProperty("role", "theme-toggle")
        self._btn_light.setToolTip("Light theme")
        layout.addWidget(self._btn_light)

        self._btn_dark = QPushButton("🌙")
        self._btn_dark.setCheckable(True)
        self._btn_dark.setProperty("role", "theme-toggle")
        self._btn_dark.setToolTip("Dark theme")
        layout.addWidget(self._btn_dark)

        # Keep the toggle compact; let the layout around it place it.
        self.setContentsMargins(0, 0, 0, 0)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self._btn_light)
        group.addButton(self._btn_dark)
        self._group = group

        self._btn_light.toggled.connect(
            lambda checked: self._emit_if_checked(Theme.LIGHT, checked)
        )
        self._btn_dark.toggled.connect(
            lambda checked: self._emit_if_checked(Theme.DARK, checked)
        )

        self.set_theme(default)

    def set_theme(self, theme: Theme) -> None:
        if theme == Theme.DARK:
            self._btn_dark.setChecked(True)
        else:
            self._btn_light.setChecked(True)

    def _emit_if_checked(self, theme: Theme, checked: bool) -> None:
        if checked:
            self.theme_changed.emit(theme)



from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from latencylab_ui.theme import Theme


class ThemeToggle(QWidget):
    """Two-button Light/Dark toggle."""

    theme_changed = Signal(Theme)
    focus_advance_requested = Signal(object)

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
        self._update_enabled_state(theme)

    def _update_enabled_state(self, theme: Theme) -> None:
        """Disable the currently-selected theme button so it isn't tabbable."""

        if theme == Theme.DARK:
            self._btn_dark.setEnabled(False)
            self._btn_light.setEnabled(True)
        else:
            self._btn_light.setEnabled(False)
            self._btn_dark.setEnabled(True)

    def _emit_if_checked(self, theme: Theme, checked: bool) -> None:
        if checked:
            # Keep enabled/disabled state in sync even when user toggles via
            # keyboard (space) or mouse.
            #
            if theme == Theme.DARK:
                # Request focus to advance to the next UI control (e.g.
                # "Open model…") when dark is selected.
                #
                # This must happen *before* we disable the button, so the
                # focus-cycle controller can advance relative to it.
                self.focus_advance_requested.emit(self._btn_dark)

            self._update_enabled_state(theme)

            # Focus behavior:
            # - Selecting Light keeps focus within the toggle by moving focus
            #   to Dark (the next option).
            # - Selecting Dark advances focus out of the toggle group.
            if theme == Theme.LIGHT:
                # After enabling Dark, move focus to it.
                self._btn_dark.setFocus()

            self.theme_changed.emit(theme)



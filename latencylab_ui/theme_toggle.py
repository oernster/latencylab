from __future__ import annotations

"""One button that switches between the light and the dark theme."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QWidget

from latencylab_ui.theme import Theme

# The button names the theme it will switch TO, not the one already in force. A
# control captioned with its own current state reads as an indicator rather than
# something to press, and there is nowhere for a single button to put both.
_CAPTION = {Theme.DARK: "☀", Theme.LIGHT: "🌙"}
_TOOLTIP = {
    Theme.DARK: "Switch to the light theme",
    Theme.LIGHT: "Switch to the dark theme",
}

_OTHER = {Theme.DARK: Theme.LIGHT, Theme.LIGHT: Theme.DARK}


class ThemeToggle(QPushButton):
    """A single always-enabled toggle between the two themes.

    It replaces a pair of buttons that disabled whichever theme was in force.
    That made the ACTIVE theme the dead control, so under the three-state ring
    model it wore the permanent red danger ring: the one thing on screen that
    was working correctly was the one thing painted as broken. A single button
    that is never disabled has no such state to get wrong, and it is one stop on
    the keyboard ring instead of two, one of which could never be reached.
    """

    theme_changed = Signal(Theme)

    def __init__(
        self, *, default: Theme = Theme.DARK, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "theme-toggle")
        self._theme = default
        self._paint(default)
        self.clicked.connect(self._on_clicked)

    def theme(self) -> Theme:
        """The theme currently in force."""

        return self._theme

    def next_theme(self) -> Theme:
        """The theme this button will switch to, which is what it is captioned."""

        return _OTHER[self._theme]

    def set_theme(self, theme: Theme) -> None:
        """Adopt `theme` and announce it."""

        self._theme = theme
        self._paint(theme)
        self.theme_changed.emit(theme)

    def _on_clicked(self) -> None:
        self.set_theme(self.next_theme())

    def _paint(self, theme: Theme) -> None:
        self.setText(_CAPTION[theme])
        self.setToolTip(_TOOLTIP[theme])

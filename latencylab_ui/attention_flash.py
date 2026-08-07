from __future__ import annotations

"""A control that has just become usable, saying so, briefly, then stopping.

Loading a model changes what the application can do, and the change happens on
the far side of the window from where the user was looking: the path label
updates on the left, while the thing to press next is the Run button. This
draws the eye there once and then gets out of the way.

Deliberately finite. A pulse that continues until it is obeyed is a nag, and
the user who has read it has no way to say so; two flashes are enough to catch
peripheral vision and few enough to be over before they become the thing you
are trying to ignore. The pause between them is long on purpose, so it reads as
a surfacing rather than a blink.

The colour is not chosen here. The flash sets a property and the stylesheet
paints it in the same green the ring uses for hover and focus, which already
means "you can use this": the button has just become usable, so it is the same
statement, made without being asked.
"""

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

# How many times the border appears. See the module docstring: this is a
# deliberate ceiling, not a default to be raised later.
FLASH_COUNT = 2

# How long the border stays visible each time.
FLASH_ON_MS = 450

# Start to start, so lengthening the lit time does not silently shorten the
# gap. The gap itself is derived rather than written down twice.
FLASH_INTERVAL_MS = 1750
FLASH_OFF_MS = FLASH_INTERVAL_MS - FLASH_ON_MS

# The dynamic property the stylesheet selects on. Qt renders a bool property as
# "true"/"false", so the sheet matches [flash="true"].
FLASH_PROPERTY = "flash"


class AttentionFlash(QObject):
    """Flashes one widget's border a fixed number of times, then stops."""

    def __init__(self, widget: QWidget) -> None:
        super().__init__(widget)
        self._widget = widget
        self._lit = False
        self._remaining = 0

        # Single-shot and re-armed rather than repeating, so the lit and unlit
        # halves can have different lengths without a counter deciding which
        # half a tick belongs to.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        """Begin the sequence, restarting it if one is already running.

        A disabled widget is left alone. Pointing at a control that cannot be
        used says the opposite of what this is for, and it would collide with
        the red ring that is already explaining why it cannot.
        """

        self.stop()
        if not self._widget.isEnabled():
            return
        self._remaining = FLASH_COUNT
        self._begin_flash()

    def stop(self) -> None:
        """Cancel any sequence in progress and leave the border unlit."""

        self._timer.stop()
        self._remaining = 0
        self._set_lit(False)

    def is_lit(self) -> bool:
        """Whether the border is currently painted."""

        return self._lit

    def _begin_flash(self) -> None:
        self._remaining -= 1
        self._set_lit(True)
        self._timer.start(FLASH_ON_MS)

    def _advance(self) -> None:
        if self._lit:
            self._set_lit(False)
            if self._remaining > 0:
                self._timer.start(FLASH_OFF_MS)
            return
        # A finished sequence stays finished. Without this guard the state
        # machine relights on any tick that arrives after the last flash, so
        # the ceiling would hold only because nothing happened to fire one.
        if self._remaining <= 0:
            return
        self._begin_flash()

    def _set_lit(self, lit: bool) -> None:
        self._lit = lit
        self._widget.setProperty(FLASH_PROPERTY, lit)
        # A dynamic property does not repaint on its own: Qt has already
        # resolved the stylesheet for this widget and will not reconsider until
        # it is asked to.
        style = self._widget.style()
        style.unpolish(self._widget)
        style.polish(self._widget)

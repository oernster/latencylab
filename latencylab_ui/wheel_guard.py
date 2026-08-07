from __future__ import annotations

"""Scrolling past a control must not change it.

Qt gives the wheel to whatever sits under the pointer, and a combo box or a
spin box accepts it whether or not it has focus. Inside a scrolling panel that
is not a small annoyance: dragging the wheel down the Model Composer walked
through every context's concurrency and every task's distribution on the way
past, silently rewriting the model the user was only trying to read.

The rule is that a control changes when it has been chosen, not when it has
been travelled over. A focused control keeps its wheel, because at that point
the wheel is being aimed at it rather than passing through.

The event is forwarded to the enclosing scroll area rather than swallowed. A
guard that only blocked the change would leave the pointer over a dead patch of
a scrolling panel, which reads as the application having frozen.

Installed once on the application rather than per control. The composer builds
and destroys cards as tasks are added and removed, so anything installed per
widget would protect the controls that existed when it ran and quietly miss
every one created afterwards.
"""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QWidget,
)

# The controls that read the wheel as INPUT rather than as navigation. A list
# or a text view is the thing being scrolled, and a text field ignores the
# wheel already, so neither belongs here.
WHEEL_HUNGRY = (QComboBox, QAbstractSpinBox)


class WheelGuard(QObject):
    """Denies the wheel to an unfocused control and scrolls the panel instead."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.Wheel:
            return False
        if not isinstance(watched, WHEEL_HUNGRY):
            return False
        if not isinstance(watched, QWidget) or watched.hasFocus():
            return False

        area = enclosing_scroll_area(watched)
        if area is not None:
            QApplication.sendEvent(area.viewport(), event)
        return True


def enclosing_scroll_area(widget: QWidget) -> QAbstractScrollArea | None:
    """The scrolling panel this control sits in, if any.

    Walks up rather than reading the immediate parent, because the controls sit
    several layouts deep inside the composer's scroll area.
    """

    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


def install_wheel_guard(app: QApplication) -> WheelGuard:
    """Protect every wheel-hungry control in the application, now and later."""

    guard = WheelGuard(app)
    app.installEventFilter(guard)
    return guard

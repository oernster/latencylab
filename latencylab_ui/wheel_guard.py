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

Blocking the wheel is not on its own enough, because Qt gives these controls
`WheelFocus` by default, which means the wheel FOCUSES them before it reaches
them. So travelling over one both stole the keyboard focus and left the control
focused, and a focused control is exactly the case this guard deliberately hands
its wheel back to. The two reported faults, values changing and focus getting
stuck, were the same fault seen from either end. The policy is therefore
narrowed to remove the wheel from it, which is what makes the rule below true
rather than merely stated.

Forwarding also has to skip an ancestor that cannot move. A spin box in a table
sits inside the TABLE's scroll area, so the nearest ancestor absorbed the wheel
and the panel the user was actually reading never moved: the same dead patch,
reached the other way. The event goes to the first ancestor that can consume it
on the axis the wheel was turned.

Installed once on the application rather than per control. The composer builds
and destroys cards as tasks are added and removed, so anything installed per
widget would protect the controls that existed when it ran and quietly miss
every one created afterwards.
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
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

# `Qt.FocusPolicy` is a bit set and `WheelFocus` is `StrongFocus` plus one more
# bit. Derived from the two rather than written down, so it cannot drift from
# whatever Qt actually numbers them.
WHEEL_FOCUS_BIT = Qt.FocusPolicy.WheelFocus.value & ~Qt.FocusPolicy.StrongFocus.value


class WheelGuard(QObject):
    """Denies the wheel to an unfocused control and scrolls the panel instead."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Polish:
            deny_wheel_focus(watched)
            return False
        if event.type() != QEvent.Type.Wheel:
            return False
        if not isinstance(watched, WHEEL_HUNGRY):
            return False
        if not isinstance(watched, QWidget) or watched.hasFocus():
            return False

        area = enclosing_scroll_area(watched, vertical=turned_vertically(event))
        if area is not None:
            QApplication.sendEvent(area.viewport(), event)
        return True


def deny_wheel_focus(widget: QObject) -> bool:
    """Take the wheel out of a control's focus policy, leaving the rest intact.

    Narrowed rather than replaced: a control set to `NoFocus` or `ClickFocus`
    keeps that, because the only claim being made here is that scrolling past
    something is not a way of choosing it.
    """

    if not isinstance(widget, WHEEL_HUNGRY) or not isinstance(widget, QWidget):
        return False
    policy = widget.focusPolicy()
    if not policy.value & WHEEL_FOCUS_BIT:
        return False
    widget.setFocusPolicy(Qt.FocusPolicy(policy.value & ~WHEEL_FOCUS_BIT))
    return True


def turned_vertically(event: QWheelEvent) -> bool:
    """Which axis the wheel was turned on, ties going to the vertical.

    A plain wheel reports only a vertical delta, so the tie is the common case.
    """

    delta = event.angleDelta()
    return abs(delta.y()) >= abs(delta.x())


def enclosing_scroll_area(
    widget: QWidget, vertical: bool = True
) -> QAbstractScrollArea | None:
    """The nearest scrolling panel this control sits in that can actually move.

    Walks up rather than reading the immediate parent, because the controls sit
    several layouts deep inside the composer's scroll area. An ancestor with
    nothing to scroll is passed over rather than handed the event, since giving
    the wheel to something that cannot use it is indistinguishable to the user
    from swallowing it.
    """

    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea) and can_scroll(parent, vertical):
            return parent
        parent = parent.parentWidget()
    return None


def can_scroll(area: QAbstractScrollArea, vertical: bool) -> bool:
    """Whether this panel has anywhere to go on the axis the wheel was turned."""

    bar = area.verticalScrollBar() if vertical else area.horizontalScrollBar()
    return bar.maximum() > bar.minimum()


def install_wheel_guard(app: QApplication) -> WheelGuard:
    """Protect every wheel-hungry control in the application, now and later."""

    guard = WheelGuard(app)
    app.installEventFilter(guard)
    # Anything already built has had its Polish event and will not see another,
    # so the filter alone would start one generation late.
    for widget in app.allWidgets():
        deny_wheel_focus(widget)
    return guard

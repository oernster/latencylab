from __future__ import annotations

"""Event-level helpers for the focus cycle, kept out of the controller.

Everything here answers a question about a single event or a single widget:
"is this a hover over the menu bar", "should Enter click this", "where is the
nearest button ancestor". None of it needs the traversal chain, and separating
it leaves `focus_cycle.py` holding one idea: the order things are visited in.
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QMainWindow,
    QWidget,
)

# The pointer events that make a menu bar open a dropdown on its own.
_HOVER_EVENTS = (
    QEvent.Type.Enter,
    QEvent.Type.HoverEnter,
    QEvent.Type.HoverMove,
    QEvent.Type.MouseMove,
)


def nearest_ancestor(w: QWidget, cls: type[QWidget]) -> QWidget | None:
    """The closest ancestor of `w` (including itself) that is a `cls`."""
    cur: QWidget | None = w
    while cur is not None:
        if isinstance(cur, cls):
            return cur
        cur = cur.parentWidget()
    return None


def focus_within_any(w: QWidget, classes: tuple[type[QWidget], ...]) -> bool:
    """Whether `w` sits inside any of `classes`."""
    cur: QWidget | None = w
    while cur is not None:
        if isinstance(cur, classes):
            return True
        cur = cur.parentWidget()
    return False


def is_menu_hover(window: QMainWindow, watched: object, event: QEvent) -> bool:
    """Whether this event is the pointer arriving over the window's menu bar."""
    return watched is window.menuBar() and event.type() in _HOVER_EVENTS


def suppress_menu_hover(window: QMainWindow) -> bool:
    """Stop a hover opening a dropdown, and say whether the event was consumed.

    A menu title can be active purely because keyboard traversal put it there.
    Left alone, moving the pointer across the bar then opens that menu, which is
    not what the user asked for. Clearing the active action is not enough on its
    own: the event has to be swallowed too, or the bar re-activates the action
    and opens the dropdown anyway.

    Returns False when a popup is already open, because the user opened it
    deliberately and the event belongs to Qt.
    """
    if QApplication.activePopupWidget() is not None:
        return False
    window.menuBar().setActiveAction(None)
    return True


def activate_focused_button(window: QMainWindow) -> bool | None:
    """Make Enter click a focused button, the way Space already does.

    Qt triggers a button on Space but not consistently on Enter across
    platforms and styles, so it is normalised here.

    Three answers, because the caller has three things to do: True when the
    event is consumed, False when it belongs to an input widget and must be
    passed on untouched, and None when this is not an activation at all and the
    caller should carry on to traversal.
    """
    fw = QApplication.focusWidget()
    if fw is None or fw.window() is not window:
        return None

    # Never override input widgets: Enter means something else inside a combo
    # box or a spin box.
    if focus_within_any(fw, (QComboBox, QAbstractSpinBox)):
        return False

    btn = nearest_ancestor(fw, QAbstractButton)
    if btn is None or not btn.isEnabled() or not btn.isVisibleTo(window):
        return None
    try:
        btn.click()
    except RuntimeError:  # pragma: no cover
        return True  # pragma: no cover
    return True


def dismiss_active_popup() -> None:
    """Close any open dropdown, so traversal can leave the menu.

    `close()` and `hide()` are unreliable on some platforms, so Escape is sent
    to the popup first: that is the signal the menu itself acts on. The direct
    calls follow as a belt-and-braces second attempt.
    """
    popup = QApplication.activePopupWidget()
    if popup is None:
        return
    try:
        QApplication.sendEvent(
            popup,
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.NoModifier),
        )
        QApplication.sendEvent(
            popup,
            QKeyEvent(QKeyEvent.Type.KeyRelease, Qt.Key.Key_Escape, Qt.NoModifier),
        )
        popup.hide()
        popup.close()
    except RuntimeError:  # pragma: no cover
        pass

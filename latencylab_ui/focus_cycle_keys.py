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

from latencylab_ui import focus_cycle_menu as menus
from latencylab_ui.focus_cycle_widgets import is_text_entry

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


def handle_space(window: QMainWindow, key: Qt.Key) -> bool:
    """Make Space mean what it means everywhere else, inside the menus too.

    Qt already fires a focused button on Space. What it does not do is activate
    a highlighted MENU item (its Windows styles leave that hint off) or drop a
    highlighted menu title, so Enter worked in the menus and Space silently did
    nothing at all.

    The title branch cannot be reached under the offscreen platform the tests
    run on: activating a menu title there pops its menu open immediately, by
    any route, so "highlighted but closed" is a state that cannot be built. The
    work it delegates to is covered directly instead.
    """

    if key != Qt.Key.Key_Space:
        return False

    popup = menus.active_popup_menu()
    if popup is not None:
        return menus.trigger_highlighted_item(popup)
    if window.menuBar().activeAction() is not None:
        return menus.open_menu_under_title(window)  # pragma: no cover - see above
    return False


def handle_combo_box(key: Qt.Key) -> bool:
    """Down drops a closed combo box open; it must never change its value.

    Qt's default walks the selection with the arrows while the popup is shut,
    so a user stepping the ring silently changes the current run just by
    pressing Down on it. Down opens the list instead, and Up on a closed box is
    swallowed rather than allowed to do the same damage in the other direction.

    There is deliberately no "is the list already open" check. Opening a combo
    box moves focus to its popup VIEW, so the focused widget is no longer the
    box and this returns above; the arrows reach the open list untouched. A
    guard for a case that cannot arise is a guard nobody can test.
    """

    if key not in (Qt.Key.Key_Down, Qt.Key.Key_Up):
        return False

    focused = QApplication.focusWidget()
    if focused is None or is_text_entry(focused):
        return False
    if not isinstance(focused, QComboBox) or not focused.isEnabled():
        return False
    if key == Qt.Key.Key_Down:
        focused.showPopup()
    return True


def horizontal_arrow_belongs_elsewhere(*, forward: bool) -> bool:
    """Whether Left or Right means something other than stepping the ring.

    Only two things can claim them. A text field owns them for the caret, and
    Tab is how you leave one; taking them away would make the spin boxes
    uneditable, which is a steep price for a traversal shortcut. An open menu
    owns Right into a submenu and Left back out of one, and nothing else.
    """

    focused = QApplication.focusWidget()
    if focused is not None and is_text_entry(focused):
        return True

    popup = menus.active_popup_menu()
    return popup is not None and menus.should_yield_horizontal(popup, forward=forward)


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

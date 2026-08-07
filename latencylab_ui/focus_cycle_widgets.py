from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QDockWidget,
    QLayout,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QWidget,
)

# Widgets whose own arrow keys mean "move the caret". They are left alone: a
# text field is left with Tab, never with the arrows; otherwise editing it becomes
# impossible.
_TEXT_ENTRY_TYPES = (QLineEdit, QAbstractSpinBox)

# A table or list is ONE stop, never one per cell: its rows are walked with the
# vertical arrows and Tab leaves it in a single press. See `is_interactive_widget`
# for the condition that keeps a table with nothing to choose off the ring.
_RING_TYPES = (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QAbstractItemView,
)


def collect_interactive_widgets_in_layout_order(window: QMainWindow) -> list[QWidget]:
    """Every ring stop in the window, in the order the eye meets them.

    The central widget first, then each VISIBLE dock. Docks are siblings of the
    central widget rather than children of it, so a walk that starts and ends
    there reaches none of their controls: with the Model Composer open, every
    control in it was unreachable from the keyboard, measured at zero.

    Hidden docks are skipped rather than filtered later, so the ring is exactly
    what is on screen at the moment the key was pressed.
    """

    out: list[QWidget] = []
    seen: set[int] = set()
    walk_widget_for_interactive(window, window.centralWidget(), out, seen)

    for dock in window.findChildren(QDockWidget):
        if dock.isVisible():
            walk_widget_for_interactive(window, dock.widget(), out, seen)
    return out


def is_text_entry(w: QWidget) -> bool:
    """Whether this widget (or an ancestor) owns its arrow keys for editing.

    A spin box is a line edit with buttons welded on, so focus usually lands on
    the inner editor rather than the spin box itself. The walk upwards is what
    makes the caret work in practice.
    """

    cur: QWidget | None = w
    while cur is not None:
        if isinstance(cur, _TEXT_ENTRY_TYPES):
            return True
        cur = cur.parentWidget()
    return False


def scrolls_vertically(w: QWidget) -> bool:
    """Whether a scroll area currently has anything to scroll.

    A pane that fits its viewport scrolls nowhere, so focusing it lets the user
    do nothing at all: it fails the actionable test and is not a stop. The ring
    is rebuilt on every move, so the same pane counts or does not according to
    the window size at that moment.
    """

    if not isinstance(w, QAbstractScrollArea):
        return False
    bar = w.verticalScrollBar()
    return bar is not None and bar.maximum() > 0


def is_interactive_widget(window: QMainWindow, w: QWidget) -> bool:
    if not isinstance(w, _RING_TYPES):
        return False
    if not w.isVisibleTo(window) or not w.isEnabled():
        return False
    if w.focusPolicy() == Qt.FocusPolicy.NoFocus:
        return False
    if isinstance(w, QPlainTextEdit):
        # A read-only output pane earns a place on the ring only while it
        # overflows, then only to be scrolled. Without this the run output
        # cannot be reached from the keyboard at all; with it unconditionally,
        # the ring stalls on panes that have nothing to show.
        return w.isReadOnly() is False or scrolls_vertically(w)
    if isinstance(w, QAbstractItemView):
        # An empty table or list can neither be scrolled nor selected within, so
        # focusing it lets the user do nothing: it is not a stop until it has a
        # row. Selecting a row IS the consequence that makes it actionable,
        # because that is what arms the Remove buttons beside it.
        return w.model() is not None and w.model().rowCount() > 0
    return True


def maybe_add_interactive_widget(
    window: QMainWindow,
    w: QWidget,
    out: list[QWidget],
    seen: set[int],
) -> None:
    if id(w) in seen:
        return
    if not is_interactive_widget(window, w):
        return
    seen.add(id(w))
    out.append(w)


def walk_layout_for_interactive(
    window: QMainWindow,
    layout: QLayout,
    out: list[QWidget],
    seen: set[int],
) -> None:
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item is None:  # pragma: no cover
            continue
        if item.widget() is not None:
            walk_widget_for_interactive(window, item.widget(), out, seen)
        elif item.layout() is not None:
            walk_layout_for_interactive(window, item.layout(), out, seen)


def declared_ring_stops(w: QWidget) -> tuple[QWidget, ...] | None:
    """A container's own reading order, where its layout is not in that order.

    Layout order is the right default and is what the eye follows almost
    everywhere. It is wrong the moment a container OVERLAYS one child on
    another, because an overlay has no position in the row it covers: the top
    bar centres the application mark on the whole bar by putting it in the same
    grid cell as the row of buttons, so the layout reaches it last however far
    left it is drawn. Such a container says what its order is; everything else
    is walked exactly as before.
    """

    stops = getattr(w, "ring_stops", None)
    return tuple(stops()) if callable(stops) else None


def walk_widget_for_interactive(
    window: QMainWindow,
    w: QWidget | None,
    out: list[QWidget],
    seen: set[int],
) -> None:
    if w is None:
        return

    maybe_add_interactive_widget(window, w, out, seen)

    declared = declared_ring_stops(w)
    if declared is not None:
        for stop in declared:
            walk_widget_for_interactive(window, stop, out, seen)
        return

    if w.layout() is not None:
        walk_layout_for_interactive(window, w.layout(), out, seen)
        return

    if isinstance(w, QSplitter):
        for idx in range(w.count()):
            walk_widget_for_interactive(window, w.widget(idx), out, seen)
        return

    if isinstance(w, QScrollArea):
        walk_widget_for_interactive(window, w.widget(), out, seen)
        return

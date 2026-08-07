from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QLayout,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QWidget,
)

# Widgets whose own arrow keys mean "move the caret". They are left alone: a
# text field is left with Tab, never with the arrows, or editing it becomes
# impossible.
_TEXT_ENTRY_TYPES = (QLineEdit, QAbstractSpinBox)

_RING_TYPES = (QAbstractButton, QAbstractSpinBox, QComboBox, QPlainTextEdit)


def collect_interactive_widgets_in_layout_order(window: QMainWindow) -> list[QWidget]:
    out: list[QWidget] = []
    seen: set[int] = set()
    walk_widget_for_interactive(window, window.centralWidget(), out, seen)
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
        # overflows, and then only to be scrolled. Without this the run output
        # cannot be reached from the keyboard at all; with it unconditionally,
        # the ring stalls on panes that have nothing to show.
        return w.isReadOnly() is False or scrolls_vertically(w)
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


def walk_widget_for_interactive(
    window: QMainWindow,
    w: QWidget | None,
    out: list[QWidget],
    seen: set[int],
) -> None:
    if w is None:
        return

    maybe_add_interactive_widget(window, w, out, seen)

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

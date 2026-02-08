from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QLayout,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QWidget,
)


def collect_interactive_widgets_in_layout_order(window: QMainWindow) -> list[QWidget]:
    out: list[QWidget] = []
    seen: set[int] = set()
    walk_widget_for_interactive(window, window.centralWidget(), out, seen)
    return out


def is_interactive_widget(window: QMainWindow, w: QWidget) -> bool:
    if isinstance(w, QPlainTextEdit):
        return False
    if not isinstance(w, (QAbstractButton, QAbstractSpinBox, QComboBox)):
        return False
    if not w.isVisibleTo(window) or not w.isEnabled():
        return False
    if w.focusPolicy() == Qt.FocusPolicy.NoFocus:
        return False
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


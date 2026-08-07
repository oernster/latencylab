from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from latencylab_ui import focus_cycle_widgets as ring
from latencylab_ui.main_window import MainWindow


class _IdleController(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    finished = Signal(int, float)

    def is_running(self) -> bool:
        return False

    def is_cancelled(self, run_token: int) -> bool:
        return False

    def shutdown(self) -> None:
        return None


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication) -> MainWindow:
    win = MainWindow(run_controller=_IdleController())
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def _settle(app: QApplication) -> None:
    for _ in range(10):
        app.processEvents()


def _dock_stops(window: MainWindow) -> list:
    dock = window._model_composer_dock
    return [
        stop
        for stop in ring.collect_interactive_widgets_in_layout_order(window)
        if dock.isAncestorOf(stop)
    ]


def test_the_composer_dock_was_entirely_unreachable_and_is_not_now(
    app: QApplication, window: MainWindow
) -> None:
    """The measured gap: with the composer open, zero of it was on the ring.

    A dock is a SIBLING of the central widget, not a child, so a walk that
    starts and ends at the central widget reaches none of it. Every control in
    the Model Composer was unreachable from the keyboard.
    """

    closed = len(ring.collect_interactive_widgets_in_layout_order(window))
    assert _dock_stops(window) == []

    window._model_composer_dock.setVisible(True)
    _settle(app)

    opened = ring.collect_interactive_widgets_in_layout_order(window)
    assert len(_dock_stops(window)) > 0
    assert len(opened) > closed

    # Everything the central widget offered is still there and still first: the
    # dock extends the ring rather than replacing part of it.
    assert [
        stop for stop in opened if not window._model_composer_dock.isAncestorOf(stop)
    ]


def test_closing_the_composer_takes_its_controls_off_the_ring(
    app: QApplication, window: MainWindow
) -> None:
    """The ring is what is on screen NOW, not what has ever been on screen."""

    before = len(ring.collect_interactive_widgets_in_layout_order(window))

    window._model_composer_dock.setVisible(True)
    _settle(app)
    assert len(ring.collect_interactive_widgets_in_layout_order(window)) > before

    window._model_composer_dock.setVisible(False)
    _settle(app)
    assert len(ring.collect_interactive_widgets_in_layout_order(window)) == before


def test_the_composer_text_fields_are_reachable(
    app: QApplication, window: MainWindow
) -> None:
    """A text field nobody can Tab to is a text field nobody can fill in."""

    window._model_composer_dock.setVisible(True)
    _settle(app)

    assert [stop for stop in _dock_stops(window) if isinstance(stop, QLineEdit)]


def test_the_composer_buttons_are_reachable(
    app: QApplication, window: MainWindow
) -> None:
    window._model_composer_dock.setVisible(True)
    _settle(app)

    captions = {
        stop.text() for stop in _dock_stops(window) if isinstance(stop, QPushButton)
    }
    assert "Validate Model" in captions
    assert "Add context" in captions
    assert "Export JSON…" in captions


def test_a_table_is_one_stop_rather_than_one_per_cell(
    app: QApplication, window: MainWindow
) -> None:
    """Qt's default spends a Tab press per CELL.

    A two-column table then costs two presses to cross and turns its read-only
    cells into dead stops. The table is one stop; its rows are walked with the
    vertical arrows.
    """

    window._model_composer_dock.setVisible(True)
    _settle(app)

    tables = [stop for stop in _dock_stops(window) if isinstance(stop, QTableWidget)]
    assert tables, "the contexts table should be on the ring"

    for table in tables:
        assert table.tabKeyNavigation() is False
        assert _dock_stops(window).count(table) == 1


def test_an_empty_table_or_list_is_not_a_stop_at_all(
    app: QApplication, window: MainWindow
) -> None:
    """Focus that lets the user do nothing is not a stop.

    An empty list cannot be scrolled and has no row to select, so selecting
    within it has no consequence: it fails every actionable test there is.
    """

    from PySide6.QtWidgets import QListWidget

    window._model_composer_dock.setVisible(True)
    _settle(app)

    # The wiring editor's real listeners list, not a parentless stand-in: an
    # orphan widget is not visible to the window and would be skipped for that
    # reason instead of for the emptiness this is about.
    lists = window._model_composer_dock.findChildren(QListWidget)
    assert lists, "the wiring editor should own a listeners list"
    listeners = lists[0]

    assert isinstance(listeners, QAbstractItemView)
    assert listeners.count() == 0
    assert ring.is_interactive_widget(window, listeners) is False
    assert listeners not in _dock_stops(window)

    listeners.addItem("something to choose")
    _settle(app)
    assert ring.is_interactive_widget(window, listeners) is True
    assert listeners in _dock_stops(window)


def test_a_hidden_dock_contributes_nothing(
    app: QApplication, window: MainWindow
) -> None:
    """Skipped while hidden rather than collected and filtered afterwards."""

    window._distributions_dock.setVisible(False)
    window._model_composer_dock.setVisible(False)
    _settle(app)

    stops = ring.collect_interactive_widgets_in_layout_order(window)
    for dock in (window._distributions_dock, window._model_composer_dock):
        assert not any(dock.isAncestorOf(stop) for stop in stops)

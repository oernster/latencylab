from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QWidget,
)

from latencylab_ui import focus_cycle_widgets as ring
from latencylab_ui.main_window import MainWindow
from latencylab_ui.model_composer_tree import CONTEXTS, SYSTEM, TASKS, WIRING


class _IdleController(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
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


def _open_composer(app: QApplication, window: MainWindow, section: str):
    """The composer up and showing one section, without a modal event loop."""

    composer = window._model_composer
    composer.show()
    composer._tree.select_section(section)
    _settle(app)
    return composer


def _dialog_stops(dialog: QWidget) -> list[QWidget]:
    """Every control the dialog's own Tab chain reaches, in order.

    Walked along the toolkit's OWN focus chain rather than over the child list,
    for the same reason `FirstStopDialog.first_stop` is: the answer wanted is
    exactly what Tab would give, not a second opinion about it. The seen-set is
    not optional, because the chain is circular.
    """

    stops: list[QWidget] = []
    seen: set[int] = set()
    widget = dialog.nextInFocusChain()
    while widget is not None and id(widget) not in seen:
        seen.add(id(widget))
        if (
            widget is not dialog
            and dialog.isAncestorOf(widget)
            and widget.isEnabled()
            and widget.isVisible()
            and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
        ):
            stops.append(widget)
        widget = widget.nextInFocusChain()
    return stops


def test_the_composer_is_reached_as_a_dialog_not_through_the_window_ring(
    app: QApplication, window: MainWindow
) -> None:
    """It used to be a dock, which is a SIBLING of the central widget rather
    than a child, so the window's ring had to be taught to walk into it. A
    dialog is a window of its own and owns its focus, so the main ring stays
    exactly what the main window offers whether the composer is up or not."""

    closed = ring.collect_interactive_widgets_in_layout_order(window)

    composer = _open_composer(app, window, SYSTEM)

    opened = ring.collect_interactive_widgets_in_layout_order(window)
    assert opened == closed
    assert not any(composer.isAncestorOf(stop) for stop in opened)


def test_the_composer_opens_focused_on_its_first_control(
    app: QApplication, window: MainWindow
) -> None:
    """A dialog was opened on purpose, to do the one thing it is for, so making
    the user press Tab before anything is focused tells them nothing."""

    composer = _open_composer(app, window, SYSTEM)

    focused = QApplication.focusWidget()
    assert focused is not None
    assert composer.isAncestorOf(focused)


def test_the_composer_text_fields_are_reachable(
    app: QApplication, window: MainWindow
) -> None:
    """A text field nobody can Tab to is a text field nobody can fill in."""

    composer = _open_composer(app, window, SYSTEM)

    assert [stop for stop in _dialog_stops(composer) if isinstance(stop, QLineEdit)]


def test_the_composer_buttons_are_reachable(
    app: QApplication, window: MainWindow
) -> None:
    """Validate and Export sit under both panes, so they are reachable from
    whichever section is showing."""

    composer = _open_composer(app, window, CONTEXTS)

    captions = {
        stop.text() for stop in _dialog_stops(composer) if isinstance(stop, QPushButton)
    }
    assert "Validate Model" in captions
    assert "Export JSON…" in captions
    assert "Add context" in captions


def test_the_section_list_is_itself_a_stop(
    app: QApplication, window: MainWindow
) -> None:
    """The pane that chooses what the other pane shows has to be reachable, or
    the keyboard can edit one section and never leave it."""

    composer = _open_composer(app, window, SYSTEM)

    assert composer._tree in _dialog_stops(composer)


def test_a_table_is_one_stop_rather_than_one_per_cell(
    app: QApplication, window: MainWindow
) -> None:
    """Qt's default spends a Tab press per CELL.

    A two-column table then costs two presses to cross and turns its read-only
    cells into dead stops. The table is one stop; its rows are walked with the
    vertical arrows.
    """

    composer = _open_composer(app, window, CONTEXTS)

    stops = _dialog_stops(composer)
    tables = [stop for stop in stops if isinstance(stop, QTableWidget)]
    assert tables, "the contexts table should be reachable"

    for table in tables:
        assert table.tabKeyNavigation() is False
        assert stops.count(table) == 1


def test_an_empty_list_is_not_a_stop_at_all(
    app: QApplication, window: MainWindow
) -> None:
    """Focus that lets the user do nothing is not a stop.

    An empty list cannot be scrolled and has no row to select, so selecting
    within it has no consequence: it fails every actionable test there is.
    """

    composer = _open_composer(app, window, WIRING)

    lists = composer.findChildren(QListWidget)
    assert lists, "the wiring editor should own a listeners list"
    listeners = lists[0]

    assert isinstance(listeners, QAbstractItemView)
    assert listeners.count() == 0
    assert ring.is_interactive_widget(composer, listeners) is False

    listeners.addItem("something to choose")
    _settle(app)
    assert ring.is_interactive_widget(composer, listeners) is True


def test_only_the_showing_section_is_on_the_dialog_ring(
    app: QApplication, window: MainWindow
) -> None:
    """One pane shows one thing, so Tab reaches the controls of that thing.

    This is the point of the two panes: the ring used to run through every
    control of every section, because every section was on screen at once.
    """

    composer = _open_composer(app, window, CONTEXTS)
    on_contexts = {
        stop.text() for stop in _dialog_stops(composer) if isinstance(stop, QPushButton)
    }

    composer._tree.select_section(TASKS)
    _settle(app)
    on_tasks = {
        stop.text() for stop in _dialog_stops(composer) if isinstance(stop, QPushButton)
    }

    assert "Add context" in on_contexts
    assert "Add context" not in on_tasks
    assert "Add task" in on_tasks


def test_a_hidden_dock_contributes_nothing(
    app: QApplication, window: MainWindow
) -> None:
    """Skipped while hidden rather than collected and filtered afterwards."""

    window._distributions_dock.setVisible(False)
    _settle(app)

    stops = ring.collect_interactive_widgets_in_layout_order(window)
    assert not any(window._distributions_dock.isAncestorOf(stop) for stop in stops)

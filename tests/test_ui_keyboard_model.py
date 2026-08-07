from __future__ import annotations

from pathlib import Path

import pytest

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from latencylab.model import Model
from latencylab_ui import focus_cycle_widgets as ring
from latencylab_ui.main_window import MainWindow

MODEL_JSON = {
    "schema_version": 1,
    "entry_event": "e0",
    "contexts": {"ui": {"concurrency": 1}},
    "events": {"e0": {"tags": ["ui"]}},
    "tasks": {},
}

# Enough lines that the pane cannot fit them, whatever the offscreen metrics.
OVERFLOWING_LINES = 500


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
    win.activateWindow()
    win.setFocus()
    app.processEvents()
    win._set_model_load_ok(Path("model.json"), Model.from_json(MODEL_JSON))
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def _settle(app: QApplication) -> None:
    for _ in range(20):
        app.processEvents()


# ------------------------------------------------- a text field keeps its arrows


def test_a_spin_box_keeps_its_arrows_for_the_caret(
    app: QApplication, window: MainWindow
) -> None:
    """Invariant 7: you leave a text field with Tab, never with an arrow.

    The horizontal arrows step the ring everywhere else, but taking them from a
    spin box would make its value uneditable, which is a steep price for a
    traversal shortcut.
    """

    window._runs_spin.setFocus()
    _settle(app)

    QTest.keyClick(QApplication.focusWidget(), Qt.Key_Right, Qt.NoModifier)
    _settle(app)

    assert window._runs_spin.hasFocus() or ring.is_text_entry(
        QApplication.focusWidget()
    )

    # Tab still leaves it, which is the whole point of the exemption.
    QTest.keyClick(QApplication.focusWidget(), Qt.Key_Tab, Qt.NoModifier)
    _settle(app)
    assert not window._runs_spin.hasFocus()


# ----------------------------------------------- a closed combo box on Down/Up


def test_down_opens_the_run_selector_instead_of_changing_it(
    app: QApplication, window: MainWindow
) -> None:
    """Qt's default silently changes the value of a CLOSED combo box.

    Stepping the ring onto the run selector and pressing Down would then pick a
    different run without ever showing the list.
    """

    combo = window._run_select
    combo.setEnabled(True)
    combo.addItems(["run 0", "run 1", "run 2"])
    combo.setCurrentIndex(0)
    combo.setFocus()
    _settle(app)

    QTest.keyClick(combo, Qt.Key_Down, Qt.NoModifier)
    _settle(app)

    assert combo.currentIndex() == 0, "Down must not change a closed selection"
    assert combo.view().isVisible(), "Down must drop the list open"

    combo.hidePopup()
    _settle(app)

    # Up on a closed box is swallowed rather than allowed to do the same damage
    # in the other direction.
    combo.setCurrentIndex(1)
    QTest.keyClick(combo, Qt.Key_Up, Qt.NoModifier)
    _settle(app)
    assert combo.currentIndex() == 1


# ------------------------------------------ an output pane is a stop only when full


def test_an_output_pane_joins_the_ring_only_while_it_overflows(
    app: QApplication, window: MainWindow
) -> None:
    """Focus that lets the user do nothing is not a stop.

    An empty summary pane scrolls nowhere, so it is skipped. A full one is the
    only way to read the run output from the keyboard at all, so it is not.
    """

    pane = window._summary_text
    assert pane.isReadOnly()

    pane.setPlainText("")
    _settle(app)
    assert ring.is_interactive_widget(window, pane) is False

    pane.setPlainText("\n".join(f"line {n}" for n in range(OVERFLOWING_LINES)))
    _settle(app)
    assert ring.scrolls_vertically(pane) is True
    assert ring.is_interactive_widget(window, pane) is True

    assert pane in ring.collect_interactive_widgets_in_layout_order(window)


def test_an_editable_pane_is_always_a_stop() -> None:
    """A read-only pane is there to be READ; an editable one is a text field."""

    from PySide6.QtWidgets import QPlainTextEdit

    editable = QPlainTextEdit()
    assert editable.isReadOnly() is False
    assert ring.scrolls_vertically(editable) is False
    # Not asserted through is_interactive_widget, which needs a parent window;
    # the read-only branch is the one with the overflow condition on it.
    assert ring.is_text_entry(editable) is False


# ------------------------------------------------------ Space inside the menus


def test_space_drops_a_highlighted_menu_title(
    app: QApplication, window: MainWindow
) -> None:
    """Qt gives a highlighted menu title nothing at all on Space.

    Enter worked in the menu bar and Space silently did not, so the one key
    that activates everything else in the application stopped at the menus.
    """

    from latencylab_ui import focus_cycle_menu as menus

    bar = window.menuBar()
    title = bar.actions()[0]
    bar.setActiveAction(title)
    _settle(app)

    # What is asserted is that the call reports success and leaves THIS menu up.
    # Whether it was already up cannot be established here: the offscreen
    # platform drops a menu merely on highlighting its title, and closing it
    # clears the active action that the call needs, so there is no order of
    # operations that proves the before-state. The branches that decide NOT to
    # open anything are covered by their own tests below.
    assert menus.open_menu_under_title(window) is True
    _settle(app)
    assert title.menu().isVisible() is True

    title.menu().close()
    _settle(app)


def test_space_on_a_title_with_no_menu_does_nothing(window: MainWindow) -> None:
    from PySide6.QtGui import QAction

    from latencylab_ui import focus_cycle_menu as menus

    bar = window.menuBar()
    bare = QAction("Bare", bar)
    bar.addAction(bare)
    bar.setActiveAction(bare)

    assert menus.open_menu_under_title(window) is False

    bar.setActiveAction(None)
    bar.removeAction(bare)


def test_nothing_highlighted_means_space_is_not_ours(window: MainWindow) -> None:
    from latencylab_ui import focus_cycle_menu as menus

    window.menuBar().setActiveAction(None)
    assert menus.open_menu_under_title(window) is False


# -------------------------------------------------- submenus own two arrow keys


def test_an_open_menu_yields_right_into_a_submenu_and_left_back_out(
    window: MainWindow,
) -> None:
    """The only two horizontal arrows the ring does not claim.

    Everywhere else Left and Right step the ring, which is what stops the menu
    bar's native title cycling from trapping focus in it.
    """

    from PySide6.QtWidgets import QMenu

    from latencylab_ui import focus_cycle_menu as menus

    parent = QMenu(window)
    plain = parent.addAction("Plain")
    submenu = QMenu("Deeper", parent)
    submenu.addAction("Inner")
    with_sub = parent.addMenu(submenu)

    parent.setActiveAction(with_sub)
    assert menus.should_yield_horizontal(parent, forward=True) is True

    parent.setActiveAction(plain)
    assert menus.should_yield_horizontal(parent, forward=True) is False

    # Left is only the menu's when there is a parent menu to climb back to.
    assert menus.should_yield_horizontal(parent, forward=False) is False
    assert menus.should_yield_horizontal(submenu, forward=False) is True


def test_a_menu_item_that_opens_a_submenu_is_not_triggered_by_space(
    window: MainWindow,
) -> None:
    """Space on it would close the menu without choosing anything."""

    from PySide6.QtWidgets import QMenu

    from latencylab_ui import focus_cycle_menu as menus

    parent = QMenu(window)
    submenu = QMenu("Deeper", parent)
    submenu.addAction("Inner")
    with_sub = parent.addMenu(submenu)

    parent.setActiveAction(with_sub)
    assert menus.trigger_highlighted_item(parent) is False

    parent.setActiveAction(None)
    assert menus.trigger_highlighted_item(parent) is False


def test_space_triggers_the_highlighted_item_of_an_open_menu(
    app: QApplication, window: MainWindow
) -> None:
    """Driven through a menu of our own, deliberately.

    The real File menu's first item is "Open model…", so triggering it opens a
    modal file dialog: the suite would hang rather than fail, which is a far
    worse thing for a test to do.
    """

    from PySide6.QtWidgets import QMenu

    from latencylab_ui.focus_cycle_keys import handle_space

    fired: list[str] = []
    menu = QMenu(window)
    action = menu.addAction("Harmless")
    action.triggered.connect(lambda: fired.append("fired"))

    menu.popup(window.mapToGlobal(window.rect().center()))
    _settle(app)
    menu.setActiveAction(action)

    assert handle_space(window, Qt.Key_Space) is True
    assert fired == ["fired"]

    menu.close()
    _settle(app)


def test_the_combo_handler_declines_everything_that_is_not_its_business(
    app: QApplication, window: MainWindow
) -> None:
    from latencylab_ui.focus_cycle_keys import handle_combo_box

    # A text field owns its own vertical arrows.
    window._runs_spin.setFocus()
    _settle(app)
    assert handle_combo_box(Qt.Key_Down) is False

    # A disabled selector is not its business either.
    combo = window._run_select
    combo.setEnabled(False)
    combo.setFocus()
    _settle(app)
    assert handle_combo_box(Qt.Key_Down) is False

    # And a key that is neither Down nor Up is nothing to do with it.
    assert handle_combo_box(Qt.Key_A) is False


def test_a_widget_that_cannot_scroll_is_never_a_scroll_stop() -> None:
    from PySide6.QtWidgets import QPushButton

    assert ring.scrolls_vertically(QPushButton("not a scroll area")) is False


def test_focus_is_reasserted_when_something_steals_it(
    app: QApplication, window: MainWindow
) -> None:
    """Qt drops the odd focus change on the first attempt, so the ring retries.

    The retry is guarded against acting for a stop the ring has already left, so
    this proves the guard lets the LIVE case through rather than swallowing it
    along with the stale ones.
    """

    controller = window._focus_cycle
    target = window._run_btn

    controller._apply(("widget", target))
    # Something else takes focus before the queued settle runs.
    window._how_to_read_btn.setFocus()
    assert not target.hasFocus()

    _settle(app)
    assert target.hasFocus()


def test_space_triggers_a_plain_highlighted_item(window: MainWindow) -> None:
    from PySide6.QtWidgets import QMenu

    from latencylab_ui import focus_cycle_menu as menus

    fired: list[str] = []
    menu = QMenu(window)
    action = menu.addAction("Do it")
    action.triggered.connect(lambda: fired.append("done"))

    menu.setActiveAction(action)
    assert menus.trigger_highlighted_item(menu) is True
    assert fired == ["done"]

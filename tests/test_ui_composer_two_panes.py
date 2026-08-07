from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton

from latencylab_ui import focus_cycle_widgets as ring
from latencylab_ui.main_window import MainWindow
from latencylab_ui.model_composer_dialog import ModelComposerDialog
from latencylab_ui.model_composer_panes import (
    MIN_HEIGHT,
    MIN_WIDTH,
    initial_size,
    page_index,
)
from latencylab_ui.model_composer_tree import (
    CONTEXTS,
    NO_TASK,
    SYSTEM,
    TASKS,
    WIRING,
    ComposerTree,
)


class _IdleController(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
    finished = Signal(int, float)

    def is_running(self) -> bool:
        return False

    def is_cancelled(self, _token: int) -> bool:
        return False

    def shutdown(self) -> None:
        return None


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def composer(app: QApplication) -> ModelComposerDialog:
    holder = QMainWindow()
    holder.resize(1200, 900)
    dialog = ModelComposerDialog(holder)
    dialog.show()
    app.processEvents()
    yield dialog
    dialog.reject()
    holder.close()
    app.processEvents()


def test_choosing_a_section_changes_what_the_other_pane_shows(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """The whole point: one pane names the parts, the other shows one part."""

    for section in (SYSTEM, CONTEXTS, TASKS, WIRING):
        composer._tree.select_section(section)
        app.processEvents()
        assert composer._stack.currentIndex() == page_index(section)


def test_one_task_is_shown_at_a_time(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """The tasks were the length: eleven of them asked for 3,647 pixels."""

    composer._tasks._on_add()
    composer._tasks._on_add()
    app.processEvents()
    assert composer._tasks.card_count() == 2

    composer._tree.select_task(0)
    app.processEvents()
    shown = [c for c in composer._tasks._iter_cards() if c.isVisibleTo(composer)]
    assert len(shown) == 1

    composer._tree.select_task(1)
    app.processEvents()
    also_shown = [c for c in composer._tasks._iter_cards() if c.isVisibleTo(composer)]
    assert len(also_shown) == 1
    assert also_shown[0] is not shown[0]


def test_the_tasks_section_itself_shows_no_card(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """The section is the place the Add button lives, not a task."""

    composer._tasks._on_add()
    composer._tree.select_section(TASKS)
    app.processEvents()

    assert composer._stack.currentIndex() == page_index(TASKS)
    assert [c for c in composer._tasks._iter_cards() if c.isVisibleTo(composer)] == []

    add = [
        b for b in composer._tasks.findChildren(QPushButton) if b.text() == "Add task"
    ]
    assert add and add[0].isVisibleTo(composer)


def test_adding_a_task_lands_on_the_task_that_was_added(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """Asking for a new task and being shown the old one is a wasted click."""

    composer._tree.select_section(TASKS)
    composer._tasks._on_add()
    app.processEvents()

    cards = composer._tasks._iter_cards()
    shown = [c for c in cards if c.isVisibleTo(composer)]
    assert shown == [cards[-1]]


def test_renaming_a_task_relabels_its_row_without_rebuilding(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """A name is edited a keystroke at a time and every keystroke says the
    model changed, so a rebuild per keystroke would take the selection and the
    keyboard away from the field being typed into."""

    composer._tasks._on_add()
    app.processEvents()
    composer._tree.select_task(0)
    row = composer._tree.currentItem()

    composer._tasks._iter_cards()[0].name_edit.setText("renamed")
    app.processEvents()

    assert composer._tree.currentItem() is row
    assert row.text(0) == "renamed"


def test_a_task_with_no_name_yet_still_has_a_row(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """Dropping the unnamed is right for a model and wrong for a list someone
    selects from: the positions would stop matching the cards."""

    composer._tasks._on_add()
    app.processEvents()
    composer._tasks._iter_cards()[0].name_edit.setText("")
    app.processEvents()

    assert composer._tasks.task_names() == []
    assert composer._tasks.card_labels() == ["(unnamed task 1)"]


def test_removing_a_task_keeps_the_selection_on_a_real_row(
    composer: ModelComposerDialog, app: QApplication
) -> None:
    """A selection that pointed at the last task points at nothing once it is
    gone, so it moves to the nearest surviving one rather than dangling."""

    composer._tasks._on_add()
    composer._tasks._on_add()
    app.processEvents()
    composer._tree.select_task(1)

    composer._tasks._remove_card(composer._tasks._iter_cards()[1])
    app.processEvents()

    assert composer._tasks.card_count() == 1
    section, index = _current(composer._tree)
    assert section == TASKS
    assert index == 0


def _current(tree: ComposerTree) -> tuple[str, int]:
    item = tree.currentItem()
    from latencylab_ui.model_composer_tree import INDEX_ROLE, SECTION_ROLE

    return str(item.data(0, SECTION_ROLE)), int(item.data(0, INDEX_ROLE))


def test_selecting_a_task_that_is_not_there_falls_back_to_the_section(
    app: QApplication,
) -> None:
    tree = ComposerTree()
    tree.set_task_labels(["only"])

    tree.select_task(9)

    assert _current(tree) == (TASKS, NO_TASK)

    tree.deleteLater()


def test_an_empty_selection_says_nothing(app: QApplication) -> None:
    """Qt reports the selection leaving as well as arriving, and a row that is
    not there is not a section to show."""

    seen: list[tuple[str, int]] = []
    tree = ComposerTree()
    tree.selected.connect(lambda section, index: seen.append((section, index)))

    tree._on_current_changed(None, None)

    assert seen == []

    tree.deleteLater()


def test_the_task_index_is_only_read_off_a_task_row(app: QApplication) -> None:
    tree = ComposerTree()
    assert tree._current_task_index() == NO_TASK

    tree.select_section(CONTEXTS)
    assert tree._current_task_index() == NO_TASK

    tree.set_task_labels(["a", "b"])
    tree.select_task(1)
    assert tree._current_task_index() == 1

    tree.deleteLater()


def test_the_dialog_opens_against_the_screen_when_it_has_no_parent(
    app: QApplication,
) -> None:
    """Modelling wants room, and with no parent to measure there is still a
    screen to measure."""

    parentless = initial_size(None)

    assert parentless.width() >= MIN_WIDTH
    assert parentless.height() >= MIN_HEIGHT


def test_the_dialog_opens_against_its_parent_when_it_has_one(
    app: QApplication,
) -> None:
    holder = QMainWindow()
    holder.resize(1400, 1000)

    against_parent = initial_size(holder)

    assert against_parent.width() <= 1400
    assert against_parent.width() >= MIN_WIDTH

    holder.close()
    holder.deleteLater()


def test_a_visible_dock_is_walked_and_a_chart_is_not_a_control(
    app: QApplication,
) -> None:
    """A dock is a SIBLING of the central widget rather than a child, so the
    walk has to reach into it explicitly rather than fall into it.

    Reaching into the distributions panel correctly yields nothing, which is
    the right answer rather than a missed one: it is charts and captions, and a
    picture of a distribution is not something to focus.
    """

    window = MainWindow(run_controller=_IdleController())
    window.show()
    app.processEvents()

    window._distributions_dock.setVisible(False)
    for _ in range(5):
        app.processEvents()
    hidden = ring.collect_interactive_widgets_in_layout_order(window)

    window._distributions_dock.setVisible(True)
    for _ in range(5):
        app.processEvents()
    shown = ring.collect_interactive_widgets_in_layout_order(window)

    assert window._distributions_dock.isVisible() is True
    assert shown == hidden
    assert not any(window._distributions_dock.isAncestorOf(stop) for stop in shown)

    window.close()
    window.deleteLater()
    app.processEvents()

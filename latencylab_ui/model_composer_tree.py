from __future__ import annotations

"""The composer's left pane: what the model is made of, as a list.

The composer used to be one column that scrolled. With a real model loaded it
asked for around 4,800 pixels of height, the tasks alone accounting for 3,647 of
them, so everything past the second task was found by scrolling and remembering.
A model is not a document, it is a handful of named things, and this pane says
what they are so the right-hand pane only ever has to show one of them.

The sections are fixed, because they are the parts of a model rather than
anything the user creates. Only the tasks have children, because tasks are the
only part there can be many of and the only part that was long.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

SYSTEM = "system"
CONTEXTS = "contexts"
TASKS = "tasks"
WIRING = "wiring"

# The order they are worked in: what the model is, what it runs on, what it
# does, then what triggers what. It is also the order the old column had them.
SECTIONS: tuple[tuple[str, str], ...] = (
    (SYSTEM, "System"),
    (CONTEXTS, "Contexts"),
    (TASKS, "Tasks"),
    (WIRING, "Wiring"),
)

# Where a section key is kept on its row. Qt's user-data role, so the row's
# TEXT stays free to be a label and nothing has to parse it back.
SECTION_ROLE = Qt.ItemDataRole.UserRole

# The index of a task within the tasks editor, on a task row. Kept beside the
# section rather than derived from the row's position, so an inserted section
# could never silently shift what a row points at.
INDEX_ROLE = Qt.ItemDataRole.UserRole + 1

# No task selected: the Tasks section itself is showing.
NO_TASK = -1


class ComposerTree(QTreeWidget):
    """The sections of a model, with one row per task under Tasks."""

    # (section key, task index). The index is NO_TASK for a section row.
    selected = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composer_tree")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        # One row is one thing. Selecting a range would suggest an action that
        # applies to several, and there is not one.
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.setUniformRowHeights(True)

        self._sections: dict[str, QTreeWidgetItem] = {}
        for key, label in SECTIONS:
            item = QTreeWidgetItem(self, [label])
            item.setData(0, SECTION_ROLE, key)
            item.setData(0, INDEX_ROLE, NO_TASK)
            self._sections[key] = item

        self._sections[TASKS].setExpanded(True)
        self.currentItemChanged.connect(self._on_current_changed)

    def _on_current_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            return
        self.selected.emit(
            str(current.data(0, SECTION_ROLE)), int(current.data(0, INDEX_ROLE))
        )

    def set_task_labels(self, labels: list[str]) -> None:
        """Show one row per task, renaming rather than rebuilding where it can.

        A task's name is edited a keystroke at a time and every keystroke says
        the model changed, so rebuilding on each one would take the selection
        and the keyboard away from the field being typed into. When the COUNT is
        the same the rows are simply relabelled, which is invisible; a rebuild
        happens only when there is genuinely a different number of tasks.
        """

        tasks = self._sections[TASKS]
        if tasks.childCount() == len(labels):
            for index, label in enumerate(labels):
                tasks.child(index).setText(0, label)
            return

        was_on_task = self._current_task_index()

        blocked = self.blockSignals(True)
        tasks.takeChildren()
        for index, label in enumerate(labels):
            row = QTreeWidgetItem(tasks, [label])
            row.setData(0, SECTION_ROLE, TASKS)
            row.setData(0, INDEX_ROLE, index)
        tasks.setExpanded(True)
        self.blockSignals(blocked)

        # A selection that pointed at a task now points at nothing, so it is
        # put back on the nearest surviving one rather than left dangling.
        if was_on_task != NO_TASK and labels:
            self.select_task(min(was_on_task, len(labels) - 1))

    def _current_task_index(self) -> int:
        item = self.currentItem()
        if item is None:
            return NO_TASK
        if str(item.data(0, SECTION_ROLE)) != TASKS:
            return NO_TASK
        return int(item.data(0, INDEX_ROLE))

    def select_section(self, key: str) -> None:
        self.setCurrentItem(self._sections[key])

    def select_task(self, index: int) -> None:
        """Select a task row, falling back to the section if it is not there."""

        tasks = self._sections[TASKS]
        if 0 <= index < tasks.childCount():
            self.setCurrentItem(tasks.child(index))
            return
        self.setCurrentItem(tasks)

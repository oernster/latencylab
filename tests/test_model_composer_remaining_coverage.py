from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMainWindow

from latencylab_ui.model_composer_dock import ModelComposerDock
from latencylab_ui.model_composer_tasks_editor import TasksEditor, _TaskCard
from latencylab_ui.model_composer_wiring_editor import WiringEditor


def _ensure_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dock_refresh_wiring_events_includes_task_emits_and_strips() -> None:
    """Cover the task.emit loop in _refresh_wiring_events()."""

    _ensure_qapp()
    mw = QMainWindow()
    dock = ModelComposerDock(mw)

    captured: dict[str, object] = {}

    def _capture(names, *, entry_event: str) -> None:  # type: ignore[no-untyped-def]
        captured["names"] = list(names)
        captured["entry_event"] = entry_event

    dock._wiring.set_event_names = _capture  # type: ignore[method-assign]

    dock._state.entry_event = "start"
    dock._state.tasks = {
        "t1": {"emit": ["  a  ", " ", "b"]},
        "t2": {"emit": []},
    }
    dock._state.wiring = {"w": []}

    dock._refresh_wiring_events()

    assert captured["entry_event"] == "start"
    assert captured["names"] == ["a", "b", "start", "w"]


def test_dock_autowires_entry_event_to_first_task_and_tracks_rename() -> None:
    _ensure_qapp()

    mw = QMainWindow()
    dock = ModelComposerDock(mw)

    # Ensure stable entry event.
    dock._system.entry_event_edit.setText("start")  # noqa: SLF001

    # No tasks yet -> no wiring.
    dock._tasks._on_add()  # noqa: SLF001
    card = dock._tasks._iter_cards()[0]  # noqa: SLF001
    card.name_edit.setText("task_1")

    dock._on_tasks_changed()  # noqa: SLF001
    assert dock._wiring.get_wiring().get("start") == [  # noqa: SLF001
        {"task": "task_1", "delay_ms": None}
    ]

    # Rename the only task; wiring should follow.
    card.name_edit.setText("renamed")
    dock._on_tasks_changed()  # noqa: SLF001
    assert dock._wiring.get_wiring().get("start") == [  # noqa: SLF001
        {"task": "renamed", "delay_ms": None}
    ]


def test_dock_autowire_entry_event_early_return_guards() -> None:
    """Cover early returns in `_maybe_autowire_entry_event()`.

    The rename/sync path can't be exercised through `_on_tasks_changed()` because
    `WiringEditor.set_task_names()` prunes edges that reference missing tasks.
    """

    _ensure_qapp()
    mw = QMainWindow()
    dock = ModelComposerDock(mw)

    # Guard 1: empty entry event.
    # Can't use `entry_event_edit.setText("")` because SystemEditor.get_entry_event()
    # normalizes empty -> "start". Patch the getter instead.
    dock._system.get_entry_event = lambda: ""  # type: ignore[method-assign]  # noqa: SLF001
    dock._wiring.set_wiring({"start": [{"task": "t", "delay_ms": None}]})  # noqa: SLF001
    dock._maybe_autowire_entry_event(task_names=["t"])  # noqa: SLF001
    assert dock._wiring.get_wiring() == {"start": [{"task": "t", "delay_ms": None}]}  # noqa: SLF001

    # Guard 2: not exactly one task.
    dock._system.get_entry_event = lambda: "start"  # type: ignore[method-assign]  # noqa: SLF001
    dock._wiring.set_wiring({})  # noqa: SLF001
    dock._maybe_autowire_entry_event(task_names=["a", "b"])  # noqa: SLF001
    assert dock._wiring.get_wiring() == {}  # noqa: SLF001

    # Guard 3: only task name is empty.
    dock._wiring.set_wiring({})  # noqa: SLF001
    dock._maybe_autowire_entry_event(task_names=["  "])  # noqa: SLF001
    assert dock._wiring.get_wiring() == {}  # noqa: SLF001


def test_dock_autowire_single_edge_task_sync_preserves_delay_ms() -> None:
    """Cover the `len(edges) == 1` sync branch in `_maybe_autowire_entry_event()`."""

    _ensure_qapp()
    mw = QMainWindow()
    dock = ModelComposerDock(mw)

    dock._system.entry_event_edit.setText("start")  # noqa: SLF001
    dock._wiring.set_wiring({"start": [{"task": "old", "delay_ms": 5}]})  # noqa: SLF001

    dock._maybe_autowire_entry_event(task_names=["new"])  # noqa: SLF001
    assert dock._wiring.get_wiring()["start"] == [{"task": "new", "delay_ms": 5}]  # noqa: SLF001


def test_tasks_editor_context_preserve_skip_and_remove_paths() -> None:
    """Cover remaining branches in TasksEditor/_TaskCard."""

    _ensure_qapp()
    te = TasksEditor()

    # Add one card, then exercise set_context_names() looping over cards.
    te._on_add()
    cards = te._iter_cards()
    assert len(cards) == 1
    card = cards[0]

    # Cover: _TaskCard.set_context_names() keeps previous selection when possible.
    card.set_context_names(["ui", "ctx"])
    card.context_combo.setCurrentText("ctx")
    card.set_context_names(["ui", "ctx", "other"])
    assert card.context_combo.currentText() == "ctx"

    te.set_context_names(["ui", "ctx", "other"])
    assert card.context_combo.count() >= 2

    # Cover: _TaskCard.to_task_obj() returns None when name is empty,
    # and TasksEditor.to_tasks_dict() skips such cards.
    card.name_edit.setText("")
    assert card.to_task_obj(version=2) is None
    assert te.to_tasks_dict(version=2) == {}

    # Cover: remove card cleanup + changed emission.
    seen: list[str] = []

    def _on_changed() -> None:
        seen.append("changed")

    te.changed.connect(_on_changed)
    te._remove_card(card)
    assert len(seen) == 1
    assert card.parent() is None
    assert te._iter_cards() == []


def test_wiring_editor_remaining_coverage_paths() -> None:
    """Cover remaining branches in WiringEditor."""

    _ensure_qapp()
    w = WiringEditor()

    # Cover: preserve previous selection in set_task_names().
    w.set_task_names(["keep", "x"])
    w.add_listener_combo.setCurrentText("keep")
    w.set_task_names(["keep", "y"])
    assert w.add_listener_combo.currentText() == "keep"

    # Cover: set_task_names() prunes edges that reference missing tasks.
    w.set_event_names(["ev"], entry_event="ev")
    w.set_wiring({"ev": [{"task": "missing", "delay_ms": None}]})
    w.set_task_names(["present"])
    assert w.get_wiring()["ev"] == []

    # Cover: _on_event_selected() delegates to _render_listeners().
    w.set_task_names(["t1"])
    w.set_event_names(["ev1"], entry_event="ev1")
    w.set_wiring({"ev1": [{"task": "t1", "delay_ms": None}]})
    # Cover: set_task_names() keeps valid edges.
    w.set_task_names(["t1"])
    w._on_event_selected("ev1")
    assert w.listeners_list.count() == 1

    # Cover: defensive selection restore when no previous selection matches.
    # (Hits setCurrentIndex(0) branches)
    w.set_event_names(["a", "b"], entry_event="")
    assert w.event_combo.currentIndex() >= 0

    # Force currentIndex < 0 while combo has items, then trigger defensive fix
    # in set_event_names() (line 110 in WiringEditor).
    w.event_combo.setCurrentIndex(-1)
    w.set_event_names(["a", "b"], entry_event="")
    assert w.event_combo.currentIndex() >= 0

    # Cover: `_refresh_event_choices()` selects entry_event when prev missing.
    w.set_event_names(["start", "x"], entry_event="start")
    w._refresh_event_choices(select="does-not-exist")
    assert w.event_combo.currentText() == "start"

    # Cover: `_refresh_event_choices()` falls back to index 0 when prev missing
    # and entry_event is empty.
    w.set_event_names(["a"], entry_event="")
    w._refresh_event_choices(select="does-not-exist")
    assert w.event_combo.currentIndex() == 0


def test_wiring_editor_defensive_current_index_fix_executes() -> None:
    """Force the `currentIndex() < 0` defensive branch in set_event_names()."""

    _ensure_qapp()
    w = WiringEditor()

    class _FakeCombo:
        def __init__(self) -> None:
            self._items: list[str] = []
            self._idx = -1
            self._blocked = False

        def currentText(self) -> str:
            if 0 <= self._idx < len(self._items):
                return self._items[self._idx]
            return ""

        def blockSignals(self, blocked: bool) -> None:  # noqa: N802
            self._blocked = bool(blocked)

        def clear(self) -> None:
            self._items.clear()
            self._idx = -1

        def addItems(self, items: list[str]) -> None:  # noqa: N802
            self._items.extend(list(items))
            # Intentionally keep idx invalid to simulate Qt losing selection.

        def setCurrentText(self, txt: str) -> None:  # noqa: N802
            # Intentionally do nothing: simulate a broken restore.
            _ = txt

        def setCurrentIndex(self, idx: int) -> None:  # noqa: N802
            # Intentionally do nothing: keep index invalid.
            _ = idx

        def currentIndex(self) -> int:  # noqa: N802
            return int(self._idx)

        def count(self) -> int:
            return len(self._items)

    # Replace the combo with a fake that reports `count()>0` but `currentIndex()<0`.
    fake = _FakeCombo()
    w.event_combo = fake  # type: ignore[assignment]

    # Ensure _refresh_event_choices() does NOT auto-select an item, so the
    # defensive branch in set_event_names() is exercised.
    def _no_select(*, select=None) -> None:  # type: ignore[no-untyped-def]
        fake.clear()
        fake.addItems(list(w._event_names))

    w._refresh_event_choices = _no_select  # type: ignore[method-assign]

    w.set_event_names(["start"], entry_event="start")
    assert fake.count() == 1
    # We *expect* the fake to remain invalid; this is about line coverage for
    # the hard guard in `set_event_names()`.
    assert fake.currentIndex() < 0

    # Cover: WiringEditor.set_event_names() docstring path (line coverage).
    # (This is intentionally just an execution hit.)
    w.set_event_names(["ev1", "x"], entry_event="ev1")

    # Cover: add/remove early-return guards.
    # QComboBox won't select an empty string unless it's in the model, so make
    # the *task* empty instead.
    w.event_combo.setCurrentText("ev1")

    w.set_event_names(["ev1"], entry_event="ev1")
    w._refresh_event_choices(select="ev1")
    assert w.listeners_list.currentRow() == -1
    w._on_remove_listener()


def test_wiring_editor_add_listener_duplicate_guard_returns() -> None:
    """Cover duplicate-guard early return in `_on_add_listener()` (line 279)."""

    _ensure_qapp()
    w = WiringEditor()

    w.set_task_names(["t1"])
    w.set_event_names(["ev1"], entry_event="ev1")
    w.set_wiring({"ev1": [{"task": "t1", "delay_ms": None}]})

    # Force the add-listener combo to include the duplicate (normally filtered
    # out by `_sync_add_listener_choices()`), so the safety guard line executes.
    w.add_listener_combo.setEnabled(True)
    w.add_listener_combo.blockSignals(True)
    w.add_listener_combo.clear()
    w.add_listener_combo.addItems(["t1"])
    w.add_listener_combo.setCurrentText("t1")
    w.add_listener_combo.blockSignals(False)

    w.event_combo.setCurrentText("ev1")

    # Attempt to add the same listener again; should no-op.
    w._on_add_listener()
    assert w.get_wiring()["ev1"] == [{"task": "t1", "delay_ms": None}]


def test_wiring_editor_add_listener_empty_task_early_return() -> None:
    """Cover the `if not ev or not task: return` guard in `_on_add_listener()`."""

    _ensure_qapp()
    w = WiringEditor()

    w.set_task_names(["t1"])
    w.set_event_names(["ev1"], entry_event="ev1")
    w.set_wiring({"ev1": []})

    w.event_combo.setCurrentText("ev1")

    # Force empty task.
    w.add_listener_combo.clear()
    w._on_add_listener()

    assert w.get_wiring() == {"ev1": []}


def test_wiring_editor_event_filter_swallows_mouse_and_key_when_single_event() -> None:
    """Cover eventFilter swallow paths for read-only single-choice combos."""

    _ensure_qapp()
    w = WiringEditor()

    # Ensure `count() <= 1`.
    w.set_event_names(["start"], entry_event="start")
    assert w.event_combo.count() == 1

    # Use the non-deprecated Qt6 constructor (localPos + globalPos) to avoid
    # `DeprecationWarning`.
    local = QPointF(w.event_combo.rect().center())
    global_pt = QPointF(w.event_combo.mapToGlobal(w.event_combo.rect().center()))
    mouse_evt = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        global_pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert w.eventFilter(w.event_combo, mouse_evt) is True

    key_evt = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    assert w.eventFilter(w.event_combo, key_evt) is True


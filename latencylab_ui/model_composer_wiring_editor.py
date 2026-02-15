from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.qt_style_helpers import harden_combobox_popup


def _maybe_harden_combo(combo: object) -> None:
    """Best-effort hardening.

    Some unit tests replace real QComboBox instances with fakes to force
    defensive branches. Avoid calling hardening logic on those fakes.
    """

    if isinstance(combo, QComboBox):
        harden_combobox_popup(combo)


class WiringEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._wiring: dict[str, list[dict[str, object]]] = {}
        self._task_names: list[str] = []
        self._event_names: list[str] = []
        self._entry_event: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top = QWidget(self)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Event"))
        self.event_combo = QComboBox(top)
        harden_combobox_popup(self.event_combo)
        self.event_combo.currentTextChanged.connect(self._on_event_selected)
        # UX decision: when there is only *one* possible event (commonly just
        # the entry event `start`), this should behave like a read-only field,
        # not an interactive dropdown that appears to offer choices.
        self.event_combo.installEventFilter(self)
        top_layout.addWidget(self.event_combo, 1)
        layout.addWidget(top)

        self.listeners_list = QListWidget(self)
        layout.addWidget(self.listeners_list)

        # Empty-state hint: users commonly interpret an empty list as a
        # rendering bug. Keep it short so it fits even in narrow panels.
        self._empty_hint = QLabel("No listeners yet", self)
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setStyleSheet("color: palette(mid); padding: 2px 0;")
        layout.addWidget(self._empty_hint)

        add_row = QWidget(self)
        add_layout = QHBoxLayout(add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.addWidget(QLabel("Add listener"))
        self.add_listener_combo = QComboBox(add_row)
        harden_combobox_popup(self.add_listener_combo)
        add_layout.addWidget(self.add_listener_combo, 1)
        self._add_listener_btn = QPushButton("Add", add_row)
        self._add_listener_btn.clicked.connect(self._on_add_listener)
        add_layout.addWidget(self._add_listener_btn)
        self._remove_listener_btn = QPushButton("Remove selected", add_row)
        self._remove_listener_btn.clicked.connect(self._on_remove_listener)
        add_layout.addWidget(self._remove_listener_btn)
        layout.addWidget(add_row)

        self._refresh_event_choices()
        self._update_empty_hint()
        self._update_event_combo_interactive_state()
        self._sync_add_listener_choices()

    def eventFilter(self, obj: object, event: QEvent) -> bool:  # noqa: N802
        if obj is self.event_combo and self.event_combo.count() <= 1:
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            ):
                return True

            if event.type() == QEvent.Type.KeyPress:
                key = getattr(event, "key", lambda: None)()
                if key in (
                    int(Qt.Key.Key_Space),
                    int(Qt.Key.Key_Return),
                    int(Qt.Key.Key_Enter),
                    int(Qt.Key.Key_Down),
                ):
                    return True

        return super().eventFilter(obj, event)

    def _update_event_combo_interactive_state(self) -> None:
        # Keep it visually enabled (readable), but disable interaction when
        # there are no alternative choices.
        tip = "Only one event available" if self.event_combo.count() <= 1 else ""
        # Some unit tests replace this with a fake combo; guard optional methods.
        if hasattr(self.event_combo, "setToolTip"):
            self.event_combo.setToolTip(tip)  # type: ignore[call-arg]

    def _update_empty_hint(self) -> None:
        self._empty_hint.setVisible(self.listeners_list.count() == 0)

    def _sync_add_listener_choices(self) -> None:
        """Keep the Add Listener combo consistent with current tasks/wiring.

        UX decision:
        - If there are no tasks, disable Add Listener controls.
        - If all tasks are already listeners for the selected event, disable Add.
        - Never offer duplicates in the dropdown.
        """

        ev = self.event_combo.currentText().strip()
        tasks = [t for t in (self._task_names or []) if str(t).strip()]

        # Determine which tasks are already listeners for the selected event.
        used: set[str] = set()
        if ev:
            for edge in self._wiring.get(ev, []) or []:
                t = str((edge or {}).get("task", "")).strip()
                if t:
                    used.add(t)

        available = [t for t in tasks if t not in used]

        # Rebuild combo items deterministically, preserving selection when possible.
        prev = self.add_listener_combo.currentText()
        self.add_listener_combo.blockSignals(True)
        self.add_listener_combo.clear()
        self.add_listener_combo.addItems(available)
        _maybe_harden_combo(self.add_listener_combo)
        if prev in available:
            self.add_listener_combo.setCurrentText(prev)
        self.add_listener_combo.blockSignals(False)

        has_tasks = bool(tasks)
        can_add = bool(available)
        has_listeners = self.listeners_list.count() > 0

        # Enable/disable controls.
        self.add_listener_combo.setEnabled(has_tasks and can_add)
        self._add_listener_btn.setEnabled(has_tasks and can_add)
        self._remove_listener_btn.setEnabled(has_listeners)

        if not has_tasks:
            tip = "Add a task first"
        elif not can_add:
            tip = "No more tasks to add"
        else:
            tip = ""

        self.add_listener_combo.setToolTip(tip)
        self._add_listener_btn.setToolTip(tip)

    def set_task_names(self, names: Sequence[str]) -> None:
        self._task_names = list(names)

        # State-sync clarity: if tasks were renamed/removed, prune any wiring
        # edges that now reference missing tasks so the UI doesn't show
        # listeners that can never be satisfied.
        allowed = {t for t in self._task_names if str(t).strip()}
        for ev, edges in list(self._wiring.items()):
            kept: list[dict[str, object]] = []
            for edge in edges or []:
                task = str((edge or {}).get("task", "")).strip()
                # Keep original edge dicts (incl. delay_ms), but only when task exists.
                if task and task in allowed:
                    kept.append(edge)
            self._wiring[ev] = kept

        prev = self.add_listener_combo.currentText()
        self.add_listener_combo.blockSignals(True)
        self.add_listener_combo.clear()
        self.add_listener_combo.addItems(self._task_names)
        # Defensive: if items were added/reset, re-harden so model roles are
        # re-applied immediately (not only at popup show-time).
        _maybe_harden_combo(self.add_listener_combo)
        if prev in self._task_names:
            self.add_listener_combo.setCurrentText(prev)
        self.add_listener_combo.blockSignals(False)

        self._sync_add_listener_choices()

        # Refresh the visible list for the currently-selected event.
        self._render_listeners(self.event_combo.currentText())

    def set_event_names(self, names: Sequence[str], *, entry_event: str) -> None:
        """Set the list of selectable events.

        MVP policy: events are derived-only.
        """

        prev = self.event_combo.currentText()

        self._entry_event = str(entry_event).strip()
        uniq = {str(n).strip() for n in (names or []) if str(n).strip()}

        ordered: list[str] = []
        if self._entry_event and self._entry_event in uniq:
            ordered.append(self._entry_event)

        rest = sorted(n for n in uniq if n != self._entry_event)
        ordered.extend(rest)

        self._event_names = ordered

        # Deterministic selection restore.
        self.event_combo.blockSignals(True)
        self.event_combo.clear()
        self.event_combo.addItems(ordered)
        # Defensive: if items were added/reset, re-harden so model roles are
        # re-applied immediately (not only at popup show-time).
        _maybe_harden_combo(self.event_combo)

        if prev and prev in ordered:
            self.event_combo.setCurrentText(prev)
        elif self._entry_event and self._entry_event in ordered:
            self.event_combo.setCurrentText(self._entry_event)
        elif ordered:
            self.event_combo.setCurrentIndex(0)

        self.event_combo.blockSignals(False)
        self._update_event_combo_interactive_state()

        # Hard guard: never allow populated combo to have currentIndex == -1.
        if ordered and self.event_combo.currentIndex() < 0:
            self.event_combo.setCurrentIndex(0)

        self._render_listeners(self.event_combo.currentText())

    def set_wiring(self, wiring: dict[str, list[dict[str, object]]]) -> None:
        self._wiring = {str(k): list(v) for k, v in (wiring or {}).items()}
        self._refresh_event_choices()
        self._sync_add_listener_choices()

    def get_wiring(self) -> dict[str, list[dict[str, object]]]:
        return {k: list(v) for k, v in self._wiring.items()}

    def _on_event_selected(self, ev: str) -> None:
        self._render_listeners(ev)

    def _render_listeners(self, ev: str) -> None:
        self.listeners_list.clear()
        if not ev:
            self._update_empty_hint()
            self._sync_add_listener_choices()
            return
        for edge in self._wiring.get(ev, []) or []:
            t = str((edge or {}).get("task", "")).strip()
            if t:
                self.listeners_list.addItem(t)
        self._update_empty_hint()
        self._sync_add_listener_choices()

    def _on_add_listener(self) -> None:
        ev = self.event_combo.currentText().strip()
        task = self.add_listener_combo.currentText().strip()
        if not ev or not task:
            return
        # Prevent duplicates (should be impossible via UI, but keep it safe).
        if any(str((e or {}).get("task", "")).strip() == task for e in (self._wiring.get(ev) or [])):
            return
        self._wiring.setdefault(ev, []).append({"task": task, "delay_ms": None})
        self._render_listeners(ev)
        self.changed.emit()

    def _on_remove_listener(self) -> None:
        ev = self.event_combo.currentText().strip()
        row = self.listeners_list.currentRow()
        if not ev or row < 0:
            return
        edges = self._wiring.get(ev) or []
        if 0 <= row < len(edges):
            edges.pop(row)
        self._render_listeners(ev)
        self.changed.emit()

    def _refresh_event_choices(self, *, select: str | None = None) -> None:
        prev = (select or self.event_combo.currentText()).strip()
        # Derived-only list (set by the dock).
        evs = list(self._event_names)
        self.event_combo.blockSignals(True)
        self.event_combo.clear()
        self.event_combo.addItems(evs)
        # Defensive: this method is called from multiple refresh paths; ensure
        # roles are re-applied for any newly populated items.
        _maybe_harden_combo(self.event_combo)
        if prev and prev in evs:
            self.event_combo.setCurrentText(prev)
        elif self._entry_event and self._entry_event in evs:
            self.event_combo.setCurrentText(self._entry_event)
        elif evs:
            self.event_combo.setCurrentIndex(0)
        self.event_combo.blockSignals(False)
        self._update_event_combo_interactive_state()
        self._render_listeners(self.event_combo.currentText())


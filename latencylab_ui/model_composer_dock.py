from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from latencylab.model import Model
from latencylab.validate import ModelValidationError, validate_model
from latencylab_ui.model_composer_contexts_editor import ContextsEditor
from latencylab_ui.model_composer_system_editor import SystemEditor
from latencylab_ui.model_composer_tasks_editor import TasksEditor
from latencylab_ui.model_composer_wiring_editor import WiringEditor
from latencylab_ui.model_composer_types import ComposerState, build_raw_model_dict
from latencylab_ui.model_composer_export import export_model, export_stress_variant
from latencylab_ui.model_composer_load import load_raw_model


class ModelComposerDock(QDockWidget):
    """Authoring-only dock.

    Phase 1 MVP:
    - System (name/version/entry event)
    - Contexts
    - Tasks (fixed/normal/lognormal; basic v2 category)
    - Wiring builder (no delays)
    - Validate + Export (+ stress)
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("model_composer_dock")
        self.setWindowTitle("Model Composer")
        # Give the composer enough horizontal space to avoid cramped/hidden
        # controls on first open (especially after switching from Distributions).
        self.setMinimumWidth(560)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        self._state = ComposerState()

        # Whether these editors are a view of an opened model or something the
        # user typed. See `is_showing_loaded_model`.
        self._showing_loaded_model = False

        root = QWidget(self)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(root)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        body = QWidget(scroll)
        # `Maximum` vertically reads as "no taller than it needs" and means
        # "may be made SHORTER than it needs", which is not what a scrolling
        # panel wants: the scrollbar exists precisely so the content does not
        # have to fit. Measured with the checkout model loaded and the layouts
        # settled, it left nineteen controls drawn under their own minimum,
        # which is how the Params arrows came out squashed. The trailing
        # `addStretch(1)` below is what absorbs the surplus when a model is
        # small, so nothing here needs the shrink permission.
        body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self._valid_label = QLabel("")

        layout.addWidget(self._wrap_box("System", self._build_system()))
        layout.addWidget(self._wrap_box("Contexts", self._build_contexts()))
        layout.addWidget(self._wrap_box("Tasks", self._build_tasks()))
        layout.addWidget(self._wrap_box("Wiring", self._build_wiring()))
        layout.addWidget(self._build_validate_box())
        layout.addWidget(self._build_export_box())
        layout.addStretch(1)

        self.setWidget(root)
        self._apply_version_to_children()

        # Ensure derived event lists are ready before first interaction.
        # (Prevents the Wiring event combo from appearing empty/blank on open.)
        self._sync_from_ui()
        self._refresh_wiring_events()

    @staticmethod
    def _wrap_box(title: str, inner: QWidget) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(inner)
        return box

    def _build_system(self) -> QWidget:
        self._system = SystemEditor(self)
        self._system.set_values(
            model_name=self._state.model_name,
            version=self._state.version,
            entry_event=self._state.entry_event,
        )
        self._system.changed.connect(self._on_state_changed)
        self._system.version_changed.connect(self._on_version_changed)
        self._system.changed.connect(self._refresh_wiring_events)
        return self._system

    def _build_contexts(self) -> QWidget:
        self._contexts = ContextsEditor(self)
        self._contexts.changed.connect(self._on_contexts_changed)
        return self._contexts

    def _build_tasks(self) -> QWidget:
        self._tasks = TasksEditor(self)
        self._tasks.changed.connect(self._on_tasks_changed)
        self._tasks.changed.connect(self._refresh_wiring_events)
        return self._tasks

    def _build_wiring(self) -> QWidget:
        self._wiring = WiringEditor(self)
        self._wiring.changed.connect(self._on_state_changed)
        return self._wiring

    def _on_version_changed(self, version: int) -> None:
        self._state.version = int(version)
        self._apply_version_to_children()
        self._on_state_changed()

    def _apply_version_to_children(self) -> None:
        self._tasks.set_version(self._state.version)

    def _on_contexts_changed(self) -> None:
        # Update dependent editors first, then state.
        self._tasks.set_context_names(self._contexts.context_names())
        self._on_state_changed()

    def _maybe_autowire_entry_event(self, *, task_names: list[str]) -> None:
        """Auto-wire entry_event -> first task for a smoother MVP.

        Policy (explicit UX decision):
        - Only when there is exactly one task in the model.
        - If wiring for entry_event is empty/missing, create a single edge.
        - If wiring for entry_event has exactly one edge, keep its task name in
          sync with the sole task (covers rename) while preserving delay_ms.
        """

        entry = str(self._system.get_entry_event()).strip()
        if not entry:
            return

        if len(task_names) != 1:
            return

        only_task = str(task_names[0]).strip()
        if not only_task:
            return

        wiring = self._wiring.get_wiring() or {}
        edges = list(wiring.get(entry) or [])

        if len(edges) == 0:
            wiring[entry] = [{"task": only_task, "delay_ms": None}]
            self._wiring.set_wiring(wiring)
            return

        if len(edges) == 1:
            edge = dict(edges[0] or {})
            if str(edge.get("task", "")).strip() != only_task:
                edge["task"] = only_task
                edge.setdefault("delay_ms", None)
                wiring[entry] = [edge]
                self._wiring.set_wiring(wiring)

    def _on_tasks_changed(self) -> None:
        task_names = self._tasks.task_names()
        self._wiring.set_task_names(task_names)
        self._maybe_autowire_entry_event(task_names=task_names)
        self._on_state_changed()

    def load_raw_model(self, raw: dict, *, model_name: str) -> None:
        """Fill the composer from a model that already exists on disk."""

        load_raw_model(self, raw, model_name=model_name)
        self._showing_loaded_model = True

    def is_showing_loaded_model(self) -> bool:
        """Whether these editors are a view of a model that was opened.

        The difference matters when another model is opened. A composer that is
        showing a loaded model is stale the moment a different one loads and
        has to follow it. A composer holding something typed from scratch is
        the user's own work, and replacing that would be data loss rather than
        a refresh, so it is left alone.
        """

        return self._showing_loaded_model

    def clear_validation(self) -> None:
        """Drop the last validation verdict and re-derive from the editors."""

        self._valid_label.setText("")
        self._sync_from_ui()

    def _on_state_changed(self) -> None:
        self._valid_label.setText("")
        self._sync_from_ui()

    def _sync_from_ui(self) -> None:
        self._state.model_name = self._system.get_model_name()
        self._state.version = self._system.get_version()
        self._state.entry_event = self._system.get_entry_event()
        self._state.contexts = self._contexts.to_contexts_dict()
        self._state.tasks = self._tasks.to_tasks_dict(version=self._state.version)
        self._state.wiring = self._wiring.get_wiring()

        # Derived-only wiring events list (Policy 1: entry_event first, then alpha).
        self._refresh_wiring_events()

    def _refresh_wiring_events(self) -> None:
        evs: set[str] = set()
        entry = str(self._state.entry_event).strip()
        if entry:
            evs.add(entry)
        for t in self._state.tasks.values():
            for ev in t.get("emit", []) or []:
                s = str(ev).strip()
                if s:
                    evs.add(s)
        # Keep any already-authored wiring keys as selectable.
        for ev in (self._state.wiring or {}).keys():
            s = str(ev).strip()
            if s:
                evs.add(s)

        self._wiring.set_event_names(sorted(evs), entry_event=entry)

    # ----- Validate -----

    def _build_validate_box(self) -> QGroupBox:
        box = QGroupBox("Validate")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        btn = QPushButton("Validate Model", box)
        btn.clicked.connect(self._on_validate_clicked)
        layout.addWidget(btn)
        layout.addWidget(self._valid_label, 1)
        return box

    def _on_validate_clicked(self) -> None:
        ok = self._validate_now(show_dialog=True)
        self._valid_label.setText("Valid" if ok else "Invalid")

    def _validate_now(self, *, show_dialog: bool) -> bool:
        try:
            self._sync_from_ui()
            raw = build_raw_model_dict(self._state)
            model = Model.from_json(raw)
            validate_model(model)
            return True
        except (ModelValidationError, ValueError, TypeError) as e:
            if show_dialog:
                QMessageBox.critical(self, "Invalid model", str(e))
            return False
        except Exception as e:  # noqa: BLE001
            if show_dialog:
                QMessageBox.critical(self, "Error", str(e))
            return False

    # ----- Export -----

    def _build_export_box(self) -> QGroupBox:
        box = QGroupBox("Export")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        stress_row = QWidget(box)
        stress_layout = QHBoxLayout(stress_row)
        stress_layout.setContentsMargins(0, 0, 0, 0)
        stress_layout.addWidget(QLabel("Stress multiplier"))
        self._stress_mult = QDoubleSpinBox(stress_row)
        self._stress_mult.setDecimals(6)
        self._stress_mult.setRange(0.000001, 1e6)
        self._stress_mult.setValue(2.0)
        stress_layout.addWidget(self._stress_mult)
        stress_layout.addStretch(1)
        layout.addWidget(stress_row)

        btn_row = QWidget(box)
        btns = QHBoxLayout(btn_row)
        btns.setContentsMargins(0, 0, 0, 0)
        export_btn = QPushButton("Export JSON…", btn_row)
        export_load_btn = QPushButton("Export + Load Into Main UI…", btn_row)
        stress_btn = QPushButton("Generate Stress Variant…", btn_row)
        export_btn.clicked.connect(lambda: self._on_export_clicked(load_after=False))
        export_load_btn.clicked.connect(
            lambda: self._on_export_clicked(load_after=True)
        )
        stress_btn.clicked.connect(self._on_export_stress_clicked)
        btns.addWidget(export_btn)
        btns.addWidget(export_load_btn)
        btns.addWidget(stress_btn)
        btns.addStretch(1)
        layout.addWidget(btn_row)
        return box

    def _on_export_clicked(self, *, load_after: bool) -> None:
        export_model(self, load_after=load_after)

    def _on_export_stress_clicked(self) -> None:
        export_stress_variant(self, multiplier=float(self._stress_mult.value()))

    # ----- What the load and export helpers read -----
    #
    # Named rather than reached for through the private attributes, so the two
    # halves of the composer's file handling are a small stated surface instead
    # of an open licence over the dock's internals.

    @property
    def state(self) -> ComposerState:
        return self._state

    def sync_from_ui(self) -> None:
        self._sync_from_ui()

    def validate_now(self, *, show_dialog: bool) -> bool:
        return self._validate_now(show_dialog=show_dialog)

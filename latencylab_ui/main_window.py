from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from latencylab.model import Model

from latencylab_ui.main_window_file_io import (
    load_model as _load_model,
    on_save_log_clicked as _on_save_log_clicked,
    open_model_dialog as _open_model_dialog,
)

from latencylab_ui.run_controller import RunController, RunOutputs, RunRequest
from latencylab_ui.focus_cycle import FocusCycleController
from latencylab_ui.main_window_menus import build_menus, show_how_to_read_dialog
from latencylab_ui.theme import Theme, apply_theme
from latencylab_ui.main_window_top_bar import build_top_bar
from latencylab_ui import main_window_actions as actions
from latencylab_ui import main_window_panels as panels
from latencylab_ui.main_window_panels import build_left_panel
from latencylab_ui.distributions_dock import DistributionsDock
from latencylab_ui.model_composer_dock import ModelComposerDock
from latencylab_ui.main_window_dock_switching import toggle_or_switch_to_model_composer


@dataclass
class _LoadedModel:
    path: Path
    model: Model


class MainWindow(QMainWindow):
    def __init__(self, *, run_controller: RunController) -> None:
        super().__init__()
        self._controller = run_controller

        self._loaded_model: _LoadedModel | None = None
        self._active_run_token: int | None = None
        self._active_cancelled = False

        # Last successful, non-cancelled outputs. Used by the top-bar export button.
        self._last_outputs: RunOutputs | None = None

        # Tracks whether there are run outputs that have not been exported yet.
        # Used to prompt before switching away from inspection UI (Compose).
        self._have_unexported_outputs = False

        # If the user closes the Distributions dock while a run is active, do not
        # auto-reopen it when the run completes.
        self._dist_dock_closed_during_run = False

        # Auto-open trigger is set on success and executed on `finished` after the
        # UI has transitioned out of the running state.
        self._auto_open_distributions_on_finish = False

        # If the Run button had focus when a run started, restore focus to it
        # after completion so keyboard traversal continues from Run.
        self._restore_focus_to_run_btn = False

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._elapsed_started_at: float | None = None

        self._focus_cycle = FocusCycleController(self)
        self._focus_cycle.install()

        self._build_actions()
        self._build_ui()
        self._wire_controller()

        self.setWindowTitle("LatencyLab")
        # One call settles every action's enabled state and its tooltip: on a
        # cold start nothing has been loaded and nothing has been run, so Run,
        # Cancel, Export and Distributions all open inert and say why.
        self._set_running(False)

    def _build_actions(self) -> None:
        build_menus(
            self,
            on_open_model=self._open_model_dialog,
            on_exit=self.close,
        )

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        top_bar = build_top_bar(
            self,
            on_save_log_clicked=self._on_save_log_clicked,
            on_show_distributions_clicked=self._on_show_distributions_clicked,
            on_show_how_to_read_clicked=lambda: show_how_to_read_dialog(self),
            on_toggle_model_composer_clicked=self._on_toggle_model_composer_clicked,
            on_theme_changed=self._on_theme_changed,
        )
        self._save_log_btn = top_bar.save_log_btn
        self._distributions_btn = top_bar.distributions_btn
        self._how_to_read_btn = top_bar.how_to_read_btn
        self._compose_btn = top_bar.compose_btn
        self._top_badge = top_bar.badge
        self._theme_toggle = top_bar.theme_toggle

        root_layout.addWidget(top_bar.widget)

        # Right-side distributions panel (dockable, non-modal).
        self._distributions_dock = DistributionsDock(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._distributions_dock
        )
        self._distributions_dock.setVisible(False)
        self._distributions_dock.visibilityChanged.connect(
            self._on_distributions_visibility_changed
        )

        # Right-side model composer dock (authoring-only; default hidden).
        self._model_composer_dock = ModelComposerDock(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._model_composer_dock
        )
        self._model_composer_dock.setVisible(False)
        self._model_composer_dock.visibilityChanged.connect(
            self._on_model_composer_visibility_changed
        )

        # Main content.
        #
        # Summary + Critical path are intentionally colocated with Run (left panel)
        # so they stay readable when the Distributions dock is open.
        root_layout.addWidget(build_left_panel(self), 1)

        status = QStatusBar()
        self.setStatusBar(status)
        self._busy_bar = QProgressBar()
        self._busy_bar.setFixedWidth(160)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setRange(0, 0)
        status.addPermanentWidget(self._busy_bar)

        self._status_label = QLabel("Ready")
        status.addWidget(self._status_label, 1)

        self._elapsed_label = QLabel("")
        status.addPermanentWidget(self._elapsed_label)

        # Availability is settled once, at the end of __init__, rather than
        # piecemeal as each control is built.

    # Panel builders live in latencylab_ui/main_window_panels.py.

    def _wire_controller(self) -> None:
        self._controller.started.connect(self._on_run_started)
        self._controller.succeeded.connect(self._on_run_succeeded)
        self._controller.failed.connect(self._on_run_failed)
        self._controller.finished.connect(self._on_run_finished)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # If a simulation is active, wait for completion to avoid:
        #   QThread: Destroyed while thread '' is still running
        self._focus_cycle.uninstall()
        self._controller.shutdown()
        super().closeEvent(event)

    def _on_theme_changed(self, theme: Theme) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme)

    def _open_model_dialog(self) -> None:
        _open_model_dialog(self)

    def _on_save_log_clicked(self) -> None:
        _on_save_log_clicked(self)

    def _on_show_distributions_clicked(self) -> None:
        if not self._distributions_btn.isEnabled():
            return
        self._show_distributions_dock()

    def _on_toggle_model_composer_clicked(self) -> None:
        try:
            toggle_or_switch_to_model_composer(self)
        except RuntimeError:  # pragma: no cover
            return  # pragma: no cover

    def _on_model_composer_visibility_changed(self, visible: bool) -> None:
        # The button is held, not looked up. A findChild by name wrapped in a
        # bare except cannot tell "the composer moved" from "the name changed",
        # so a rename would have silently stopped the button tracking the dock.
        self._compose_btn.setChecked(visible)

    def _show_distributions_dock(self) -> None:
        try:
            self._distributions_dock.show()
            self._distributions_dock.raise_()
        except RuntimeError:  # pragma: no cover
            return  # pragma: no cover

    def _on_distributions_visibility_changed(self, visible: bool) -> None:
        if self._controller.is_running() and not visible:
            self._dist_dock_closed_during_run = True

    def _refresh_actions(self, *, running: bool | None = None) -> None:
        """Apply the availability rules, and say why where they say no.

        Every control that can be inert is refreshed together from the same
        three facts. Refreshing them one at a time is how the Run button ended
        up as the only one whose availability did not track the model.
        """

        if running is None:
            running = self._controller.is_running()
        model_loaded = self._loaded_model is not None
        state = actions.availability(
            running=running,
            model_loaded=model_loaded,
            have_outputs=self._last_outputs is not None,
        )

        self._run_btn.setEnabled(state.run)
        self._run_btn.setToolTip(
            actions.run_tooltip(running=running, model_loaded=model_loaded)
        )
        self._cancel_btn.setEnabled(state.cancel)
        self._cancel_btn.setToolTip(actions.cancel_tooltip(running=running))
        self._runs_spin.setEnabled(state.inputs)
        self._seed_spin.setEnabled(state.inputs)
        self._save_log_btn.setEnabled(state.save_log)
        self._save_log_btn.setToolTip(actions.save_tooltip(available=state.save_log))
        self._distributions_btn.setEnabled(state.distributions)
        self._distributions_btn.setToolTip(
            actions.distributions_tooltip(available=state.distributions)
        )

    def _load_model(self, path: Path) -> None:
        _load_model(self, path)

    def _set_model_load_failed(
        self, path: Path, *, version_text: str, validation_text: str
    ) -> None:
        self._loaded_model = None
        self._model_path_label.setText(str(path))
        self._model_version_label.setText(version_text)
        self._model_valid_label.setText(validation_text)
        self._refresh_actions()

    def _set_model_load_ok(self, path: Path, model: Model) -> None:
        self._loaded_model = _LoadedModel(path=path, model=model)
        self._model_path_label.setText(str(path))
        self._model_version_label.setText(str(model.version))
        self._model_valid_label.setText("OK")
        self._refresh_actions()

    def _on_run_clicked(self) -> None:
        # If the run was initiated via the Run button (mouse/keyboard), restore
        # focus to it once the run finishes so keyboard traversal continues
        # from the expected control.
        self._restore_focus_to_run_btn = self.sender() is self._run_btn

        # Preconditions, not error reporting. The button is disabled and wearing
        # a red ring in both of these cases, so there is nothing left to tell
        # the user that they cannot already see; the old "No model" dialog
        # interrupted them to say what the button should have said all along.
        if self._loaded_model is None or self._controller.is_running():
            return

        req = RunRequest(
            model_path=self._loaded_model.path,
            runs=int(self._runs_spin.value()),
            seed=int(self._seed_spin.value()),
            max_tasks_per_run=panels.MAX_TASKS_PER_RUN,
            want_trace=False,
        )
        self._active_cancelled = False
        self._active_run_token = self._controller.start(req)

    def _on_cancel_clicked(self) -> None:
        if not self._controller.is_running():
            return
        self._active_cancelled = True
        self._controller.cancel_active()
        self._status_label.setText("Cancelling (will discard results when finished)…")

    def _on_run_started(self, run_token: int) -> None:
        self._active_run_token = run_token
        self._dist_dock_closed_during_run = False
        self._auto_open_distributions_on_finish = False
        self._set_running(True)
        self._status_label.setText("Running…")
        self._elapsed_started_at = time.monotonic()
        self._elapsed_label.setText("0.0s")
        self._elapsed_timer.start()

    def _on_run_succeeded(self, run_token: int, outputs_obj: object) -> None:
        if self._controller.is_cancelled(run_token) or self._active_cancelled:
            # Discard per v1 cancel semantics.
            return
        if isinstance(outputs_obj, RunOutputs):
            self._last_outputs = outputs_obj
            self._have_unexported_outputs = True
            self._outputs_view.render(outputs_obj)
            self._run_select.setEnabled(True)

            # Refreshed against the controller's ACTUAL state, which is still
            # running at this point: `succeeded` arrives before `finished`.
            # Claiming otherwise here is what previously let the export button
            # arm mid-run while the distributions button correctly did not.
            self._refresh_actions()

            # Render distributions from the same deterministic outputs.
            self._distributions_dock.render(outputs_obj)
        self._status_label.setText("Completed")

        # Auto-open exactly once per successful completion, unless the user closed
        # the dock during the active run. We delay the open until `finished` so the
        # UI is no longer in the running state.
        self._auto_open_distributions_on_finish = not self._dist_dock_closed_during_run

    def _on_run_failed(self, run_token: int, error_text: str) -> None:
        if self._controller.is_cancelled(run_token) or self._active_cancelled:
            self._status_label.setText("Cancelled")
            return
        self._status_label.setText("Failed")
        QMessageBox.critical(self, "Simulation failed", error_text)
        self._auto_open_distributions_on_finish = False
        self._refresh_actions()

    def _on_run_finished(self, run_token: int, elapsed_seconds: float) -> None:
        self._elapsed_timer.stop()
        self._elapsed_label.setText(f"{elapsed_seconds:0.2f}s")
        self._elapsed_started_at = None
        self._set_running(False)
        if self._controller.is_cancelled(run_token) or self._active_cancelled:
            self._status_label.setText("Cancelled (results discarded)")
            self._auto_open_distributions_on_finish = False
            return

        if self._auto_open_distributions_on_finish and self._last_outputs is not None:
            self._auto_open_distributions_on_finish = False
            self._show_distributions_dock()

    def _set_running(self, running: bool) -> None:
        self._busy_bar.setVisible(running)
        self._refresh_actions(running=running)

        if not running and self._restore_focus_to_run_btn:
            self._restore_focus_to_run_btn = False
            self._run_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_elapsed(self) -> None:
        if not self._controller.is_running() or self._elapsed_started_at is None:
            return
        elapsed = max(0.0, time.monotonic() - self._elapsed_started_at)
        self._elapsed_label.setText(f"{elapsed:0.1f}s")

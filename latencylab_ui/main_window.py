from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QProgressBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from latencylab.model import Model
from latencylab_ui import main_window_actions as actions
from latencylab_ui import main_window_panels as panels
from latencylab_ui import main_window_run as run_lifecycle
from latencylab_ui.attention_flash import AttentionFlash
from latencylab_ui.distributions_dock import DistributionsDock
from latencylab_ui.focus_cycle import FocusCycleController
from latencylab_ui.main_window_dock_switching import (
    open_model_composer,
    toggle_distributions,
)
from latencylab_ui.main_window_editing import (
    open_loaded_model_for_editing,
    refresh_open_editor,
)
from latencylab_ui.main_window_file_io import (
    load_model as _load_model,
)
from latencylab_ui.main_window_file_io import (
    on_save_log_clicked as _on_save_log_clicked,
)
from latencylab_ui.main_window_file_io import (
    open_model_dialog as _open_model_dialog,
)
from latencylab_ui.main_window_menus import (
    build_menus,
    show_guide_dialog,
    show_how_to_read_dialog,
)
from latencylab_ui.main_window_panels import build_left_panel
from latencylab_ui.main_window_top_bar import build_top_bar
from latencylab_ui.model_composer_dialog import ModelComposerDialog
from latencylab_ui.run_controller import RunController, RunOutputs, RunRequest
from latencylab_ui.theme import Theme, apply_theme
from latencylab_ui import update_check


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
        self._edit_action = build_menus(
            self,
            on_open_model=self._open_model_dialog,
            on_open_example=self._load_model,
            on_compose_model=self._on_toggle_model_composer_clicked,
            on_edit_model=self._on_edit_model_clicked,
            on_exit=self.close,
            on_check_updates=lambda: update_check.manual_check(self),
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
            on_show_guide_clicked=lambda: show_guide_dialog(self),
            on_show_how_to_read_clicked=lambda: show_how_to_read_dialog(self),
            on_toggle_model_composer_clicked=self._on_toggle_model_composer_clicked,
            on_edit_model_clicked=self._on_edit_model_clicked,
            on_theme_changed=self._on_theme_changed,
        )
        self._save_log_btn = top_bar.save_log_btn
        self._distributions_btn = top_bar.distributions_btn
        self._guide_btn = top_bar.guide_btn
        self._how_to_read_btn = top_bar.how_to_read_btn
        self._compose_btn = top_bar.compose_btn
        self._edit_btn = top_bar.edit_btn
        self._theme_toggle = top_bar.theme_toggle
        # Held because the band owns the ring order across it: the mark is an
        # overlay, so reading order is not layout order and the band is what
        # states it.
        self._top_bar = top_bar.widget

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

        # The composer is a modal dialog over the whole window rather than a
        # dock down one side. Built once and kept, so a model half-typed
        # survives being closed and reopened.
        self._model_composer = ModelComposerDialog(self)

        # Main content.
        #
        # Summary + Critical path are intentionally colocated with Run (left panel)
        # so they stay readable when the Distributions dock is open.
        root_layout.addWidget(build_left_panel(self), 1)

        # Built here rather than in the panel, because what it points at is a
        # window-level event (a model finished loading) and not the button's
        # own business.
        self._run_flash = AttentionFlash(self._run_btn)

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
        self._controller.cancelled.connect(self._on_run_cancelled)
        self._controller.failed.connect(self._on_run_failed)
        self._controller.finished.connect(self._on_run_finished)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # If a simulation is active, wait for completion to avoid:
        #   QThread: Destroyed while thread '' is still running
        self._focus_cycle.uninstall()
        self._run_flash.stop()
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
            # A checkable button has already flipped itself by the time the
            # click arrives, so refusing the action has to put it back or the
            # button would claim a dock that never opened.
            self._distributions_btn.setChecked(self._distributions_dock.isVisible())
            return
        toggle_distributions(self)

    def _on_toggle_model_composer_clicked(self) -> None:
        # The composer is a held attribute owned by this window, so there is no
        # deleted-object case to guard against here.
        open_model_composer(self)

    def _on_edit_model_clicked(self) -> None:
        open_loaded_model_for_editing(self)

    def _show_distributions_dock(self) -> None:
        self._distributions_dock.show()
        self._distributions_dock.raise_()

    def _on_distributions_visibility_changed(self, visible: bool) -> None:
        # Tracked from the DOCK, not set at the click, so the button still tells
        # the truth when the dock is closed by its own cross or hidden because
        # the composer took the area.
        self._distributions_btn.setChecked(visible)
        if self._controller.is_running() and not visible:
            self._dist_dock_closed_during_run = True

    def _refresh_actions(self, *, running: bool | None = None) -> None:
        """Apply the availability rules, saying why where they say no.

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
        self._edit_btn.setEnabled(state.edit_model)
        self._edit_btn.setToolTip(actions.edit_tooltip(available=state.edit_model))
        self._edit_action.setEnabled(state.edit_model)

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
        refresh_open_editor(self)
        # After the refresh, never before: Run is only enabled by that call, and
        # the flash declines to point at a control that is still disabled.
        self._run_flash.start()

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
        self._status_label.setText(actions.CANCELLING_STATUS)

    def _on_run_cancelled(self, run_token: int, completed_runs: int) -> None:
        """The run stopped because it was asked to, which is not a failure.

        How far it got is worth saying: the stop happens at a run boundary, so
        the number is exact rather than approximate; it tells the user
        whether Cancel caught the run early or nearly at the end.
        """

        self._status_label.setText(actions.cancelled_status(completed_runs))
        self._auto_open_distributions_on_finish = False

    def _on_run_started(self, run_token: int) -> None:
        run_lifecycle.on_run_started(self, run_token)

    def _on_run_succeeded(self, run_token: int, outputs_obj: object) -> None:
        run_lifecycle.on_run_succeeded(self, run_token, outputs_obj)

    def _on_run_failed(self, run_token: int, error_text: str) -> None:
        run_lifecycle.on_run_failed(self, run_token, error_text)

    def _on_run_finished(self, run_token: int, elapsed_seconds: float) -> None:
        run_lifecycle.on_run_finished(self, run_token, elapsed_seconds)

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

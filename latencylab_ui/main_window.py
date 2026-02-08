from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QSplitter,
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
from latencylab_ui.outputs_view import OutputsView
from latencylab_ui.focus_cycle import FocusCycleController
from latencylab_ui.main_window_menus import build_menus
from latencylab_ui.theme import Theme, apply_theme
from latencylab_ui.main_window_top_bar import build_top_bar
from latencylab_ui.main_window_panels import build_left_panel
from latencylab_ui.distributions_dock import DistributionsDock


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
        self._set_running(False)
        # v1 requirement: export button disabled until first successful run.
        self._save_log_btn_refresh_enabled_state(running=False)

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

        (
            top_bar,
            self._save_log_btn,
            self._distributions_btn,
            self._top_clock,
            self._theme_toggle,
        ) = build_top_bar(
            self,
            focus_cycle=self._focus_cycle,
            on_save_log_clicked=self._on_save_log_clicked,
            on_show_distributions_clicked=self._on_show_distributions_clicked,
        )

        root_layout.addWidget(top_bar)

        # Right-side distributions panel (dockable, non-modal).
        self._distributions_dock = DistributionsDock(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._distributions_dock)
        self._distributions_dock.setVisible(False)
        self._distributions_dock.visibilityChanged.connect(self._on_distributions_visibility_changed)

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

        # v1 requirement: distributions button disabled until first successful run.
        self._distributions_btn_refresh_enabled_state(running=False)

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
        if not self._distributions_btn_is_enabled():
            return
        self._show_distributions_dock()

    def _show_distributions_dock(self) -> None:
        try:
            self._distributions_dock.show()
            self._distributions_dock.raise_()
        except RuntimeError:  # pragma: no cover
            return  # pragma: no cover

    def _on_distributions_visibility_changed(self, visible: bool) -> None:
        if self._controller.is_running() and not visible:
            self._dist_dock_closed_during_run = True

    def _distributions_btn_is_enabled(self) -> bool:
        try:
            return bool(self._distributions_btn.isEnabled())
        except Exception:  # noqa: BLE001  # pragma: no cover
            return False  # pragma: no cover

    def _distributions_btn_refresh_enabled_state(self, *, running: bool) -> None:
        # Enabled iff we have a last successful output AND no run is currently active.
        enabled = (self._last_outputs is not None) and (not running)
        self._distributions_btn.setEnabled(enabled)

    def _save_log_btn_refresh_enabled_state(self, *, running: bool) -> None:
        # Enabled iff we have a last successful output AND no run is currently active.
        # This prevents exporting an empty/placeholder state before the first run.
        enabled = (self._last_outputs is not None) and (not running)
        self._save_log_btn.setEnabled(enabled)

    def _load_model(self, path: Path) -> None:
        _load_model(self, path)

    def _set_model_load_failed(
        self, path: Path, *, version_text: str, validation_text: str
    ) -> None:
        self._loaded_model = None
        self._model_path_label.setText(str(path))
        self._model_version_label.setText(version_text)
        self._model_valid_label.setText(validation_text)

    def _set_model_load_ok(self, path: Path, model: Model) -> None:
        self._loaded_model = _LoadedModel(path=path, model=model)
        self._model_path_label.setText(str(path))
        self._model_version_label.setText(str(model.version))
        self._model_valid_label.setText("OK")

    def _on_run_clicked(self) -> None:
        # If the run was initiated via the Run button (mouse/keyboard), restore
        # focus to it once the run finishes so keyboard traversal continues
        # from the expected control.
        self._restore_focus_to_run_btn = self.sender() is self._run_btn

        if self._loaded_model is None:
            QMessageBox.warning(self, "No model", "Open a model JSON file first.")
            return
        if self._controller.is_running():
            return

        req = RunRequest(
            model_path=self._loaded_model.path,
            runs=int(self._runs_spin.value()),
            seed=int(self._seed_spin.value()),
            max_tasks_per_run=200_000,
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
            self._outputs_view.render(outputs_obj)
            self._run_select.setEnabled(True)

            # Post-run actions now become available.
            self._save_log_btn_refresh_enabled_state(running=False)

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
        self._save_log_btn_refresh_enabled_state(running=False)

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
        self._run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._runs_spin.setEnabled(not running)
        self._seed_spin.setEnabled(not running)

        # During a run we disable post-run inspection actions.
        self._save_log_btn_refresh_enabled_state(running=running)
        self._distributions_btn_refresh_enabled_state(running=running)

        if not running and self._restore_focus_to_run_btn:
            self._restore_focus_to_run_btn = False
            self._run_btn.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_elapsed(self) -> None:
        if not self._controller.is_running() or self._elapsed_started_at is None:
            return
        elapsed = max(0.0, time.monotonic() - self._elapsed_started_at)
        self._elapsed_label.setText(f"{elapsed:0.1f}s")


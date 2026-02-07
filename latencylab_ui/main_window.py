from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
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
from latencylab.validate import ModelValidationError, validate_model

from latencylab_ui.run_controller import RunController, RunOutputs, RunRequest
from latencylab_ui.outputs_view import OutputsView
from latencylab_ui.theme import Theme, apply_theme
from latencylab_ui.theme_toggle import ThemeToggle


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

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(200)
        self._elapsed_timer.timeout.connect(self._update_elapsed)
        self._elapsed_started_at: float | None = None

        self._build_actions()
        self._build_ui()
        self._wire_controller()

        self.setWindowTitle("LatencyLab")
        self._set_running(False)

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_action = file_menu.addAction("Open model…")
        open_action.triggered.connect(self._open_model_dialog)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(10, 2, 10, 2)
        top_bar_layout.setSpacing(8)

        self._save_log_btn = QPushButton("💾")
        self._save_log_btn.setToolTip("Save log…")
        self._save_log_btn.setProperty("role", "icon-action")
        self._save_log_btn.clicked.connect(self._on_save_log_clicked)
        top_bar_layout.addWidget(self._save_log_btn)
        top_bar_layout.addStretch(1)

        self._theme_toggle = ThemeToggle(default=Theme.DARK, parent=self)
        self._theme_toggle.theme_changed.connect(self._on_theme_changed)
        top_bar_layout.addWidget(self._theme_toggle)

        root_layout.addWidget(top_bar)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 740])

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

    def _build_left_panel(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)

        model_box = QGroupBox("Model")
        model_form = QFormLayout(model_box)
        model_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._model_path_label = QLabel("(none)")
        self._model_path_label.setWordWrap(True)
        model_form.addRow("Path", self._model_path_label)

        self._model_version_label = QLabel("-")
        model_form.addRow("Schema version", self._model_version_label)

        self._model_valid_label = QLabel("-")
        model_form.addRow("Validation", self._model_valid_label)

        open_btn = QPushButton("Open model…")
        open_btn.clicked.connect(self._open_model_dialog)
        model_form.addRow("", open_btn)

        run_box = QGroupBox("Run")
        run_form = QFormLayout(run_box)
        run_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._runs_spin = QSpinBox()
        self._runs_spin.setRange(1, 1_000_000)
        self._runs_spin.setValue(200)
        run_form.addRow("Runs", self._runs_spin)

        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(0, 2**31 - 1)
        self._seed_spin.setValue(1)
        run_form.addRow("Seed", self._seed_spin)

        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)

        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._on_run_clicked)
        btn_row_layout.addWidget(self._run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setToolTip(
            "Cancel does not interrupt the simulation. Results will be discarded when it finishes."
        )
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row_layout.addWidget(self._cancel_btn)
        run_form.addRow("", btn_row)

        note = QLabel(
            "Cancel discards results after completion\n(no mid-run stop in v1)."
        )
        note.setWordWrap(True)
        run_form.addRow("", note)

        layout.addWidget(model_box)
        layout.addWidget(run_box)
        layout.addStretch(1)
        return root

    def _build_right_panel(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)

        summary_box = QGroupBox("Summary")
        summary_policy = summary_box.sizePolicy()
        summary_policy.setVerticalStretch(3)
        summary_box.setSizePolicy(summary_policy)
        summary_layout = QVBoxLayout(summary_box)
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setPlaceholderText("Run a simulation to see summary metrics.")
        summary_layout.addWidget(self._summary_text)

        crit_box = QGroupBox("Critical path")
        crit_policy = crit_box.sizePolicy()
        crit_policy.setVerticalStretch(1)
        crit_box.setSizePolicy(crit_policy)
        crit_layout = QVBoxLayout(crit_box)

        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.addWidget(QLabel("Run"))

        self._run_select = QComboBox()
        top_row_layout.addWidget(self._run_select, 1)
        crit_layout.addWidget(top_row)

        self._critical_path_text = QPlainTextEdit()
        self._critical_path_text.setReadOnly(True)
        self._critical_path_text.setPlaceholderText("No critical path yet.")
        crit_layout.addWidget(self._critical_path_text)

        self._outputs_view = OutputsView(
            summary_text=self._summary_text,
            run_select=self._run_select,
            critical_path_text=self._critical_path_text,
        )
        self._run_select.currentIndexChanged.connect(self._outputs_view.on_run_selected)

        summary_crit_splitter = QSplitter(Qt.Orientation.Vertical)
        summary_crit_splitter.setChildrenCollapsible(False)
        summary_crit_splitter.addWidget(summary_box)
        summary_crit_splitter.addWidget(crit_box)
        summary_crit_splitter.setStretchFactor(0, 3)
        summary_crit_splitter.setStretchFactor(1, 1)
        summary_crit_splitter.setCollapsible(0, False)
        summary_crit_splitter.setCollapsible(1, False)

        # Make the right panel scrollable for small windows.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(summary_crit_splitter, 1)
        scroll.setWidget(container)

        layout.addWidget(scroll)
        return root

    def _wire_controller(self) -> None:
        self._controller.started.connect(self._on_run_started)
        self._controller.succeeded.connect(self._on_run_succeeded)
        self._controller.failed.connect(self._on_run_failed)
        self._controller.finished.connect(self._on_run_finished)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # If a simulation is active, wait for completion to avoid:
        #   QThread: Destroyed while thread '' is still running
        self._controller.shutdown()
        super().closeEvent(event)

    def _on_theme_changed(self, theme: Theme) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, theme)

    def _open_model_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open LatencyLab model",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path_str:
            return
        self._load_model(Path(path_str))

    def _on_save_log_clicked(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save log",
            "",
            "Text files (*.txt);;All files (*)",
        )
        if not path_str:
            return

        summary_txt = self._summary_text.toPlainText().strip()
        crit_txt = self._critical_path_text.toPlainText().strip()
        log_txt = (
            "Summary\n"
            "======\n"
            f"{summary_txt}\n\n"
            "Critical path\n"
            "============\n"
            f"{crit_txt}\n"
        )

        try:
            Path(path_str).write_text(log_txt, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", f"Could not save log: {e}")

    def _load_model(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            model = Model.from_json(raw)
            validate_model(model)
        except ModelValidationError as e:
            self._loaded_model = None
            self._model_path_label.setText(str(path))
            self._model_version_label.setText("-")
            self._model_valid_label.setText(f"Invalid: {e}")
            return
        except Exception as e:  # noqa: BLE001
            self._loaded_model = None
            self._model_path_label.setText(str(path))
            self._model_version_label.setText("-")
            self._model_valid_label.setText(f"Error: {e}")
            return

        self._loaded_model = _LoadedModel(path=path, model=model)
        self._model_path_label.setText(str(path))
        self._model_version_label.setText(str(model.version))
        self._model_valid_label.setText("OK")

    def _on_run_clicked(self) -> None:
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
            self._outputs_view.render(outputs_obj)
        self._status_label.setText("Completed")

    def _on_run_failed(self, run_token: int, error_text: str) -> None:
        if self._controller.is_cancelled(run_token) or self._active_cancelled:
            self._status_label.setText("Cancelled")
            return
        self._status_label.setText("Failed")
        QMessageBox.critical(self, "Simulation failed", error_text)

    def _on_run_finished(self, run_token: int, elapsed_seconds: float) -> None:
        self._elapsed_timer.stop()
        self._elapsed_label.setText(f"{elapsed_seconds:0.2f}s")
        self._elapsed_started_at = None
        self._set_running(False)
        if self._controller.is_cancelled(run_token) or self._active_cancelled:
            self._status_label.setText("Cancelled (results discarded)")

    def _set_running(self, running: bool) -> None:
        self._busy_bar.setVisible(running)
        self._run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._runs_spin.setEnabled(not running)
        self._seed_spin.setEnabled(not running)

    def _update_elapsed(self) -> None:
        if not self._controller.is_running() or self._elapsed_started_at is None:
            return
        elapsed = max(0.0, time.monotonic() - self._elapsed_started_at)
        self._elapsed_label.setText(f"{elapsed:0.1f}s")


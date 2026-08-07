from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui import main_window_actions as actions
from latencylab_ui.outputs_view import OutputsView

# How many runs a fresh window offers. Enough that a distribution has a shape,
# few enough that the first run returns while the user is still watching.
DEFAULT_RUNS = 200
MIN_RUNS = 1
MAX_RUNS = 1_000_000

# The seed is an unsigned 32-bit value, which is what the executors mix into
# each run's generator.
DEFAULT_SEED = 1
MIN_SEED = 0
MAX_SEED = 2**31 - 1

# A ceiling on task instances per run, so a model with a runaway loop fails
# loudly instead of consuming the machine.
MAX_TASKS_PER_RUN = 200_000


def build_left_panel(window) -> QWidget:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(10, 10, 10, 10)

    model_box = QGroupBox("Model")
    model_form = QFormLayout(model_box)
    model_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    window._model_path_label = QLabel("(none)")
    window._model_path_label.setWordWrap(True)
    model_form.addRow("Path", window._model_path_label)

    window._model_version_label = QLabel("-")
    model_form.addRow("Schema version", window._model_version_label)

    window._model_valid_label = QLabel("-")
    model_form.addRow("Validation", window._model_valid_label)

    open_btn = QPushButton("Open model…")
    open_btn.clicked.connect(window._open_model_dialog)
    model_form.addRow("", open_btn)

    run_box = QGroupBox("Run")
    run_form = QFormLayout(run_box)
    run_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    window._runs_spin = QSpinBox()
    window._runs_spin.setRange(MIN_RUNS, MAX_RUNS)
    window._runs_spin.setValue(DEFAULT_RUNS)
    run_form.addRow("Runs", window._runs_spin)

    window._seed_spin = QSpinBox()
    window._seed_spin.setRange(MIN_SEED, MAX_SEED)
    window._seed_spin.setValue(DEFAULT_SEED)
    run_form.addRow("Seed", window._seed_spin)

    btn_row = QWidget()
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 0, 0, 0)

    window._run_btn = QPushButton("Run")
    window._run_btn.setToolTip(actions.RUN_NEEDS_MODEL)
    window._run_btn.clicked.connect(window._on_run_clicked)
    btn_row_layout.addWidget(window._run_btn)

    window._cancel_btn = QPushButton("Cancel")
    window._cancel_btn.setToolTip(actions.CANCEL_IDLE)
    window._cancel_btn.clicked.connect(window._on_cancel_clicked)
    btn_row_layout.addWidget(window._cancel_btn)
    run_form.addRow("", btn_row)

    # The standing note that used to sit here explained that Cancel could not
    # interrupt a run. Both buttons now carry their own state in a tooltip, so a
    # permanent paragraph of caveat is not the right place for it.

    # Outputs (moved here to avoid truncation when the Distributions dock is open).
    summary_box = QGroupBox("Summary")
    summary_layout = QVBoxLayout(summary_box)
    window._summary_text = QPlainTextEdit()
    window._summary_text.setReadOnly(True)
    window._summary_text.setPlaceholderText("Run a simulation to see summary metrics.")
    summary_layout.addWidget(window._summary_text)

    crit_box = QGroupBox("Critical path")
    crit_layout = QVBoxLayout(crit_box)

    top_row = QWidget()
    top_row_layout = QHBoxLayout(top_row)
    top_row_layout.setContentsMargins(0, 0, 0, 0)
    top_row_layout.addWidget(QLabel("Run"))

    window._run_select = QComboBox()
    window._run_select.setEnabled(False)
    window._run_select.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    window._run_select.activated.connect(lambda _idx: window._run_select.setFocus())
    top_row_layout.addWidget(window._run_select, 1)
    crit_layout.addWidget(top_row)

    window._critical_path_text = QPlainTextEdit()
    window._critical_path_text.setReadOnly(True)
    window._critical_path_text.setPlaceholderText("No critical path yet.")
    # Wrap long lines so critical-path text is not horizontally truncated.
    window._critical_path_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    window._critical_path_text.setWordWrapMode(
        QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
    )
    window._critical_path_text.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    crit_layout.addWidget(window._critical_path_text)

    window._outputs_view = OutputsView(
        summary_text=window._summary_text,
        run_select=window._run_select,
        critical_path_text=window._critical_path_text,
    )
    window._run_select.currentIndexChanged.connect(window._outputs_view.on_run_selected)

    outputs_row = QWidget()
    outputs_layout = QHBoxLayout(outputs_row)
    outputs_layout.setContentsMargins(0, 0, 0, 0)
    outputs_layout.setSpacing(10)
    outputs_layout.addWidget(summary_box, 1)
    outputs_layout.addWidget(crit_box, 1)

    layout.addWidget(model_box)
    layout.addWidget(run_box)
    layout.addWidget(outputs_row, 1)
    return root


def build_right_panel(window) -> QWidget:
    # Kept for backward compatibility with older tests/imports.
    # The main window no longer adds this panel.
    return QWidget()  # pragma: no cover

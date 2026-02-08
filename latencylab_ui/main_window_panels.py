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
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.outputs_view import OutputsView


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
    window._runs_spin.setRange(1, 1_000_000)
    window._runs_spin.setValue(200)
    run_form.addRow("Runs", window._runs_spin)

    window._seed_spin = QSpinBox()
    window._seed_spin.setRange(0, 2**31 - 1)
    window._seed_spin.setValue(1)
    run_form.addRow("Seed", window._seed_spin)

    btn_row = QWidget()
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 0, 0, 0)

    window._run_btn = QPushButton("Run")
    window._run_btn.clicked.connect(window._on_run_clicked)
    btn_row_layout.addWidget(window._run_btn)

    window._cancel_btn = QPushButton("Cancel")
    window._cancel_btn.setToolTip(
        "Cancel does not interrupt the simulation. Results will be discarded when it finishes."
    )
    window._cancel_btn.clicked.connect(window._on_cancel_clicked)
    btn_row_layout.addWidget(window._cancel_btn)
    run_form.addRow("", btn_row)

    note = QLabel("Cancel discards results after completion\n(no mid-run stop in v1).")
    note.setWordWrap(True)
    run_form.addRow("", note)

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
    window._critical_path_text.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    window._critical_path_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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


from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from latencylab.model import Model
from latencylab.validate import ModelValidationError, validate_model


def open_model_dialog(window) -> None:
    path_str, _ = QFileDialog.getOpenFileName(
        window,
        "Open LatencyLab model",
        "",
        "JSON files (*.json);;All files (*)",
    )
    if not path_str:
        return
    # Call the window method (not the helper) so tests can monkeypatch
    # `MainWindow._load_model` and observe the call.
    window._load_model(Path(path_str))  # noqa: SLF001


def on_save_log_clicked(window) -> None:
    path_str, _ = QFileDialog.getSaveFileName(
        window,
        "Save log",
        "",
        "Text files (*.txt);;All files (*)",
    )
    if not path_str:
        return

    summary_txt = window._summary_text.toPlainText().strip()  # noqa: SLF001
    crit_txt = window._critical_path_text.toPlainText().strip()  # noqa: SLF001
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
        QMessageBox.critical(window, "Save failed", f"Could not save log: {e}")


def load_model(window, path: Path) -> None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        model = Model.from_json(raw)
        validate_model(model)
    except ModelValidationError as e:
        window._set_model_load_failed(path, version_text="-", validation_text=f"Invalid: {e}")  # noqa: SLF001
        return
    except Exception as e:  # noqa: BLE001
        window._set_model_load_failed(path, version_text="-", validation_text=f"Error: {e}")  # noqa: SLF001
        return

    window._set_model_load_ok(path, model)  # noqa: SLF001


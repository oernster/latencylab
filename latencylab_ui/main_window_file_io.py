from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from latencylab.model import Model
from latencylab.validate import ModelValidationError, validate_model
from latencylab_ui.outputs_view import format_summary_text


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
    # Export all runs as a zip of per-run text files.
    path_str, _ = QFileDialog.getSaveFileName(
        window,
        "Export runs",
        "",
        "Zip files (*.zip);;All files (*)",
    )
    if not path_str:
        return

    out_path = Path(path_str)
    if out_path.suffix.lower() != ".zip":
        out_path = out_path.with_suffix(".zip")

    outputs = getattr(window, "_last_outputs", None)  # noqa: SLF001
    if outputs is None:
        QMessageBox.information(window, "Nothing to export", "Run a simulation first.")
        return

    runs = sorted(list(outputs.runs), key=lambda r: int(r.run_id))
    summary_txt = format_summary_text(outputs).strip()

    try:
        with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Summary.txt", f"{summary_txt}\n".encode("utf-8"))
            for r in runs:
                # User-facing filenames are 1-based, zero-padded.
                file_name = f"Run{(int(r.run_id) + 1):04d}.txt"
                status = "failed" if r.failed else "ok"
                failure_reason = r.failure_reason or ""
                header = (
                    f"run_id: {r.run_id}\n"
                    f"status: {status}\n"
                    f"makespan_ms: {r.makespan_ms}\n"
                    f"critical_path_ms: {r.critical_path_ms}\n"
                    f"failure_reason: {failure_reason}\n"
                )

                crit = (r.critical_path_tasks or "").strip()

                body = f"{header}\n{crit}\n"
                zf.writestr(file_name, body.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(window, "Export failed", f"Could not export runs: {e}")


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


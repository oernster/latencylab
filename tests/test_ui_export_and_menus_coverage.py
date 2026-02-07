from __future__ import annotations

import zipfile
from pathlib import Path


def test_export_runs_appends_zip_suffix_and_writes(monkeypatch, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

    from latencylab.model import Model
    from latencylab.types import RunResult
    from latencylab_ui.main_window_file_io import on_save_log_clicked
    from latencylab_ui.run_controller import RunOutputs

    _ = QApplication.instance() or QApplication([])

    # Choose a non-.zip extension; exporter should append .zip.
    chosen = tmp_path / "export.txt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(chosen), "txt"))

    # Ensure no modal dialogs appear.
    called = {"info": False, "critical": False}
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_a, **_k: called.__setitem__("info", True),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *_a, **_k: called.__setitem__("critical", True),
    )

    model = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )

    runs = [
        RunResult(
            run_id=0,
            first_ui_event_time_ms=None,
            last_ui_event_time_ms=None,
            makespan_ms=1.0,
            critical_path_ms=1.0,
            critical_path_tasks="A",
            failed=False,
            failure_reason=None,
        )
    ]

    class _Window(QWidget):
        pass

    w = _Window()
    # UI export accesses the window's last outputs.
    w._last_outputs = RunOutputs(model=model, runs=runs, summary={})  # type: ignore[attr-defined]

    on_save_log_clicked(w)

    # File should exist with .zip suffix.
    out_zip = tmp_path / "export.zip"
    assert out_zip.exists()
    assert not called["info"]
    assert not called["critical"]

    with zipfile.ZipFile(out_zip, "r") as zf:
        assert sorted(zf.namelist()) == ["Run0001.txt", "Summary.txt"]


def test_export_runs_shows_info_if_no_outputs(monkeypatch, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

    from latencylab_ui.main_window_file_io import on_save_log_clicked

    _ = QApplication.instance() or QApplication([])

    out_path = tmp_path / "runs.zip"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(out_path), "zip"),
    )

    called = {"info": False}
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_a, **_k: called.__setitem__("info", True),
    )

    w = QWidget()
    # No _last_outputs attribute => treated as None.
    on_save_log_clicked(w)
    assert called["info"]


def test_show_license_dialogs_set_parent_refs() -> None:
    from PySide6.QtWidgets import QApplication, QWidget

    import latencylab_ui.main_window_menus as menus

    _ = QApplication.instance() or QApplication([])

    parent = QWidget()
    menus.show_licence_dialog(parent)
    assert getattr(parent, "_licence_dialog") is not None

    menus.show_main_licence_dialog(parent)
    assert getattr(parent, "_main_licence_dialog") is not None


from __future__ import annotations

import json
from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_model(tmp_path: Path, *, valid: bool = True) -> Path:
    concurrency = 1 if valid else 0
    raw = {
        "schema_version": 1,
        "entry_event": "e0",
        "contexts": {"ui": {"concurrency": concurrency}},
        "events": {"e0": {"tags": ["ui"]}},
        "tasks": {},
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


def test_main_window_core_paths(monkeypatch, tmp_path: Path) -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.run_controller import RunOutputs

    class _FakeController(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal(int, float)

        def __init__(self) -> None:
            super().__init__()
            self._running = False
            self._cancelled: set[int] = set()
            self._next = 1
            self.last_request = None

        def is_running(self) -> bool:
            return self._running

        def is_cancelled(self, run_token: int) -> bool:
            return run_token in self._cancelled

        def start(self, request) -> int:
            self.last_request = request
            self._running = True
            tok = self._next
            self._next += 1
            return tok

        def cancel_active(self) -> None:
            self._cancelled.add(self._next - 1)

        def shutdown(self) -> None:
            self._running = False

    controller = _FakeController()
    w = MainWindow(run_controller=controller)
    w.show()
    app.processEvents()

    # Top-center clock emoji should exist and be non-interactive.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    clock = w.findChild(QLabel, "top_clock_emoji")
    assert clock is not None
    assert clock.text() == "⏱️"
    assert clock.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert clock.minimumWidth() >= 36

    # Theme toggle route (ensure handler is callable).
    from latencylab_ui.theme import Theme

    w._on_theme_changed(Theme.LIGHT)
    w._on_theme_changed(Theme.DARK)

    # Run clicked: no model.
    w._loaded_model = None
    warned = {"called": False}

    def _warn(*_a, **_k):
        warned["called"] = True

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    w._on_run_clicked()
    assert warned["called"]

    # Cancel clicked: not running.
    controller._running = False
    w._on_cancel_clicked()

    # Open model dialog: cancelled.
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    w._open_model_dialog()

    # Open model dialog: selects a file.
    selected = _write_model(tmp_path, valid=True)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (str(selected), ""),
    )
    seen_path: dict[str, str] = {}

    def _spy_load_model(p: Path) -> None:
        seen_path["p"] = str(p)

    real_load_model = w._load_model
    monkeypatch.setattr(w, "_load_model", _spy_load_model)
    w._open_model_dialog()
    assert seen_path["p"] == str(selected)
    monkeypatch.setattr(w, "_load_model", real_load_model)

    # Load model: invalid JSON -> generic exception path.
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json}", encoding="utf-8")
    w._load_model(bad)

    # Load model: validation error path.
    invalid_model = _write_model(tmp_path, valid=False)
    w._load_model(invalid_model)

    # Load model: success.
    valid_model = _write_model(tmp_path, valid=True)
    w._load_model(valid_model)
    assert w._loaded_model is not None

    # Run clicked: already running.
    controller._running = True
    w._on_run_clicked()

    # Run clicked with model loaded.
    controller._running = False
    w._on_run_clicked()
    assert controller.last_request is not None

    # Started updates status.
    w._on_run_started(1)
    assert w._status_label.text() == "Running…"

    # Succeeded renders.
    outputs = RunOutputs(model=w._loaded_model.model, runs=[], summary={})
    w._on_run_succeeded(1, outputs)
    assert w._status_label.text() == "Completed"

    # Cancel semantics: success after cancel is discarded.
    controller._running = True
    w._on_cancel_clicked()
    w._on_run_succeeded(1, outputs)
    assert w._status_label.text() != "Completed"

    # Reset cancel state so later failure path can show dialog.
    w._active_cancelled = False
    controller._cancelled.clear()

    # Failed shows a dialog.
    seen = {"called": False}

    def _crit(*_a, **_k):
        seen["called"] = True

    monkeypatch.setattr(QMessageBox, "critical", _crit)
    w._on_run_failed(1, "nope")
    assert seen["called"]

    # Failed after cancel: does not show dialog.
    seen["called"] = False
    controller._cancelled.add(1)
    w._on_run_failed(1, "nope")
    assert not seen["called"]
    assert w._status_label.text() == "Cancelled"

    # Finished resets running state.
    w._on_run_finished(1, 0.1)
    assert not w._busy_bar.isVisible()

    # Finished after cancel: updates status.
    w._active_cancelled = True
    w._on_run_finished(1, 0.2)
    assert "Cancelled" in w._status_label.text()

    # Elapsed updater.
    controller._running = True
    w._elapsed_started_at = 0.0
    w._update_elapsed()
    assert w._elapsed_label.text()
    controller._running = False
    prev = w._elapsed_label.text()
    w._update_elapsed()
    assert w._elapsed_label.text() == prev

    # Close event calls shutdown.
    called = {"shutdown": False}
    monkeypatch.setattr(controller, "shutdown", lambda: called.__setitem__("shutdown", True))
    w.close()
    app.processEvents()
    assert called["shutdown"]


def test_save_log_button_dumps_right_panel(monkeypatch, tmp_path: Path) -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox, QPushButton

    from PySide6.QtCore import QObject, Signal

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.run_controller import RunOutputs
    from latencylab.types import RunResult
    from latencylab.model import Model

    class _Controller(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal(int, float)

        def is_running(self) -> bool:
            return False

        def is_cancelled(self, _token: int) -> bool:
            return False

        def shutdown(self) -> None:
            return None

    w = MainWindow(run_controller=_Controller())
    w.show()
    app.processEvents()

    # Find the save button in the top bar (just below the menu).
    matches = w.findChildren(QPushButton)
    btns = [b for b in matches if "💾" in b.text()]
    assert btns
    btn = btns[0]

    assert "💾" in btn.text()

    # Seed right panel content.
    w._summary_text.setPlainText("SUMMARY\nline2")
    w._critical_path_text.setPlainText("CRIT\nlineB")

    # Cancel path: no dialog, no write.
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    crit_called = {"called": False}
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *_a, **_k: crit_called.__setitem__("called", True),
    )
    btn.click()
    assert not crit_called["called"]

    # Success path: writes expected content.
    out_path = tmp_path / "runs.zip"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(out_path), "zip"),
    )

    # Seed last outputs (what the export uses).
    m = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )

    w._last_outputs = RunOutputs(
        model=m,
        summary={},
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=123.0,
                critical_path_ms=50.0,
                critical_path_tasks="A>B>C",
                failed=False,
                failure_reason=None,
            ),
            RunResult(
                run_id=1,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=999.0,
                critical_path_ms=0.0,
                critical_path_tasks="",
                failed=True,
                failure_reason="boom",
            ),
        ],
    )

    btn.click()

    import zipfile

    with zipfile.ZipFile(out_path, "r") as zf:
        names = sorted(zf.namelist())
        assert names == ["Run0001.txt", "Run0002.txt", "Summary.txt"]

        r1 = zf.read("Run0001.txt").decode("utf-8")
        assert "run_id: 0" in r1
        assert "status: ok" in r1
        assert "makespan_ms: 123.0" in r1
        assert "critical_path_ms: 50.0" in r1
        assert "failure_reason:" in r1
        assert "A>B>C" in r1

        r2 = zf.read("Run0002.txt").decode("utf-8")
        assert "run_id: 1" in r2
        assert "status: failed" in r2
        assert "failure_reason: boom" in r2

        summary = zf.read("Summary.txt").decode("utf-8")
        assert "Model schema_version" in summary
        assert "Top critical paths:" in summary

    # Error path: shows error dialog.
    from pathlib import Path as _P

    import zipfile as _zf

    monkeypatch.setattr(
        _zf,
        "ZipFile",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("no")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(tmp_path / "err.zip"), "zip"),
    )
    btn.click()
    assert crit_called["called"]


def test_ui_focus_cycle_covered_elsewhere() -> None:
    # Kept intentionally minimal: focus-cycle behavior tests moved to
    # [`tests/test_ui_main_window_focus_cycle.py`](tests/test_ui_main_window_focus_cycle.py:1)
    # to keep each file <= 400 lines.
    assert True



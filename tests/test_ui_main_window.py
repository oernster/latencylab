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


# The main window's core paths. The save-log button is in
# test_ui_main_window_save_log.py.


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
        cancelled = Signal(int, int)
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

    # The centre mark is the generated application mark, never a font glyph,
    # and it is the distributions toggle rather than decoration.
    from PySide6.QtWidgets import QPushButton as _QPushButton

    mark = w.findChild(_QPushButton, "distributions_btn")
    assert mark is not None
    assert mark.text() == ""
    assert mark.icon().isNull() is False
    assert mark.isCheckable() is True
    # A minimum width rather than a fixed size: a mark that collapses when the
    # icon set is missing would move the thing it is supposed to centre, and
    # fixing the height too would clip the frame the stylesheet computes.
    assert mark.minimumWidth() >= 36

    # Top bar: How-to-read info button should exist and be enabled.
    from PySide6.QtWidgets import QPushButton

    info_btn = w.findChild(QPushButton, "how_to_read_btn")
    assert info_btn is not None
    assert "ℹ️" in info_btn.text()
    assert info_btn.isEnabled() is True

    # Theme toggle route (ensure handler is callable).
    from latencylab_ui.theme import Theme

    w._on_theme_changed(Theme.LIGHT)
    w._on_theme_changed(Theme.DARK)

    # No model: Run is inert and says so, rather than being pressable and then
    # interrupting with a dialog to explain what it should have shown.
    from latencylab_ui import main_window_actions as actions

    w._loaded_model = None
    w._refresh_actions()

    assert w._run_btn.isEnabled() is False
    assert w._run_btn.toolTip() == actions.RUN_NEEDS_MODEL

    warned = {"called": False}

    def _warn(*_a, **_k):
        warned["called"] = True

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    w._on_run_clicked()
    assert warned["called"] is False, "the no-model dialog should be gone"

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

    # Distributions button remains disabled until we have last successful outputs
    # *and* we are not running. Succeeded alone should not enable it.
    assert w._distributions_btn.isEnabled() is False

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

    # After finish, the distributions button becomes enabled for inspection.
    assert w._distributions_btn.isEnabled() is True

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
    monkeypatch.setattr(
        controller, "shutdown", lambda: called.__setitem__("shutdown", True)
    )
    w.close()
    app.processEvents()
    assert called["shutdown"]


def test_ui_focus_cycle_covered_elsewhere() -> None:
    # Kept intentionally minimal: focus-cycle behavior tests moved to
    # [`tests/test_ui_main_window_focus_cycle.py`](tests/test_ui_main_window_focus_cycle.py:1)
    # to keep each file <= 400 lines.
    assert True

from __future__ import annotations

from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# Saving the right-hand panel's log to a file, split out of
# test_ui_main_window.py on size.


def test_save_log_button_dumps_right_panel(monkeypatch, tmp_path: Path) -> None:
    app = _ensure_qapp()

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
        cancelled = Signal(int, int)
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

    # Requirement: export disabled until first successful run.
    assert btn.isEnabled() is False

    # Seed right panel content.
    w._summary_text.setPlainText("SUMMARY\nline2")
    w._critical_path_text.setPlainText("CRIT\nlineB")

    # Cancel path: button disabled, click should do nothing.
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

    # Enable export now that we have outputs.
    w._refresh_actions(running=False)

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

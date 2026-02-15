from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_distributions_button_disabled_until_success_then_finished_enables_and_auto_opens(
    monkeypatch,
) -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal

    from latencylab.model import Model
    from latencylab.types import RunResult
    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.run_controller import RunOutputs

    class _Controller(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal(int, float)

        def __init__(self) -> None:
            super().__init__()
            self._running = False

        def is_running(self) -> bool:
            return self._running

        def is_cancelled(self, _token: int) -> bool:
            return False

        def shutdown(self) -> None:
            return None

    c = _Controller()
    w = MainWindow(run_controller=c)
    w.show()
    app.processEvents()

    # Pre-run: disabled and dock hidden.
    assert w._distributions_btn.isEnabled() is False
    assert w._distributions_dock.isVisible() is False

    model = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )
    outputs = RunOutputs(
        model=model,
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=1.0,
                critical_path_ms=1.0,
                critical_path_tasks="A>B",
                failed=False,
                failure_reason=None,
            )
        ],
        summary={
            "latency_ms": {
                "makespan": {"p50": 1.0, "p90": 1.0, "p95": 1.0, "p99": 1.0}
            }
        },
    )

    # Success alone should NOT enable (we only enable when not running), but it
    # should arm the auto-open-on-finish.
    w._on_run_succeeded(1, outputs)
    assert w._distributions_btn.isEnabled() is False
    assert w._auto_open_distributions_on_finish is True

    # Finish transitions out of running and triggers the auto-open.
    w._on_run_finished(1, 0.1)
    app.processEvents()

    assert w._distributions_btn.isEnabled() is True
    assert w._distributions_dock.isVisible() is True

    # Compose should switch to the composer. Because the run has not been exported,
    # it should prompt first.
    from PySide6.QtWidgets import QMessageBox

    called = {"question": 0}

    def _question(*_a, **_k):
        called["question"] += 1
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", _question)

    # Cancel should keep the existing results layout.
    w._on_toggle_model_composer_clicked()
    app.processEvents()
    assert called["question"] == 1
    assert w._distributions_dock.isVisible() is True

    # Now allow the switch (No = don't export, but proceed).
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)
    w._on_toggle_model_composer_clicked()
    app.processEvents()
    assert w._distributions_dock.isVisible() is False
    assert w._model_composer_dock.isVisible() is True

    # If distributions is shown while composer is already visible, clicking
    # Compose should still switch to composer (hide distributions), not toggle off.
    w._on_show_distributions_clicked()
    app.processEvents()
    assert w._distributions_dock.isVisible() is True
    assert w._model_composer_dock.isVisible() is True

    # No prompt now (we already chose No, leaving outputs as "unexported", but
    # for test determinism we accept either path by forcing No again).
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)
    w._on_toggle_model_composer_clicked()
    app.processEvents()
    assert w._distributions_dock.isVisible() is False
    assert w._model_composer_dock.isVisible() is True

    w.close()
    app.processEvents()


def test_distributions_button_click_gate_and_manual_open() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal

    from latencylab.model import Model
    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.run_controller import RunOutputs

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

    # Disabled gate: click handler should do nothing.
    w._on_show_distributions_clicked()
    assert w._distributions_dock.isVisible() is False

    # Enable by seeding last outputs and reapplying not-running state.
    m = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )
    w._last_outputs = RunOutputs(model=m, runs=[], summary={})
    w._set_running(False)
    assert w._distributions_btn_is_enabled() is True

    # Manual open: should show the dock.
    w._on_show_distributions_clicked()
    app.processEvents()
    assert w._distributions_dock.isVisible() is True

    w.close()
    app.processEvents()


def test_distributions_visibility_change_sets_closed_during_run_flag() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal

    from latencylab_ui.main_window import MainWindow

    class _Controller(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal(int, float)

        def __init__(self) -> None:
            super().__init__()
            self._running = True

        def is_running(self) -> bool:
            return self._running

        def is_cancelled(self, _token: int) -> bool:
            return False

        def shutdown(self) -> None:
            return None

    w = MainWindow(run_controller=_Controller())
    w.show()
    app.processEvents()

    assert w._dist_dock_closed_during_run is False
    w._on_distributions_visibility_changed(False)
    assert w._dist_dock_closed_during_run is True

    w.close()
    app.processEvents()


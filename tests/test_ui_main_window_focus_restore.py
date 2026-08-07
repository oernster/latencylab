from __future__ import annotations

"""Focus restoration: where focus lands after a click or after a run.

Split out of the traversal tests, which had grown past the 400-line cap.
Traversal asks where Tab goes; this asks where focus RETURNS to, which is a
different question and answered by different code.
"""


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _load_a_model(window) -> None:
    """Give the window a model so Run is a live ring stop.

    Run is disabled, and therefore skipped by the ring, until a model is open.
    A traversal test with no model open is testing a shorter ring than the one
    the user sees the moment they have something to run.
    """

    from pathlib import Path as _Path

    from latencylab.model import Model

    window._set_model_load_ok(
        _Path("model.json"),
        Model.from_json(
            {
                "schema_version": 1,
                "entry_event": "e0",
                "contexts": {"ui": {"concurrency": 1}},
                "events": {"e0": {"tags": ["ui"]}},
                "tasks": {},
            }
        ),
    )


def test_tab_after_mouse_focus_does_not_restart_at_menu() -> None:
    """If the user clicks a control (e.g. Run) before using Tab, traversal
    should continue from that control rather than restarting at the menu.
    """

    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.main_window import MainWindow

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
    w.activateWindow()
    app.processEvents()
    _load_a_model(w)

    # Simulate mouse focus on Run.
    w._run_btn.setFocus(Qt.FocusReason.MouseFocusReason)
    app.processEvents()
    assert QApplication.focusWidget() is w._run_btn

    # Run is the last enabled widget pre-run; pressing Tab should wrap.
    QTest.keyClick(w._run_btn, Qt.Key_Tab)
    app.processEvents()
    assert QApplication.focusWidget() is w

    w.close()
    app.processEvents()


def test_run_button_focus_restored_after_run_finishes_when_requested() -> None:
    """Cover the post-run focus restoration branch.

    Requirement: after a run initiated from the Run button finishes, keyboard
    traversal should continue from Run (focus should be restored to the Run
    button rather than effectively resetting).
    """

    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.main_window import MainWindow

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
    w.activateWindow()
    app.processEvents()
    _load_a_model(w)

    # Simulate the "run started from Run button" condition.
    w._restore_focus_to_run_btn = True

    # Simulate run completion toggling running=False.
    w._set_running(False)
    app.processEvents()

    assert w._restore_focus_to_run_btn is False
    assert QApplication.focusWidget() is w._run_btn

    w.close()
    app.processEvents()

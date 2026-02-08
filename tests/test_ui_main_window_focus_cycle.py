from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_focus_cycle_tab_order_and_arrow_keys(monkeypatch) -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton

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
    w.setFocus()
    app.processEvents()

    def _focused_widget_text() -> str:
        fw = QApplication.focusWidget()
        if isinstance(fw, QPushButton):
            return fw.text()
        return type(fw).__name__ if fw is not None else "(none)"

    def _send(key: Qt.Key, modifier: Qt.KeyboardModifier = Qt.NoModifier) -> None:
        target = QApplication.focusWidget() or w
        QTest.keyClick(target, key, modifier)
        app.processEvents()

    def _wait_for_focus_text(expected: str) -> None:
        # Menu->widget focus transitions can be slightly delayed by Qt depending
        # on platform/style (popup teardown etc.).
        for _ in range(20):
            if _focused_widget_text() == expected:
                return
            app.processEvents()
        assert _focused_widget_text() == expected

    # Pre-Tab: nothing selected (no active menu title, no focused child control).
    assert w.menuBar().activeAction() is None
    for btn in w.findChildren(QPushButton):
        assert not btn.hasFocus(), f"Unexpected focused button pre-Tab: {btn.text()}"

    # Arrow keys before first Tab should do nothing.
    _send(Qt.Key_Right)
    assert w.menuBar().activeAction() is None
    assert all(not b.hasFocus() for b in w.findChildren(QPushButton))

    # Start cycle: first Tab selects the first menu title.
    _send(Qt.Key_Tab)
    assert w.menuBar().activeAction() is not None
    assert w.menuBar().activeAction().text() == "File"

    # Next Tab advances to the next menu title.
    _send(Qt.Key_Tab)
    assert w.menuBar().activeAction() is not None
    assert w.menuBar().activeAction().text() == "Help"

    # If the user opens a menu with Down/Up, Tab must escape out to the widgets
    # (not trap them inside menu navigation).
    _send(Qt.Key_Down)
    _send(Qt.Key_Tab)
    # Export is disabled until first successful run, so focus skips it.
    _wait_for_focus_text("☀")

    # Distributions button exists but is disabled until a successful run
    # completes, so it is intentionally skipped by the focus-cycle.

    # Theme toggle is a single focus stop; it is toggled with Space, not Tab.
    _send(Qt.Key_Tab)
    assert _focused_widget_text() == "Open model…"

    _send(Qt.Key_Tab)
    assert QApplication.focusWidget() is w._runs_spin

    _send(Qt.Key_Tab)
    assert QApplication.focusWidget() is w._seed_spin

    _send(Qt.Key_Tab)
    assert _focused_widget_text() == "Run"

    _send(Qt.Key_Tab)
    # Run selector is disabled (not tabbable) until a run has been performed.
    assert w._run_select.isEnabled() is False
    assert w.menuBar().activeAction() is not None
    assert w.menuBar().activeAction().text() == "File"

    # Wrap-around.
    _send(Qt.Key_Tab)
    assert w.menuBar().activeAction() is not None
    assert w.menuBar().activeAction().text() == "Help"

    _send(Qt.Key_Tab)
    assert _focused_widget_text() == "☀"

    # Ensure a Help menu exists (covered earlier: File -> Help).

    # Backwards traversal is covered elsewhere; keep this test focused on the
    # forward traversal rules and menu-escape behavior.

    # Ensure clean teardown (uninstall event filter via closeEvent).
    w.close()
    app.processEvents()


def test_current_run_selection_keeps_focus_until_tab() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from latencylab.model import Model
    from latencylab.types import RunResult
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
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    model = Model.from_json(
        {
            "schema_version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {},
        }
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
                critical_path_tasks="t0",
                failed=False,
                failure_reason=None,
            ),
            RunResult(
                run_id=1,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=2.0,
                critical_path_ms=2.0,
                critical_path_tasks="t1",
                failed=False,
                failure_reason=None,
            ),
        ],
        summary={},
    )
    w._on_run_succeeded(1, outputs)
    assert w._run_select.isEnabled()

    w._run_select.setFocus()
    app.processEvents()
    assert QApplication.focusWidget() is w._run_select

    # Choose a different run via keyboard; focus should remain on the combo.
    QTest.keyClick(w._run_select, Qt.Key_Space)
    app.processEvents()
    QTest.keyClick(w._run_select, Qt.Key_Down)
    app.processEvents()
    QTest.keyClick(w._run_select, Qt.Key_Return)
    app.processEvents()

    assert QApplication.focusWidget() is w._run_select

    w.close()
    app.processEvents()


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

    from PySide6.QtCore import QObject, Qt, Signal
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

    # Simulate the "run started from Run button" condition.
    w._restore_focus_to_run_btn = True

    # Simulate run completion toggling running=False.
    w._set_running(False)
    app.processEvents()

    assert w._restore_focus_to_run_btn is False
    assert QApplication.focusWidget() is w._run_btn

    w.close()
    app.processEvents()


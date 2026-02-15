from __future__ import annotations


def test_switch_to_compose_no_prompt_when_no_outputs() -> None:
    """Cover the early-return prompt gates in dock switching."""

    from PySide6.QtWidgets import QApplication

    from latencylab_ui.main_window_dock_switching import toggle_or_switch_to_model_composer
    from latencylab_ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    _ = app

    from PySide6.QtCore import QObject, Signal

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

    # No outputs => no prompt.
    w._have_unexported_outputs = False
    w._last_outputs = None
    toggle_or_switch_to_model_composer(w)
    app.processEvents()
    assert w._model_composer_dock.isVisible() is True

    w.close()
    app.processEvents()


def test_prompt_export_returns_when_no_last_outputs() -> None:
    """Cover `_prompt_export_if_needed()` early-return when `_last_outputs` is None."""

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.main_window_dock_switching import _prompt_export_if_needed

    app = QApplication.instance() or QApplication([])
    _ = app

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

    w._have_unexported_outputs = True
    w._last_outputs = None
    _prompt_export_if_needed(w)

    w.close()
    app.processEvents()


def test_switch_to_compose_prompt_yes_export_cancel_blocks_switch(monkeypatch) -> None:
    """Cover the prompt Yes path and the 'export cancelled/failed' gate."""

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.main_window_dock_switching import toggle_or_switch_to_model_composer

    app = QApplication.instance() or QApplication([])
    _ = app

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

    w._have_unexported_outputs = True
    w._last_outputs = object()  # type: ignore[assignment]
    w._model_composer_dock.hide()
    assert w._model_composer_dock.isVisible() is False

    # User chooses Yes -> triggers export attempt.
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)

    # Simulate export cancelled/failed by leaving the flag True.
    monkeypatch.setattr(w, "_on_save_log_clicked", lambda: None)
    toggle_or_switch_to_model_composer(w)
    app.processEvents()
    assert w._model_composer_dock.isVisible() is False

    w.close()
    app.processEvents()


def test_prompt_export_no_path_does_not_raise(monkeypatch) -> None:
    """Cover the QMessageBox.question call line and the No path."""

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.main_window_dock_switching import _prompt_export_if_needed

    app = QApplication.instance() or QApplication([])
    _ = app

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

    w._have_unexported_outputs = True
    w._last_outputs = object()  # type: ignore[assignment]

    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)
    _prompt_export_if_needed(w)

    w.close()
    app.processEvents()


def test_switch_to_compose_prompt_cancel_blocks_switch(monkeypatch) -> None:
    """Cover the prompt Cancel path."""

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication, QMessageBox

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.main_window_dock_switching import toggle_or_switch_to_model_composer

    app = QApplication.instance() or QApplication([])
    _ = app

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

    w._have_unexported_outputs = True
    w._last_outputs = object()  # type: ignore[assignment]
    w._model_composer_dock.hide()

    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Cancel)
    toggle_or_switch_to_model_composer(w)
    app.processEvents()
    assert w._model_composer_dock.isVisible() is False

    w.close()
    app.processEvents()


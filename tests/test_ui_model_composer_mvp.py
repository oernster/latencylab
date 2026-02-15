from __future__ import annotations

import json
from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_compose_button_exists_and_toggles_dock_visibility() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QPushButton

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
    app.processEvents()

    btn = w.findChild(QPushButton, "compose_model_btn")
    assert btn is not None
    assert btn.text() == "Compose Model"
    assert w._model_composer_dock.isVisible() is False

    btn.click()
    app.processEvents()
    assert w._model_composer_dock.isVisible() is True

    btn.click()
    app.processEvents()
    assert w._model_composer_dock.isVisible() is False

    w.close()
    app.processEvents()


def test_export_and_export_load_use_deterministic_json(tmp_path: Path, monkeypatch) -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QFileDialog

    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.model_composer_types import build_raw_model_dict, dumps_deterministic

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

    dock = w._model_composer_dock
    dock._system.model_name_edit.setText("m")  # noqa: SLF001
    dock._system.version_combo.setCurrentText("1")  # noqa: SLF001
    dock._system.entry_event_edit.setText("e0")  # noqa: SLF001
    app.processEvents()

    out = tmp_path / "m.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))

    # Export.
    dock._on_export_clicked(load_after=False)  # noqa: SLF001
    txt = out.read_text(encoding="utf-8")
    loaded = json.loads(txt)
    expected = build_raw_model_dict(dock._state)  # noqa: SLF001
    assert loaded == expected
    assert txt == dumps_deterministic(expected)

    # Export + load should call the existing load hook.
    seen: dict[str, str] = {}

    def _spy_load(p: Path) -> None:
        seen["p"] = str(p)

    monkeypatch.setattr(w, "_load_model", _spy_load)
    dock._on_export_clicked(load_after=True)  # noqa: SLF001
    assert seen["p"] == str(out)

    w.close()
    app.processEvents()


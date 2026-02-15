from __future__ import annotations

from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_composer_dock_remaining_branches(tmp_path: Path, monkeypatch) -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

    from latencylab.model import Model
    from latencylab_ui.model_composer_dock import ModelComposerDock

    import latencylab_ui.model_composer_dock as _dock_mod

    # Never allow modal dialogs to hang tests.
    monkeypatch.setattr(QMessageBox, "critical", lambda *_a, **_k: None)

    host = QWidget()
    dock = ModelComposerDock(host)
    dock.show()
    app.processEvents()

    # Ensure wiring editor has a derived event list (otherwise combo stays empty).
    dock._state.entry_event = "e0"  # noqa: SLF001
    dock._state.tasks = {"t": {"context": "ui", "duration_ms": {"dist": "fixed", "value": 1.0}, "emit": []}}  # noqa: SLF001
    dock._state.wiring = {"e0": []}  # noqa: SLF001
    monkeypatch.setattr(dock, "_sync_from_ui", lambda: dock._refresh_wiring_events())

    # Validate click path: True and False.
    monkeypatch.setattr(dock, "_validate_now", lambda **_k: True)
    dock._on_validate_clicked()  # noqa: SLF001
    assert dock._valid_label.text() == "Valid"  # noqa: SLF001

    monkeypatch.setattr(dock, "_validate_now", lambda **_k: False)
    dock._on_validate_clicked()  # noqa: SLF001
    assert dock._valid_label.text() == "Invalid"  # noqa: SLF001

    # Restore real `_validate_now` implementation for subsequent branch tests.
    dock._validate_now = _dock_mod.ModelComposerDock._validate_now.__get__(dock, ModelComposerDock)  # type: ignore[method-assign]

    # _default_export_dir exception branch (attribute access raises).
    class _BadHost(QWidget):
        def __getattribute__(self, name: str):
            if name == "_loaded_model":
                raise RuntimeError("boom")
            return super().__getattribute__(name)

    bad = _BadHost()
    dock2 = ModelComposerDock(bad)
    assert dock2._default_export_dir().name  # noqa: SLF001

    # _prompt_save_path cancel branch.
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: ("", ""))
    assert dock._prompt_save_path(default_filename="x.json") is None  # noqa: SLF001

    # _on_export_clicked: prompt returns None.
    monkeypatch.setattr(dock, "_validate_now", lambda **_k: True)
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: None)
    dock._on_export_clicked(load_after=False)  # noqa: SLF001

    # Restore real `_validate_now` implementation for subsequent branch tests.
    dock._validate_now = _dock_mod.ModelComposerDock._validate_now.__get__(dock, ModelComposerDock)  # type: ignore[method-assign]

    # Stress generation failure branch.
    monkeypatch.setattr(
        _dock_mod,
        "build_stress_variant_state",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("no")),
    )
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Stress cancel branch.
    monkeypatch.setattr(_dock_mod, "build_stress_variant_state", _dock_mod.build_stress_variant_state)
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: None)
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Stress write failure branch.
    out = tmp_path / "s.json"
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: out)
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")),
    )
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Ensure we call the real method (not a monkeypatched lambda).
    dock._validate_now = _dock_mod.ModelComposerDock._validate_now.__get__(dock, ModelComposerDock)  # type: ignore[method-assign]

    # Validate show_dialog=True error branches.
    monkeypatch.setattr(dock, "_sync_from_ui", lambda: None)
    monkeypatch.setattr(
        _dock_mod,
        "build_raw_model_dict",
        lambda *_a, **_k: (_ for _ in ()).throw(TypeError("x")),
    )
    assert dock._validate_now(show_dialog=True) is False  # noqa: SLF001

    monkeypatch.setattr(
        _dock_mod,
        "build_raw_model_dict",
        lambda *_a, **_k: {
            "schema_version": 2,
            "entry_event": "e0",
            "contexts": {},
            "events": {"e0": {"tags": ["entry"]}},
            "tasks": {},
        },
    )
    monkeypatch.setattr(
        Model,
        "from_json",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert dock._validate_now(show_dialog=True) is False  # noqa: SLF001

    dock.close()
    dock2.close()
    app.processEvents()


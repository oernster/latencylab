from __future__ import annotations

from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_composer_dock_export_and_stress_branches(tmp_path: Path, monkeypatch) -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMessageBox, QWidget

    from latencylab_ui.model_composer_dock import ModelComposerDock

    # Prevent modal dialogs from blocking/hanging.
    monkeypatch.setattr(QMessageBox, "critical", lambda *_a, **_k: None)

    seen: dict[str, str] = {}

    def _spy_load(p: Path) -> None:
        seen["p"] = str(p)

    host = QWidget()
    host._load_model = _spy_load  # type: ignore[attr-defined]

    dock = ModelComposerDock(host)
    dock.show()

    # Keep state stable and bypass validate gate.
    dock._state.model_name = "m"  # noqa: SLF001
    dock._state.entry_event = "e0"  # noqa: SLF001
    dock._state.contexts = {"ui": {"concurrency": 1, "policy": "fifo"}}  # noqa: SLF001
    monkeypatch.setattr(dock, "_sync_from_ui", lambda: None)
    monkeypatch.setattr(dock, "_validate_now", lambda **_k: True)
    # Ensure derived wiring events refresh doesn't interfere with this focused test.
    monkeypatch.setattr(dock, "_refresh_wiring_events", lambda: None)

    # Stress early-return branch when save dialog is cancelled (covers dock.py:280).
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: None)
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Export JSON: write failure branch (covers dock.py:256-258).
    out = tmp_path / "m.json"
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: out)
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")),
    )
    dock._on_export_clicked(load_after=False)  # noqa: SLF001

    # Stress variant: full success path (covers dock.py:271 and 276-287).
    # Restore write_text.
    monkeypatch.setattr(Path, "write_text", lambda self, txt, **_k: Path(self).write_bytes(txt.encode("utf-8")))

    stress_out = tmp_path / "m_STRESS.json"
    monkeypatch.setattr(dock, "_prompt_save_path", lambda **_k: stress_out)
    dock._on_export_stress_clicked()  # noqa: SLF001

    assert seen["p"] == str(stress_out)
    assert stress_out.exists()

    # Stress write failure branch (covers dock.py:283-285).
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")),
    )
    dock._on_export_stress_clicked()  # noqa: SLF001

    dock.close()


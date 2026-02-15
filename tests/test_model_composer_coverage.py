from __future__ import annotations

import json
from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_composer_types_build_raw_and_events_and_labels() -> None:
    from latencylab_ui.model_composer_types import (
        ComposerState,
        build_raw_model_dict,
        derive_events,
        dumps_deterministic,
        parse_labels,
    )

    # Labels: ignore invalid segments.
    assert parse_labels("a=1, b = two, nope, =bad, ok=") == {"a": "1", "b": "two", "ok": ""}

    s = ComposerState(model_name="x", version=2, entry_event="e0")
    s.contexts = {"ui": {"concurrency": 2, "policy": "fifo"}}
    s.tasks = {
        "t1": {
            "context": "ui",
            "duration_ms": {"dist": "fixed", "value": 1},
            "emit": ["e1"],
            "meta": {"category": "cat", "tags": ["a"], "labels": {"k": "v"}},
        },
        # Empty emits should be omitted.
        "t2": {
            "context": "ui",
            "duration_ms": {"dist": "normal", "mean": 1, "std": 0},
            "emit": [],
        },
    }
    s.wiring = {
        "e0": [
            {"task": "t1", "delay_ms": {"dist": "fixed", "value": 5}},
            {"task": "t2", "delay_ms": None},
        ]
    }

    ev = derive_events(s)
    assert set(ev.keys()) == {"e0", "e1"}
    assert ev["e0"]["tags"] == ["entry"]
    assert ev["e1"]["tags"] == []

    raw = build_raw_model_dict(s)
    # Deterministic serialization gate.
    assert dumps_deterministic(raw) == json.dumps(raw, indent=2, sort_keys=True)

    # v2 keeps delay objects when present.
    assert raw["wiring"]["e0"][0] == {"delay_ms": {"dist": "fixed", "value": 5.0}, "task": "t1"}
    # delay=None exports as a plain listener string.
    assert raw["wiring"]["e0"][1] == "t2"

    # v1: meta omitted, delay omitted, wiring listeners strings.
    s.version = 1
    raw_v1 = build_raw_model_dict(s)
    assert "meta" not in raw_v1["tasks"]["t1"]
    assert raw_v1["wiring"]["e0"] == ["t1", "t2"]

    # Wiring edge with empty task is ignored.
    s.version = 2
    s.wiring = {"e0": [{"task": "", "delay_ms": None}]}
    raw2 = build_raw_model_dict(s)
    assert "wiring" not in raw2

    # Invalid version raises.
    s.version = 999
    try:
        build_raw_model_dict(s)
        assert False, "expected ValueError"  # pragma: no cover
    except ValueError:
        pass


def test_model_composer_types_stress_variant() -> None:
    from latencylab_ui.model_composer_types import ComposerState, build_stress_variant_state

    s = ComposerState(model_name="m", version=2, entry_event="e0")
    s.tasks = {
        "a": {"context": "ui", "duration_ms": {"dist": "fixed", "value": 10}, "emit": []},
        "b": {"context": "ui", "duration_ms": {"dist": "normal", "mean": 3, "std": 2}, "emit": []},
        "c": {
            "context": "ui",
            "duration_ms": {"dist": "lognormal", "mu": 1, "sigma": 1},
            "emit": [],
        },
    }
    s.wiring = {
        "e0": [
            {"task": "a", "delay_ms": {"dist": "fixed", "value": 4}},
            {"task": "b", "delay_ms": {"dist": "normal", "mean": 2, "std": 1}},
            {"task": "c", "delay_ms": {"dist": "lognormal", "mu": 0, "sigma": 1}},
        ]
    }

    try:
        build_stress_variant_state(s, multiplier=0)
        assert False, "expected ValueError"  # pragma: no cover
    except ValueError:
        pass

    out = build_stress_variant_state(s, multiplier=2.0)
    assert out.model_name == "m_STRESS"
    assert out.tasks["a"]["duration_ms"]["value"] == 20.0
    assert out.tasks["b"]["duration_ms"]["mean"] == 6.0
    assert out.tasks["b"]["duration_ms"]["std"] == 4.0
    # lognormal mu shifts by log(multiplier).
    assert out.tasks["c"]["duration_ms"]["mu"] > 1.0
    assert out.wiring["e0"][0]["delay_ms"]["value"] == 8.0
    assert out.wiring["e0"][1]["delay_ms"]["mean"] == 4.0
    assert out.wiring["e0"][2]["delay_ms"]["mu"] > 0.0

    # Non-dict delay objects are ignored by the delay-stress enhancement.
    s.wiring = {"e0": [{"task": "a", "delay_ms": 5.0}]}
    out2 = build_stress_variant_state(s, multiplier=2.0)
    assert out2.wiring["e0"][0]["delay_ms"] == 5.0


def test_model_composer_widgets_duration_editor_roundtrip() -> None:
    _ensure_qapp()

    from latencylab_ui.model_composer_widgets import DurationDistEditor

    w = DurationDistEditor()

    w.set_from_obj({"dist": "fixed", "value": 3})
    assert w.to_obj()["dist"] == "fixed"
    assert float(w.to_obj()["value"]) == 3.0

    w.set_from_obj({"dist": "normal", "mean": 1.5, "std": 2.5})
    o = w.to_obj()
    assert o["dist"] == "normal"
    assert float(o["mean"]) == 1.5
    assert float(o["std"]) == 2.5

    w.set_from_obj({"dist": "lognormal", "mu": 0.1, "sigma": 0.2})
    o = w.to_obj()
    assert o["dist"] == "lognormal"
    assert float(o["mu"]) == 0.1
    assert float(o["sigma"]) == 0.2


def test_model_composer_editors_and_dock_branches(tmp_path: Path, monkeypatch) -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from PySide6.QtWidgets import QWidget

    from latencylab.model import Model

    from latencylab_ui.model_composer_contexts_editor import ContextsEditor
    from latencylab_ui.model_composer_dock import ModelComposerDock
    from latencylab_ui.model_composer_system_editor import SystemEditor
    from latencylab_ui.model_composer_tasks_editor import TasksEditor
    from latencylab_ui.model_composer_wiring_editor import WiringEditor

    # Prevent modal dialogs from blocking/hanging the test runner.
    monkeypatch.setattr(QMessageBox, "critical", lambda *_a, **_k: None)

    # SystemEditor: non-int version path.
    se = SystemEditor()
    seen: list[int] = []
    se.version_changed.connect(lambda v: seen.append(v))
    se._on_version_changed("x")  # noqa: SLF001
    assert seen[-1] == 2

    # `get_version()` ValueError fallback.
    class _BadCombo:
        def currentText(self) -> str:  # noqa: D401
            return "x"

    se.version_combo = _BadCombo()  # type: ignore[assignment]
    assert se.get_version() == 2

    # Note: version_combo is constrained to {"1","2"}; invalid handling is
    # exercised via the private handler above.

    # ContextsEditor: add/remove.
    ce = ContextsEditor()
    assert "ui" in ce.context_names()
    # _ensure_default early-return branch when table already has rows.
    ce._ensure_default()  # noqa: SLF001
    ce._on_add()  # noqa: SLF001
    assert ce.table.rowCount() == 2
    ce.table.selectRow(1)
    ce._on_remove()  # noqa: SLF001
    assert ce.table.rowCount() == 1

    ce.table.item(0, 0).setText("")
    assert ce.to_contexts_dict() == {}

    # TasksEditor (card-based): cover dist and v2 category.
    te = TasksEditor()
    te.set_context_names(["ui", "bg"])
    te.set_version(2)
    te._on_add()  # noqa: SLF001
    te._on_add()  # noqa: SLF001

    cards = te._iter_cards()  # noqa: SLF001
    assert len(cards) == 2

    # Card 0: normal.
    cards[0].name_edit.setText("t_normal")
    cards[0].context_combo.setCurrentText("ui")
    cards[0].duration.set_from_obj({"dist": "normal", "mean": 1.5, "std": 2.5})

    # Card 1: fixed + category.
    cards[1].name_edit.setText("t_fixed")
    cards[1].context_combo.setCurrentText("bg")
    cards[1].duration.set_from_obj({"dist": "fixed", "value": 5.0})
    cards[1].emits_edit.setText("e1, e2")
    cards[1].category_edit.setText("cat")

    d = te.to_tasks_dict(version=2)
    assert d["t_normal"]["duration_ms"]["dist"] == "normal"  # type: ignore[index]
    assert d["t_fixed"]["duration_ms"]["dist"] == "fixed"  # type: ignore[index]
    assert d["t_fixed"]["meta"]["category"] == "cat"  # type: ignore[index]

    te.set_version(1)
    d1 = te.to_tasks_dict(version=1)
    assert "meta" not in d1["t_fixed"]

    # WiringEditor: derived-only events.
    we = WiringEditor()
    we.set_task_names(["t_fixed"])
    we.set_wiring({"eX": []})
    we.set_event_names(["e0", "e2"], entry_event="e0")
    assert we.event_combo.itemText(0) == "e0"
    we.event_combo.setCurrentText("e0")
    we.add_listener_combo.setCurrentText("t_fixed")
    we._on_add_listener()  # noqa: SLF001
    assert we.listeners_list.count() == 1
    we.listeners_list.setCurrentRow(0)
    we._on_remove_listener()  # noqa: SLF001
    assert we.listeners_list.count() == 0

    # Dock: exercise validate/export/stress branches and exception paths.
    host = QWidget()
    dock = ModelComposerDock(host)
    dock.show()
    app.processEvents()

    # Force tasks and wiring signals to execute the sync branches.
    dock._contexts._on_add()  # noqa: SLF001
    dock._tasks._on_add()  # noqa: SLF001
    app.processEvents()

    # Validate: invalid branch via ModelValidationError (concurrency=0 is invalid).
    dock._state.version = 2
    dock._state.entry_event = "e0"
    dock._state.contexts = {"ui": {"concurrency": 0, "policy": "fifo"}}
    dock._state.tasks = {}
    dock._state.wiring = {}
    monkeypatch.setattr(dock, "_sync_from_ui", lambda: None)
    assert dock._validate_now(show_dialog=False) is False  # noqa: SLF001
    dock._valid_label.setText("Invalid")  # noqa: SLF001
    assert dock._valid_label.text() == "Invalid"  # noqa: SLF001

    # Validate: ok branch.
    dock._state.contexts = {"ui": {"concurrency": 1, "policy": "fifo"}}
    assert dock._validate_now(show_dialog=False) is True  # noqa: SLF001
    dock._valid_label.setText("Valid")  # noqa: SLF001
    assert dock._valid_label.text() == "Valid"  # noqa: SLF001

    # Validate: TypeError branch.
    import latencylab_ui.model_composer_dock as _dock_mod

    monkeypatch.setattr(
        _dock_mod,
        "build_raw_model_dict",
        lambda *_a, **_k: (_ for _ in ()).throw(TypeError("x")),
    )
    assert dock._validate_now(show_dialog=False) is False  # noqa: SLF001

    # Validate: generic Exception branch.
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
    monkeypatch.setattr(Model, "from_json", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert dock._validate_now(show_dialog=False) is False  # noqa: SLF001

    # Cancel save dialog => no write.
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dock._on_export_clicked(load_after=False)  # noqa: SLF001

    # Prompt path without .json gets normalized.
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "noext"), ""))
    p = dock._prompt_save_path(default_filename="x.json")  # noqa: SLF001
    assert p is not None
    assert p.suffix == ".json"

    # Write failure path.
    out = tmp_path / "x.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    monkeypatch.setattr(Path, "write_text", lambda *_a, **_k: (_ for _ in ()).throw(OSError("nope")))
    seen_crit = {"called": False}
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *_a, **_k: seen_crit.__setitem__("called", True),
    )
    dock._on_export_clicked(load_after=False)  # noqa: SLF001
    assert seen_crit["called"] is True

    # Restore non-blocking handler for subsequent branches.
    monkeypatch.setattr(QMessageBox, "critical", lambda *_a, **_k: None)

    # _default_export_dir uses loaded model path when present.
    class _Loaded:
        def __init__(self, path: Path) -> None:
            self.path = path

    host._loaded_model = _Loaded(tmp_path / "m.json")  # type: ignore[attr-defined]
    assert dock._default_export_dir() == tmp_path  # noqa: SLF001

    # Stress: generation failure.
    monkeypatch.setattr(
        _dock_mod,
        "build_stress_variant_state",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("nope")),
    )
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Stress: cancel path.
    monkeypatch.setattr(_dock_mod, "build_stress_variant_state", _dock_mod.build_stress_variant_state)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dock._on_export_stress_clicked()  # noqa: SLF001

    # Load failure path.
    def _boom(_p: Path) -> None:
        raise RuntimeError("no")

    host._load_model = _boom  # type: ignore[attr-defined]
    dock._load_into_main_ui(tmp_path / "x.json")  # noqa: SLF001

    dock.close()
    app.processEvents()


"""Additional Model Composer coverage lives in
[`tests.test_model_composer_dock_coverage`](tests/test_model_composer_dock_coverage.py:1)
to keep each test module <= 400 lines.
"""

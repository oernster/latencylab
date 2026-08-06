from __future__ import annotations

import json


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# Type building and the duration editor. The editor and dock branches are
# in test_model_composer_editors_and_dock.py.


def test_model_composer_types_build_raw_and_events_and_labels() -> None:
    from latencylab_ui.model_composer_types import (
        ComposerState,
        build_raw_model_dict,
        derive_events,
        dumps_deterministic,
        parse_labels,
    )

    # Labels: ignore invalid segments.
    assert parse_labels("a=1, b = two, nope, =bad, ok=") == {
        "a": "1",
        "b": "two",
        "ok": "",
    }

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
    assert raw["wiring"]["e0"][0] == {
        "delay_ms": {"dist": "fixed", "value": 5.0},
        "task": "t1",
    }
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
    from latencylab_ui.model_composer_types import (
        ComposerState,
        build_stress_variant_state,
    )

    s = ComposerState(model_name="m", version=2, entry_event="e0")
    s.tasks = {
        "a": {
            "context": "ui",
            "duration_ms": {"dist": "fixed", "value": 10},
            "emit": [],
        },
        "b": {
            "context": "ui",
            "duration_ms": {"dist": "normal", "mean": 3, "std": 2},
            "emit": [],
        },
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

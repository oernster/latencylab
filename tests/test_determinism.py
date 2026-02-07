from __future__ import annotations

import json
from pathlib import Path

from latencylab.model import Model
from latencylab.sim import simulate_many
from latencylab.validate import validate_model


def test_simulation_is_deterministic_for_seed(tmp_path: Path) -> None:
    model_path = Path("examples/interactive.json")
    model = Model.from_json(json.loads(model_path.read_text(encoding="utf-8")))
    validate_model(model)

    runs1, _ = simulate_many(
        model=model, runs=100, seed=123, max_tasks_per_run=10000, want_trace=False
    )
    runs2, _ = simulate_many(
        model=model, runs=100, seed=123, max_tasks_per_run=10000, want_trace=False
    )

    assert [
        (r.first_ui_event_time_ms, r.last_ui_event_time_ms, r.makespan_ms)
        for r in runs1
    ] == [
        (r.first_ui_event_time_ms, r.last_ui_event_time_ms, r.makespan_ms)
        for r in runs2
    ]


def test_v1_outputs_are_stable_golden_snapshot() -> None:
    model_path = Path("examples/interactive.json")
    model = Model.from_json(json.loads(model_path.read_text(encoding="utf-8")))
    validate_model(model)

    runs, _ = simulate_many(
        model=model, runs=5, seed=123, max_tasks_per_run=10000, want_trace=False
    )
    got = [
        (
            r.first_ui_event_time_ms,
            r.last_ui_event_time_ms,
            r.makespan_ms,
            r.critical_path_tasks,
        )
        for r in runs
    ]
    assert got == [
        (0.0, 31.32588509562687, 36.34342169205515, "handle_input>do_fetch>render"),
        (0.0, 16.347179889224478, 21.618934406279667, "handle_input>do_fetch>render"),
        (0.0, 61.274544591597476, 64.32323189058981, "handle_input>do_fetch>render"),
        (0.0, 46.9830963049912, 51.32834222417827, "handle_input>do_fetch>render"),
        (0.0, 15.463068682955369, 19.78655440422449, "handle_input>do_fetch>render"),
    ]

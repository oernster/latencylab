from __future__ import annotations

import json
from pathlib import Path

import numpy as np

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

    assert [(r.first_ui_event_time_ms, r.last_ui_event_time_ms, r.makespan_ms) for r in runs1] == [
        (r.first_ui_event_time_ms, r.last_ui_event_time_ms, r.makespan_ms) for r in runs2
    ]


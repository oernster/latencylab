from __future__ import annotations

from latencylab.model import Model
from latencylab.sim import simulate_many
from latencylab.validate import validate_model


def test_v2_delay_creates_synthetic_delay_nodes_in_trace_and_critical_path() -> None:
    model = Model.from_json(
        {
            "version": 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1, "policy": "fifo"}},
            "events": {"e0": {"tags": ["ui"]}, "e1": {"tags": []}},
            "tasks": {
                "t0": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 1.0},
                    "emit": ["e1"],
                    "meta": {"category": "input", "tags": ["hot"]},
                },
                "t1": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 2.0},
                    "emit": [],
                },
            },
            "wiring": {
                "e0": [{"task": "t0"}],
                "e1": [{"task": "t1", "delay_ms": {"dist": "fixed", "value": 5.0}}],
            },
        }
    )
    validate_model(model)

    runs, trace = simulate_many(
        model=model, runs=1, seed=1, max_tasks_per_run=1000, want_trace=True
    )
    assert runs[0].critical_path_tasks == "t0>delay(e1->t1)>t1"

    names = [t.task_name for t in trace]
    assert "delay(e1->t1)" in names

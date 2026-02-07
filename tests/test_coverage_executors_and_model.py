from __future__ import annotations

import pytest

from latencylab.executors import default_executor_for_model
from latencylab.model import ContextDef, EventDef, Model


def _minimal_model(*, version: int) -> Model:
    return Model(
        version=version,
        entry_event="e0",
        contexts={"ui": ContextDef(concurrency=1)},
        events={"e0": EventDef(tags=("ui",))},
        tasks={},
        wiring={},
        wiring_edges={},
    )


def test_runexecutor_protocol_method_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        # Call the Protocol's placeholder implementation to cover it.
        from latencylab.executors import RunExecutor

        RunExecutor.execute(  # type: ignore[misc]
            object(),  # type: ignore[arg-type]
            model=_minimal_model(version=2),
            runs=1,
            seed=1,
            max_tasks_per_run=1,
            want_trace=False,
        )


def test_default_executor_rejects_unknown_model_version() -> None:
    with pytest.raises(ValueError, match="Unsupported model version"):
        default_executor_for_model(_minimal_model(version=999))


def test_model_parses_numeric_delay_dist_and_rejects_bad_types() -> None:
    # Covers numeric delay shorthand and parse-time type errors in wiring.
    m = Model.from_json(
        {
            "schema_version": 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 1.0},
                    "emit": [],
                }
            },
            "wiring": {"e0": [{"task": "t", "delay_ms": 5}]},
        }
    )
    assert m.wiring_edges["e0"][0].delay_ms is not None
    assert m.wiring_edges["e0"][0].delay_ms.dist == "fixed"

    with pytest.raises(TypeError, match="delay_ms must be a number or a dist object"):
        Model.from_json(
            {
                "schema_version": 2,
                "entry_event": "e0",
                "contexts": {"ui": {"concurrency": 1}},
                "events": {"e0": {"tags": ["ui"]}},
                "tasks": {
                    "t": {
                        "context": "ui",
                        "duration_ms": {"dist": "fixed", "value": 1.0},
                        "emit": [],
                    }
                },
                "wiring": {"e0": [{"task": "t", "delay_ms": "nope"}]},
            }
        )

    with pytest.raises(TypeError, match="wiring listeners must be strings or objects"):
        Model.from_json(
            {
                "schema_version": 2,
                "entry_event": "e0",
                "contexts": {"ui": {"concurrency": 1}},
                "events": {"e0": {"tags": ["ui"]}},
                "tasks": {
                    "t": {
                        "context": "ui",
                        "duration_ms": {"dist": "fixed", "value": 1.0},
                        "emit": [],
                    }
                },
                "wiring": {"e0": [123]},
            }
        )


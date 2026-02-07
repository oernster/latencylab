from __future__ import annotations


from latencylab.executors import LegacyNumpyExecutor, StdlibV2Executor
from latencylab.model import Model


def _oracle_model_json(*, schema_version: int) -> dict:
    """Model representable in both v1 and v2.

    - fixed durations -> deterministic schedule, no RNG dependency
    - no delay edges -> v2 should not introduce synthetic delay tasks
    - ui-tagged events -> exercises first/last UI time computation
    """

    return {
        "schema_version": schema_version,
        "entry_event": "e0",
        "contexts": {"ui": {"concurrency": 1}},
        "events": {
            "e0": {"tags": ["ui"]},
            "e1": {"tags": []},
            "ui.done": {"tags": ["ui"]},
        },
        "tasks": {
            "t0": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 1.0},
                "emit": ["e1"],
            },
            "t1": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 2.0},
                "emit": ["ui.done"],
            },
        },
        "wiring": {
            "e0": ["t0"],
            "e1": ["t1"],
        },
    }


def test_legacy_v1_is_frozen_oracle_and_v2_matches_for_simple_model() -> None:
    # Execute v1 via its executor directly (oracle baseline).
    m1 = Model.from_json(_oracle_model_json(schema_version=1))
    v1_runs, v1_trace = LegacyNumpyExecutor().execute(
        model=m1,
        runs=1,
        seed=123,
        max_tasks_per_run=10,
        want_trace=True,
    )

    # Execute v2 via its executor directly (migration target).
    m2 = Model.from_json(_oracle_model_json(schema_version=2))
    v2_runs, v2_trace = StdlibV2Executor().execute(
        model=m2,
        runs=1,
        seed=123,
        max_tasks_per_run=10,
        want_trace=True,
    )

    assert len(v1_runs) == len(v2_runs) == 1
    r1 = v1_runs[0]
    r2 = v2_runs[0]

    # Key output fields should match exactly for fixed-duration, no-delay models.
    assert r1.failed == r2.failed
    assert r1.failure_reason == r2.failure_reason
    assert r1.makespan_ms == r2.makespan_ms
    assert r1.first_ui_event_time_ms == r2.first_ui_event_time_ms
    assert r1.last_ui_event_time_ms == r2.last_ui_event_time_ms
    assert r1.critical_path_tasks == r2.critical_path_tasks

    # In v2, synthetic delay nodes must not appear unless delay_ms is specified.
    assert all(
        not inst.task_name.startswith("delay(") for inst in v2_trace
    ), "Unexpected synthetic delay instances in v2 trace for no-delay model"

    # v1 trace should also not include any delay(...) tasks.
    assert all(
        not inst.task_name.startswith("delay(") for inst in v1_trace
    ), "Unexpected synthetic delay instances in v1 trace"


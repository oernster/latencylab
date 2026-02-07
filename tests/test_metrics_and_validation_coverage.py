from __future__ import annotations

import math

import pytest

from latencylab.metrics import add_task_metadata, aggregate_runs
from latencylab.model import Model
from latencylab.types import RunResult
from latencylab.validate import ModelValidationError, validate_model


def _base_model(*, version_key: str = "schema_version", version: int = 2) -> dict:
    return {
        version_key: version,
        "entry_event": "e0",
        "contexts": {"ui": {"concurrency": 1}},
        "events": {"e0": {"tags": ["ui"]}, "e1": {"tags": []}},
        "tasks": {
            "t": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 1.0},
                "emit": ["e1"],
                "meta": {
                    "category": "input",
                    "tags": ["hot"],
                    "labels": {"team": "ui"},
                },
            }
        },
        "wiring": {"e0": ["t"]},
    }


def test_metrics_percentiles_empty_values_are_nan() -> None:
    model = Model.from_json(_base_model())
    # All failed => ok=[] and makespans=[]; percentiles should be NaN
    runs = [
        RunResult(
            run_id=0,
            first_ui_event_time_ms=None,
            last_ui_event_time_ms=None,
            makespan_ms=0.0,
            critical_path_ms=0.0,
            critical_path_tasks="",
            failed=True,
            failure_reason="boom",
        )
    ]
    summary = aggregate_runs(model=model, runs=runs)
    assert math.isnan(summary["latency_ms"]["first_ui"]["p50"])
    assert math.isnan(summary["latency_ms"]["last_ui"]["p99"])
    assert math.isnan(summary["latency_ms"]["makespan"]["p90"])


def test_metrics_percentile_edges_p0_p100_and_singleton() -> None:
    from latencylab.metrics import _percentile_sorted

    assert math.isnan(_percentile_sorted([], 50))
    vals = [1.0, 2.0, 3.0]
    assert _percentile_sorted(vals, 0) == 1.0
    assert _percentile_sorted(vals, 100) == 3.0
    assert _percentile_sorted([5.0], 50) == 5.0


def test_add_task_metadata_v2_adds_and_v1_does_not() -> None:
    m2 = Model.from_json(_base_model())
    s = aggregate_runs(
        model=m2,
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=0.0,
                last_ui_event_time_ms=1.0,
                makespan_ms=1.0,
                critical_path_ms=1.0,
                critical_path_tasks="t",
                failed=False,
                failure_reason=None,
            )
        ],
    )
    s2 = add_task_metadata(s, model=m2)
    assert "task_metadata" in s2
    assert s2["task_metadata"]["t"]["labels"]["team"] == "ui"

    m1 = Model.from_json(_base_model(version=1, version_key="version"))
    s1 = add_task_metadata(s, model=m1)
    assert "task_metadata" not in s1


def test_validation_error_branches() -> None:
    # Unsupported version
    m = Model.from_json(_base_model(version=999, version_key="version"))
    with pytest.raises(ModelValidationError, match="Unsupported model version"):
        validate_model(m)

    # Missing entry event
    bad = _base_model()
    bad["entry_event"] = "missing"
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="entry_event"):
        validate_model(m)

    # Bad context concurrency
    bad = _base_model()
    bad["contexts"]["ui"]["concurrency"] = 0
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="concurrency"):
        validate_model(m)

    # Bad policy
    bad = _base_model()
    bad["contexts"]["ui"]["policy"] = "lifo"
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="policy"):
        validate_model(m)

    # Unknown task context
    bad = _base_model()
    bad["tasks"]["t"]["context"] = "missing"
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="unknown context"):
        validate_model(m)

    # fixed dist missing value
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "fixed"}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="fixed dist requires 'value'"):
        validate_model(m)

    # fixed negative
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "fixed", "value": -1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="fixed value"):
        validate_model(m)

    # normal missing std
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "normal", "mean": 1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal dist requires 'std'"):
        validate_model(m)

    # normal negative std
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "normal", "mean": 1, "std": -1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal std"):
        validate_model(m)

    # normal negative min
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {
        "dist": "normal",
        "mean": 1,
        "std": 1,
        "min": -1,
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal min"):
        validate_model(m)

    # lognormal missing sigma
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "lognormal", "mu": 1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="lognormal dist requires 'sigma'"):
        validate_model(m)

    # lognormal negative sigma
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "lognormal", "mu": 1, "sigma": -1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="lognormal sigma"):
        validate_model(m)

    # unsupported dist
    bad = _base_model()
    bad["tasks"]["t"]["duration_ms"] = {"dist": "weird", "value": 1}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="unsupported dist"):
        validate_model(m)

    # emits unknown event
    bad = _base_model()
    bad["tasks"]["t"]["emit"] = ["missing"]
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="emits unknown event"):
        validate_model(m)

    # wiring unknown event
    bad = _base_model()
    bad["wiring"] = {"missing": ["t"]}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="wiring references unknown event"):
        validate_model(m)

    # wiring unknown task
    bad = _base_model()
    bad["wiring"] = {"e0": ["missing_task"]}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="references unknown task"):
        validate_model(m)

    # wiring delay dist invalid
    bad = _base_model()
    bad["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "fixed", "value": -1}}]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="fixed value must be >= 0"):
        validate_model(m)

    # wiring delay fixed missing value
    bad = _base_model()
    bad["wiring"] = {"e0": [{"task": "t", "delay_ms": {"dist": "fixed"}}]}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="fixed dist requires 'value'"):
        validate_model(m)

    # wiring delay normal missing std
    bad = _base_model()
    bad["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "normal", "mean": 1.0}}]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal dist requires 'std'"):
        validate_model(m)

    # wiring delay lognormal missing sigma
    bad = _base_model()
    bad["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "lognormal", "mu": 1.0}}]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="lognormal dist requires 'sigma'"):
        validate_model(m)

    # wiring delay normal negative std
    bad = _base_model()
    bad["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "normal", "mean": 1.0, "std": -1.0}}]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal std must be >= 0"):
        validate_model(m)

    # wiring delay normal negative min
    bad = _base_model()
    bad["wiring"] = {
        "e0": [
            {
                "task": "t",
                "delay_ms": {"dist": "normal", "mean": 1.0, "std": 1.0, "min": -1.0},
            }
        ]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="normal min must be >= 0"):
        validate_model(m)

    # wiring delay lognormal negative sigma
    bad = _base_model()
    bad["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "lognormal", "mu": 1.0, "sigma": -1.0}}]
    }
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="lognormal sigma must be >= 0"):
        validate_model(m)

    # wiring delay normal ok -> hits _validate_dist normal success return
    ok = _base_model()
    ok["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "normal", "mean": 1.0, "std": 0.0}}]
    }
    m = Model.from_json(ok)
    validate_model(m)

    # wiring delay lognormal ok -> hits _validate_dist lognormal success return
    ok = _base_model()
    ok["wiring"] = {
        "e0": [{"task": "t", "delay_ms": {"dist": "lognormal", "mu": 0.0, "sigma": 0.0}}]
    }
    m = Model.from_json(ok)
    validate_model(m)

    # wiring delay unsupported dist
    bad = _base_model()
    bad["wiring"] = {"e0": [{"task": "t", "delay_ms": {"dist": "weird"}}]}
    m = Model.from_json(bad)
    with pytest.raises(ModelValidationError, match="unsupported dist"):
        validate_model(m)


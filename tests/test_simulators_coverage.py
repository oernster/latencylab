from __future__ import annotations

import pytest

from latencylab.model import Model
from latencylab.sim import simulate_many


def test_v2_delay_parse_errors_and_sampler_unhandled_dist() -> None:
    from latencylab.sim_v2 import _sample_ms
    from latencylab.model import DurationDist
    import random

    with pytest.raises(AssertionError, match="unhandled dist"):
        _sample_ms(__import__("random").Random(1), DurationDist(dist="weird", params={}))

    # Cover all supported distributions in sampler.
    rng = random.Random(0)
    assert _sample_ms(rng, DurationDist(dist="fixed", params={"value": 1.0})) == 1.0
    assert _sample_ms(rng, DurationDist(dist="normal", params={"mean": 0.0, "std": 0.0})) == 0.0
    v = _sample_ms(rng, DurationDist(dist="lognormal", params={"mu": 0.0, "sigma": 0.0}))
    assert v == 1.0


def test_v2_failure_when_max_tasks_per_run_exceeded() -> None:
    # Cycle: task emits same event; wiring re-enqueues task indefinitely.
    model = Model.from_json(
        {
            "schema_version": 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 0.0},
                    "emit": ["e0"],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    runs, _ = simulate_many(
        model=model, runs=1, seed=1, max_tasks_per_run=3, want_trace=False
    )
    assert runs[0].failed
    assert "max_tasks_per_run exceeded" in (runs[0].failure_reason or "")

    # Cover: if want_trace: all_traces.extend(trace)
    ok_model = Model.from_json(
        {
            "schema_version": 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 0.0},
                    "emit": [],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    ok_runs, ok_trace = simulate_many(
        model=ok_model, runs=1, seed=1, max_tasks_per_run=10, want_trace=True
    )
    assert not ok_runs[0].failed
    assert ok_trace


def test_v1_legacy_sampler_unhandled_dist_and_failure_when_max_tasks_exceeded() -> None:
    from latencylab.sim_legacy import _sample_duration_ms, simulate_many

    # Cover: if want_trace: all_traces.extend(trace)
    ok_model = Model.from_json(
        {
            "version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 0.0},
                    "emit": [],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    ok_runs, ok_trace = simulate_many(
        model=ok_model, runs=1, seed=1, max_tasks_per_run=10, want_trace=True
    )
    assert not ok_runs[0].failed
    assert ok_trace

    # Unhandled dist for legacy sampler
    with pytest.raises(AssertionError, match="unhandled dist"):
        _sample_duration_ms(
            rng=__import__("numpy").random.default_rng(1),
            dist="weird",
            params={},
        )

    # Cover supported distributions.
    rng = __import__("numpy").random.default_rng(0)
    assert _sample_duration_ms(rng, "fixed", {"value": 1.0}) == 1.0
    assert _sample_duration_ms(rng, "normal", {"mean": 0.0, "std": 0.0, "min": 0.0}) == 0.0
    assert _sample_duration_ms(rng, "lognormal", {"mu": 0.0, "sigma": 0.0}) == 1.0

    model = Model.from_json(
        {
            "version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 0.0},
                    "emit": ["e0"],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    runs, _ = simulate_many(
        model=model, runs=1, seed=1, max_tasks_per_run=3, want_trace=False
    )
    assert runs[0].failed


def test_v2_capacity_parent_branch_in_critical_path() -> None:
    # Force a queue so that capacity parent dominates event causality.
    model = Model.from_json(
        {
            "schema_version": 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 10.0},
                    "emit": [],
                }
            },
            # Two tasks enqueued at same time -> second has capacity_parent set.
            "wiring": {"e0": ["t", "t"]},
        }
    )
    runs, _ = simulate_many(
        model=model, runs=1, seed=1, max_tasks_per_run=10, want_trace=True
    )
    # Critical path should mention task at least once.
    assert runs[0].critical_path_tasks


def test_v1_capacity_parent_branch_in_critical_path() -> None:
    # Same idea as v2: enqueue two tasks at t=0 so the second is capacity-blocked.
    model = Model.from_json(
        {
            "version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 10.0},
                    "emit": [],
                }
            },
            "wiring": {"e0": ["t", "t"]},
        }
    )
    runs, _ = simulate_many(
        model=model, runs=1, seed=1, max_tasks_per_run=10, want_trace=False
    )
    assert runs[0].critical_path_tasks


def test_legacy_seed_helpers_cover_splitmix_and_seed_for_run() -> None:
    from latencylab.sim_legacy import _seed_for_run, _splitmix64

    assert isinstance(_splitmix64(0), int)
    assert _seed_for_run(123, 0) != _seed_for_run(123, 1)


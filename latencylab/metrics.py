from __future__ import annotations

import math
from collections import Counter
from typing import Any

from latencylab.model import Model
from latencylab.types import RunResult


def _percentile_sorted(values_sorted: list[float], p: int) -> float:
    if not values_sorted:
        return math.nan
    if p <= 0:
        return float(values_sorted[0])
    if p >= 100:
        return float(values_sorted[-1])

    # Linear interpolation between closest ranks, matching common percentile defs.
    n = len(values_sorted)
    pos = (p / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(values_sorted[lo])
    frac = pos - lo
    return float(values_sorted[lo] * (1.0 - frac) + values_sorted[hi] * frac)


def _percentiles(values: list[float], ps: list[int]) -> dict[str, float]:
    if not values:
        return {f"p{p}": math.nan for p in ps}
    values_sorted = sorted(float(x) for x in values)
    return {f"p{p}": _percentile_sorted(values_sorted, p) for p in ps}


def aggregate_runs(*, model: Model, runs: list[RunResult]) -> dict[str, Any]:
    ok = [r for r in runs if not r.failed]

    first_ui = [
        r.first_ui_event_time_ms for r in ok if r.first_ui_event_time_ms is not None
    ]
    last_ui = [
        r.last_ui_event_time_ms for r in ok if r.last_ui_event_time_ms is not None
    ]
    makespans = [r.makespan_ms for r in ok]

    crit_paths = [r.critical_path_tasks for r in ok if r.critical_path_tasks]
    counts = {k: int(v) for k, v in Counter(crit_paths).items()}

    return {
        "model_version": model.version,
        "runs_requested": len(runs),
        "runs_ok": len(ok),
        "runs_failed": len(runs) - len(ok),
        "latency_ms": {
            "first_ui": _percentiles(first_ui, [50, 90, 95, 99]),
            "last_ui": _percentiles(last_ui, [50, 90, 95, 99]),
            "makespan": _percentiles(makespans, [50, 90, 95, 99]),
        },
        "critical_path": {
            "top_paths": [
                {"tasks": path, "count": counts[path]}
                for path in sorted(counts, key=lambda p: (-counts[p], p))[:10]
            ]
        },
    }


def add_task_metadata(summary: dict[str, Any], *, model: Model) -> dict[str, Any]:
    if model.version != 2:
        return summary

    meta: dict[str, Any] = {}
    for name, task in model.tasks.items():
        if task.meta is None:
            continue
        meta[name] = {
            "category": task.meta.category,
            "tags": list(task.meta.tags),
            "labels": dict(task.meta.labels or {}),
        }

    if meta:
        summary = dict(summary)
        summary["task_metadata"] = meta
    return summary

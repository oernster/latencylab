from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np
from collections import Counter

from latencylab.model import Model
from latencylab.sim import RunResult


def _percentiles(values: list[float], ps: list[int]) -> dict[str, float]:
    if not values:
        return {f"p{p}": math.nan for p in ps}
    arr = np.array(values, dtype=float)
    out: dict[str, float] = {}
    for p in ps:
        out[f"p{p}"] = float(np.percentile(arr, p))
    return out


def aggregate_runs(*, model: Model, runs: list[RunResult]) -> dict[str, Any]:
    ok = [r for r in runs if not r.failed]

    first_ui = [r.first_ui_event_time_ms for r in ok if r.first_ui_event_time_ms is not None]
    last_ui = [r.last_ui_event_time_ms for r in ok if r.last_ui_event_time_ms is not None]
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


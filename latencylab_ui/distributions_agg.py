from __future__ import annotations

"""Aggregation helpers for the Distributions / Histogram UI.

This module is intentionally Qt-free.

Design constraints (v1):
- No resimulation, inference, or smoothing.
- Makespan histogram bin width uses the Freedman–Diaconis rule.
- Critical-path frequencies match the ordering rules in
  [`latencylab.metrics.aggregate_runs()`](latencylab/metrics.py:37).
"""

import math
from collections import Counter
from dataclasses import dataclass

from latencylab.types import RunResult


@dataclass(frozen=True)
class HistogramBin:
    lo: float
    hi: float
    count: int


@dataclass(frozen=True)
class CriticalPathBar:
    label_full: str
    label_display: str
    count: int


def stable_truncate(text: str, *, max_chars: int) -> str:
    """Truncate to a stable, deterministic prefix.

    We use a prefix + ellipsis so the beginning of a critical-path string remains
    visible (tasks are ordered).
    """

    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    return text[: max_chars - 1] + "…"


def _percentile_sorted(values_sorted: list[float], p: float) -> float:
    """Percentile with linear interpolation between closest ranks.

    This matches the algorithm used by the core in
    [`latencylab.metrics._percentile_sorted()`](latencylab/metrics.py:11), but is
    duplicated here to keep the UI layer independent of private core helpers.
    """

    if not values_sorted:
        return math.nan
    if p <= 0:
        return float(values_sorted[0])
    if p >= 100:
        return float(values_sorted[-1])

    n = len(values_sorted)
    pos = (p / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(values_sorted[lo])
    frac = pos - lo
    return float(values_sorted[lo] * (1.0 - frac) + values_sorted[hi] * frac)


def freedman_diaconis_bins(values: list[float]) -> list[HistogramBin]:
    """Compute histogram bins using the Freedman–Diaconis rule.

    Documentation requirement (v1):
        "Histogram bin width is computed using the Freedman–Diaconis rule from
        observed makespan values."

    Notes on degenerate inputs:
    - If we cannot compute a positive FD width (e.g., IQR=0), we produce a
      single bin spanning [min, max]. This is deterministic and explainable.
    """

    # `values` is typed as list[float], but we still accept mixed inputs from
    # callers defensively.
    xs = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not xs:
        return []
    if len(xs) == 1:
        x = xs[0]
        return [HistogramBin(lo=x, hi=x, count=1)]

    xs_sorted = sorted(xs)
    lo = xs_sorted[0]
    hi = xs_sorted[-1]
    span = hi - lo
    if span <= 0:
        return [HistogramBin(lo=lo, hi=hi, count=len(xs_sorted))]

    q1 = _percentile_sorted(xs_sorted, 25.0)
    q3 = _percentile_sorted(xs_sorted, 75.0)
    iqr = q3 - q1
    if not math.isfinite(iqr) or iqr <= 0:
        return [HistogramBin(lo=lo, hi=hi, count=len(xs_sorted))]

    width = (2.0 * iqr) / (len(xs_sorted) ** (1.0 / 3.0))
    # Defensive only: given the checks above (finite, positive IQR; finite n),
    # width should be finite and > 0.
    if not math.isfinite(width) or width <= 0:  # pragma: no cover
        return [HistogramBin(lo=lo, hi=hi, count=len(xs_sorted))]  # pragma: no cover

    bin_count = int(math.ceil(span / width))
    bin_count = max(1, bin_count)

    # Recompute width to ensure the final edge covers the max value.
    width = span / bin_count

    counts = [0 for _ in range(bin_count)]
    for x in xs_sorted:
        idx = int((x - lo) / width) if width > 0 else 0
        idx = max(0, min(bin_count - 1, idx))
        counts[idx] += 1

    out: list[HistogramBin] = []
    for i, c in enumerate(counts):
        b_lo = lo + i * width
        b_hi = lo + (i + 1) * width
        out.append(HistogramBin(lo=b_lo, hi=b_hi, count=int(c)))
    return out


def critical_path_frequency(
    runs: list[RunResult], *, top_n: int = 10
) -> list[CriticalPathBar]:
    """Compute Top-N critical-path frequency bars with an aggregated long tail.

    Ordering matches the core summary generation in
    [`latencylab.metrics.aggregate_runs()`](latencylab/metrics.py:37):
    - Only non-failed runs contribute.
    - Sort by descending frequency, then by path string.
    """

    ok_paths = [
        r.critical_path_tasks
        for r in runs
        if (not r.failed) and r.critical_path_tasks
    ]
    counts = Counter(ok_paths)
    if not counts:
        return []

    ordered = sorted(counts, key=lambda p: (-counts[p], p))
    top = ordered[:top_n]
    rest = ordered[top_n:]

    out: list[CriticalPathBar] = []
    for path in top:
        out.append(
            CriticalPathBar(
                label_full=path,
                # Display uses the full path string; the chart is responsible for
                # deterministic wrapping/eliding to available pixels.
                label_display=path,
                count=int(counts[path]),
            )
        )

    if rest:
        other_count = int(sum(counts[p] for p in rest))
        out.append(
            CriticalPathBar(
                label_full="Other (long tail)",
                label_display="Other (long tail)",
                count=other_count,
            )
        )

    return out


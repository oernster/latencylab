from __future__ import annotations

"""Small testable façade around the threaded RunController.

This keeps the real controller Qt-threaded, but provides a pure function to
compute elapsed time for deterministic coverage.
"""


def elapsed_seconds(*, started_at: float | None, now: float) -> float:
    if started_at is None:
        return 0.0
    return max(0.0, now - started_at)


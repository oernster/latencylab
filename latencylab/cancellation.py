from __future__ import annotations

"""Stopping a run that is already under way.

The simulator is CPU-bound, so it can only be stopped by asking it to stop:
there is no safe way to interrupt it from outside. What it offers instead is a
place to ask, checked once per RUN rather than once per event.

The run boundary is the right place for three reasons. Each run seeds its own
generator from the run index, so stopping between runs cannot leave a run half
simulated. The check costs one predicate per run rather than one per event, so
it is invisible against the work. And the worst-case delay before a run stops is
one run, which is a number the user can be told.

Nothing here imports Qt, or anything else. The user interface passes in an
object with an `is_cancelled` method and the simulator never learns what it is.
"""

from typing import Protocol


class CancellationSignal(Protocol):
    """Something that can be asked whether the work should stop."""

    def is_cancelled(self) -> bool:
        """True once the run should stop at the next opportunity."""


class RunCancelled(Exception):
    """Raised when a run stops because it was asked to.

    Deliberately an exception rather than a partial result. A cancelled set of
    runs is not a smaller set of runs: aggregating half of them would produce
    percentiles that look exactly like real ones, describing a system nobody
    asked about. Refusing to return anything is what stops that being possible.
    """

    def __init__(self, completed_runs: int) -> None:
        super().__init__(f"Cancelled after {completed_runs} runs.")
        self.completed_runs = completed_runs


def should_stop(signal: CancellationSignal | None) -> bool:
    """Whether `signal` is asking for a stop; False when there is no signal.

    Written once here so neither executor has to repeat the None check, and so
    "no signal" can never accidentally read as "cancelled".
    """

    return signal is not None and signal.is_cancelled()

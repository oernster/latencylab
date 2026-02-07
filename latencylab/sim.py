from __future__ import annotations

# Public simulation entrypoint.
#
# This module is intentionally stdlib-only and selects an execution strategy via
# the RunExecutor abstraction. The NumPy-backed legacy implementation is isolated
# behind a lazy import.

from latencylab.executors import default_executor_for_model
from latencylab.model import Model
from latencylab.types import RunResult, TaskInstance


def simulate_many(
    *,
    model: Model,
    runs: int,
    seed: int,
    max_tasks_per_run: int,
    want_trace: bool,
) -> tuple[list[RunResult], list[TaskInstance]]:
    executor = default_executor_for_model(model)
    return executor.execute(
        model=model,
        runs=runs,
        seed=seed,
        max_tasks_per_run=max_tasks_per_run,
        want_trace=want_trace,
    )

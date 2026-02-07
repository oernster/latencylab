from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from latencylab.model import Model
from latencylab.types import RunResult, TaskInstance


class RunExecutor(Protocol):
    def execute(
        self,
        *,
        model: Model,
        runs: int,
        seed: int,
        max_tasks_per_run: int,
        want_trace: bool,
    ) -> tuple[list[RunResult], list[TaskInstance]]:
        raise NotImplementedError


@dataclass(frozen=True)
class LegacyNumpyExecutor:
    def execute(
        self,
        *,
        model: Model,
        runs: int,
        seed: int,
        max_tasks_per_run: int,
        want_trace: bool,
    ) -> tuple[list[RunResult], list[TaskInstance]]:
        from latencylab.sim_legacy import simulate_many

        return simulate_many(
            model=model,
            runs=runs,
            seed=seed,
            max_tasks_per_run=max_tasks_per_run,
            want_trace=want_trace,
        )


@dataclass(frozen=True)
class StdlibV2Executor:
    def execute(
        self,
        *,
        model: Model,
        runs: int,
        seed: int,
        max_tasks_per_run: int,
        want_trace: bool,
    ) -> tuple[list[RunResult], list[TaskInstance]]:
        from latencylab.sim_v2 import simulate_many

        return simulate_many(
            model=model,
            runs=runs,
            seed=seed,
            max_tasks_per_run=max_tasks_per_run,
            want_trace=want_trace,
        )


def default_executor_for_model(model: Model) -> RunExecutor:
    if model.version == 1:
        return LegacyNumpyExecutor()
    if model.version == 2:
        return StdlibV2Executor()
    raise ValueError(f"Unsupported model version: {model.version}")

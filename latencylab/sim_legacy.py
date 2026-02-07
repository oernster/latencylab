from __future__ import annotations

"""Legacy v1 executor (NumPy-backed).

FROZEN.

This module is intentionally retained as a migration oracle for v1 semantics.

Policy:
- No new features.
- No refactors / style alignment with v2.
- Changes allowed only for: critical bug fixes, security issues, or test harness
  maintenance.

Rationale:
- Provides a trusted behavioral baseline and regression oracle while v2 is
  validated in the wild.
"""

# NumPy-backed legacy simulator, preserved for exact v1 output compatibility.

from collections import deque
import heapq
from typing import TYPE_CHECKING

try:
    import numpy as np
except ModuleNotFoundError as exc:  # pragma: no cover
    np = None  # type: ignore[assignment]
    _NUMPY_IMPORT_ERROR = exc
else:
    _NUMPY_IMPORT_ERROR = None

if TYPE_CHECKING:  # pragma: no cover
    from numpy.random import Generator

from latencylab.model import Model
from latencylab.types import EventOccurrence, RunResult, TaskInstance


def _require_numpy() -> None:
    if np is None:  # pragma: no cover
        raise ModuleNotFoundError(
            "NumPy is required for legacy v1 execution. Install with: pip install numpy"
        ) from _NUMPY_IMPORT_ERROR


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return z ^ (z >> 31)


def _seed_for_run(base_seed: int, run_id: int) -> int:
    return _splitmix64((base_seed & 0xFFFFFFFFFFFFFFFF) ^ (run_id & 0xFFFFFFFFFFFFFFFF))


def _sample_duration_ms(rng: "Generator", dist: str, params: dict[str, float]) -> float:
    if dist == "fixed":
        return float(params["value"])
    if dist == "normal":
        mean = float(params["mean"])
        std = float(params["std"])
        min_v = float(params.get("min", 0.0))
        return float(max(min_v, rng.normal(loc=mean, scale=std)))
    if dist == "lognormal":
        mu = float(params["mu"])
        sigma = float(params["sigma"])
        return float(rng.lognormal(mean=mu, sigma=sigma))
    raise AssertionError(f"unhandled dist: {dist}")


def simulate_many(
    *,
    model: Model,
    runs: int,
    seed: int,
    max_tasks_per_run: int,
    want_trace: bool,
) -> tuple[list[RunResult], list[TaskInstance]]:
    _require_numpy()

    all_runs: list[RunResult] = []
    all_traces: list[TaskInstance] = []

    for run_id in range(runs):
        rng = np.random.default_rng(_seed_for_run(seed, run_id))
        run_res, trace = simulate_one(
            model=model,
            run_id=run_id,
            rng=rng,
            max_tasks_per_run=max_tasks_per_run,
            want_trace=want_trace,
        )
        all_runs.append(run_res)
        if want_trace:
            all_traces.extend(trace)

    return all_runs, all_traces


def simulate_one(
    *,
    model: Model,
    run_id: int,
    rng: "Generator",
    max_tasks_per_run: int,
    want_trace: bool,
) -> tuple[RunResult, list[TaskInstance]]:
    # Per-context queues of pending task instances to start.
    ctx_queues: dict[str, deque[tuple[str, float, int | None]]] = {
        name: deque() for name in model.contexts
    }
    # Free slots and slot->last task instance.
    free_slots: dict[str, list[int]] = {}
    last_on_slot: dict[str, dict[int, int | None]] = {}
    for ctx_name, ctx in model.contexts.items():
        free_slots[ctx_name] = list(range(ctx.concurrency))
        last_on_slot[ctx_name] = {i: None for i in range(ctx.concurrency)}

    instances: dict[int, TaskInstance] = {}
    traces: list[TaskInstance] = []
    next_instance_id = 1
    next_event_id = 1

    event_occurrences: list[EventOccurrence] = []

    # Completion heap entries are:
    # (end_time, context, task_name, instance_id, slot_index)
    completion_heap: list[tuple[float, str, str, int, int]] = []

    # Safety counters.
    tasks_created = 0
    failed = False
    failure_reason: str | None = None

    def occur_event(
        name: str, time_ms: float, source_task_instance_id: int | None
    ) -> None:
        nonlocal next_event_id
        eo = EventOccurrence(
            event_id=next_event_id,
            name=name,
            time_ms=time_ms,
            source_task_instance_id=source_task_instance_id,
        )
        next_event_id += 1
        event_occurrences.append(eo)

        for task_name in model.wiring.get(name, ()):  # unwired events are allowed
            enqueue_task(
                task_name=task_name,
                enqueue_time_ms=time_ms,
                parent_task=source_task_instance_id,
            )

    def enqueue_task(
        task_name: str, enqueue_time_ms: float, parent_task: int | None
    ) -> None:
        nonlocal tasks_created, failed, failure_reason
        if tasks_created >= max_tasks_per_run:
            failed = True
            failure_reason = f"max_tasks_per_run exceeded ({max_tasks_per_run})"
            return
        tasks_created += 1

        task_def = model.tasks[task_name]
        ctx_queues[task_def.context].append((task_name, enqueue_time_ms, parent_task))

    # Inject entry event at t=0.
    t = 0.0
    occur_event(model.entry_event, time_ms=0.0, source_task_instance_id=None)

    def try_start_tasks(now_ms: float) -> None:
        nonlocal next_instance_id
        made_progress = True
        while made_progress and not failed:
            made_progress = False
            for ctx_name, q in ctx_queues.items():
                if not q or not free_slots[ctx_name]:
                    continue
                # FIFO: pop left.
                task_name, enqueue_time_ms, parent_task = q.popleft()

                # Allocate a slot deterministically: lowest index.
                free_slots[ctx_name].sort()
                slot = free_slots[ctx_name].pop(0)
                cap_parent = last_on_slot[ctx_name][slot]

                start_time_ms = now_ms
                duration = _sample_duration_ms(
                    rng,
                    model.tasks[task_name].duration_ms.dist,
                    model.tasks[task_name].duration_ms.params,
                )
                end_time_ms = start_time_ms + duration

                inst = TaskInstance(
                    instance_id=next_instance_id,
                    run_id=run_id,
                    task_name=task_name,
                    context=ctx_name,
                    enqueue_time_ms=float(enqueue_time_ms),
                    start_time_ms=float(start_time_ms),
                    end_time_ms=float(end_time_ms),
                    queue_wait_ms=float(start_time_ms - enqueue_time_ms),
                    duration_ms=float(duration),
                    emitted_events=tuple(model.tasks[task_name].emit),
                    parent_task_instance_id=parent_task,
                    capacity_parent_instance_id=cap_parent,
                )
                instances[inst.instance_id] = inst
                if want_trace:
                    traces.append(inst)
                next_instance_id += 1

                heapq.heappush(
                    completion_heap,
                    (
                        inst.end_time_ms,
                        ctx_name,
                        inst.task_name,
                        inst.instance_id,
                        slot,
                    ),
                )
                last_on_slot[ctx_name][slot] = inst.instance_id
                made_progress = True

    # Initial scheduling at t=0.
    try_start_tasks(t)

    # Event loop.
    while completion_heap and not failed:
        # Pop all completions at earliest time.
        t_next = completion_heap[0][0]
        t = t_next

        completed: list[tuple[float, str, str, int, int]] = []
        while completion_heap and completion_heap[0][0] == t_next:
            completed.append(heapq.heappop(completion_heap))

        # Deterministic processing order for same-time completions.
        completed.sort(key=lambda x: (x[1], x[2], x[3]))

        for _, ctx_name, task_name, instance_id, slot in completed:
            # Free the slot.
            free_slots[ctx_name].append(slot)

            inst = instances[instance_id]
            # Emit events at completion time.
            for ev in inst.emitted_events:
                occur_event(
                    ev, time_ms=inst.end_time_ms, source_task_instance_id=instance_id
                )

        # Start any newly-enqueued tasks at this same time.
        try_start_tasks(t)

    makespan = 0.0
    if instances:
        makespan = max(i.end_time_ms for i in instances.values())

    ui_times: list[float] = []
    for eo in event_occurrences:
        ev_def = model.events.get(eo.name)
        if ev_def and ev_def.has_tag("ui"):
            ui_times.append(eo.time_ms)
    first_ui = min(ui_times) if ui_times else None
    last_ui = max(ui_times) if ui_times else None

    critical_tasks: list[str] = []
    critical_ms = makespan
    if instances:
        last_inst = max(
            instances.values(),
            key=lambda i: (i.end_time_ms, i.context, i.task_name, i.instance_id),
        )
        cur: TaskInstance | None = last_inst
        while cur is not None:
            critical_tasks.append(cur.task_name)

            cap_pred = (
                instances[cur.capacity_parent_instance_id]
                if cur.capacity_parent_instance_id is not None
                else None
            )
            cap_time = cap_pred.end_time_ms if cap_pred is not None else float("-inf")

            evt_pred = (
                instances[cur.parent_task_instance_id]
                if cur.parent_task_instance_id is not None
                else None
            )
            evt_time = cur.enqueue_time_ms

            if cap_time > evt_time:
                cur = cap_pred
            elif evt_pred is not None and evt_time >= cap_time:
                cur = evt_pred
            else:
                cur = None

        critical_tasks.reverse()

    critical_path_tasks = ">".join(critical_tasks)

    run = RunResult(
        run_id=run_id,
        first_ui_event_time_ms=first_ui,
        last_ui_event_time_ms=last_ui,
        makespan_ms=float(makespan),
        critical_path_ms=float(critical_ms),
        critical_path_tasks=critical_path_tasks,
        failed=failed,
        failure_reason=failure_reason,
    )

    return run, traces

from __future__ import annotations

# Stdlib-only v2 simulator with delayed wiring and synthetic delay nodes.

from collections import deque
import heapq
import math
import random

from latencylab.model import DurationDist, Model, WiringEdge
from latencylab.types import EventOccurrence, RunResult, TaskInstance

DELAY_CONTEXT = "__delay__"


def _sample_ms(rng: random.Random, dist: DurationDist) -> float:
    name = dist.dist
    p = dist.params
    if name == "fixed":
        return float(p["value"])
    if name == "normal":
        mean = float(p["mean"])
        std = float(p["std"])
        min_v = float(p.get("min", 0.0))
        return float(max(min_v, rng.gauss(mu=mean, sigma=std)))
    if name == "lognormal":
        mu = float(p["mu"])
        sigma = float(p["sigma"])
        return float(math.exp(rng.gauss(mu=mu, sigma=sigma)))
    raise AssertionError(f"unhandled dist: {name}")


def _delay_task_name(event_name: str, task_name: str) -> str:
    return f"delay({event_name}->{task_name})"


def simulate_many(
    *,
    model: Model,
    runs: int,
    seed: int,
    max_tasks_per_run: int,
    want_trace: bool,
) -> tuple[list[RunResult], list[TaskInstance]]:
    all_runs: list[RunResult] = []
    all_traces: list[TaskInstance] = []
    for run_id in range(runs):
        rng = random.Random((seed << 32) ^ run_id)
        res, trace = simulate_one(
            model=model,
            run_id=run_id,
            rng=rng,
            max_tasks_per_run=max_tasks_per_run,
            want_trace=want_trace,
        )
        all_runs.append(res)
        if want_trace:
            all_traces.extend(trace)
    return all_runs, all_traces


def simulate_one(
    *,
    model: Model,
    run_id: int,
    rng: random.Random,
    max_tasks_per_run: int,
    want_trace: bool,
) -> tuple[RunResult, list[TaskInstance]]:
    ctx_queues: dict[str, deque[tuple[str, float, int | None]]] = {
        name: deque() for name in model.contexts
    }

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

    # (time, kind, ctx, name, instance_id, slot)
    # kind: 0=delay_end, 1=task_end
    completion_heap: list[tuple[float, int, str, str, int, int | None]] = []
    delay_targets: dict[int, tuple[str, float]] = {}

    tasks_created = 0
    failed = False
    failure_reason: str | None = None

    def _record_instance(inst: TaskInstance) -> None:
        instances[inst.instance_id] = inst
        if want_trace:
            traces.append(inst)

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
        ctx_queues[task_def.context].append(
            (task_name, float(enqueue_time_ms), parent_task)
        )

    def schedule_delay(
        *,
        event_name: str,
        edge: WiringEdge,
        emit_time_ms: float,
        source_task: int | None,
    ) -> None:
        nonlocal next_instance_id
        assert edge.delay_ms is not None
        delay_ms = _sample_ms(rng, edge.delay_ms)
        delay_ms = max(0.0, float(delay_ms))
        start = float(emit_time_ms)
        end = start + delay_ms

        inst = TaskInstance(
            instance_id=next_instance_id,
            run_id=run_id,
            task_name=_delay_task_name(event_name, edge.task),
            context=DELAY_CONTEXT,
            enqueue_time_ms=start,
            start_time_ms=start,
            end_time_ms=end,
            queue_wait_ms=0.0,
            duration_ms=delay_ms,
            emitted_events=(),
            parent_task_instance_id=source_task,
            capacity_parent_instance_id=None,
        )
        delay_targets[inst.instance_id] = (edge.task, start)
        _record_instance(inst)

        heapq.heappush(
            completion_heap,
            (inst.end_time_ms, 0, inst.context, inst.task_name, inst.instance_id, None),
        )
        next_instance_id += 1

    def occur_event(
        name: str, time_ms: float, source_task_instance_id: int | None
    ) -> None:
        nonlocal next_event_id
        eo = EventOccurrence(
            event_id=next_event_id,
            name=name,
            time_ms=float(time_ms),
            source_task_instance_id=source_task_instance_id,
        )
        next_event_id += 1
        event_occurrences.append(eo)

        edges = model.wiring_edges.get(name, ())
        for edge in edges:
            if edge.delay_ms is None:
                enqueue_task(
                    task_name=edge.task,
                    enqueue_time_ms=float(time_ms),
                    parent_task=source_task_instance_id,
                )
            else:
                schedule_delay(
                    event_name=name,
                    edge=edge,
                    emit_time_ms=float(time_ms),
                    source_task=source_task_instance_id,
                )

    def try_start_tasks(now_ms: float) -> None:
        nonlocal next_instance_id
        made_progress = True
        while made_progress and not failed:
            made_progress = False
            for ctx_name, q in ctx_queues.items():
                if not q or not free_slots[ctx_name]:
                    continue
                task_name, enqueue_time_ms, parent_task = q.popleft()

                free_slots[ctx_name].sort()
                slot = free_slots[ctx_name].pop(0)
                cap_parent = last_on_slot[ctx_name][slot]

                start_time_ms = float(now_ms)
                duration = _sample_ms(rng, model.tasks[task_name].duration_ms)
                duration = max(0.0, float(duration))
                end_time_ms = start_time_ms + duration

                inst = TaskInstance(
                    instance_id=next_instance_id,
                    run_id=run_id,
                    task_name=task_name,
                    context=ctx_name,
                    enqueue_time_ms=float(enqueue_time_ms),
                    start_time_ms=start_time_ms,
                    end_time_ms=end_time_ms,
                    queue_wait_ms=float(start_time_ms - enqueue_time_ms),
                    duration_ms=duration,
                    emitted_events=tuple(model.tasks[task_name].emit),
                    parent_task_instance_id=parent_task,
                    capacity_parent_instance_id=cap_parent,
                )
                _record_instance(inst)
                next_instance_id += 1

                heapq.heappush(
                    completion_heap,
                    (
                        inst.end_time_ms,
                        1,
                        inst.context,
                        inst.task_name,
                        inst.instance_id,
                        slot,
                    ),
                )
                last_on_slot[ctx_name][slot] = inst.instance_id
                made_progress = True

    t = 0.0
    occur_event(model.entry_event, time_ms=0.0, source_task_instance_id=None)
    try_start_tasks(t)

    while completion_heap and not failed:
        t_next = completion_heap[0][0]
        t = t_next

        completed: list[tuple[float, int, str, str, int, int | None]] = []
        while completion_heap and completion_heap[0][0] == t_next:
            completed.append(heapq.heappop(completion_heap))

        # Deterministic order for same-time completions.
        completed.sort(key=lambda x: (x[1], x[2], x[3], x[4]))

        for _, kind, ctx_name, _name, instance_id, slot in completed:
            inst = instances[instance_id]
            if kind == 1:
                assert slot is not None
                free_slots[ctx_name].append(int(slot))
                for ev in inst.emitted_events:
                    occur_event(
                        ev,
                        time_ms=inst.end_time_ms,
                        source_task_instance_id=instance_id,
                    )
            else:
                target_task, _emit_time = delay_targets[instance_id]
                enqueue_task(
                    task_name=target_task,
                    enqueue_time_ms=inst.end_time_ms,
                    parent_task=instance_id,
                )

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

    run = RunResult(
        run_id=run_id,
        first_ui_event_time_ms=first_ui,
        last_ui_event_time_ms=last_ui,
        makespan_ms=float(makespan),
        critical_path_ms=float(critical_ms),
        critical_path_tasks=">".join(critical_tasks),
        failed=failed,
        failure_reason=failure_reason,
    )
    return run, traces

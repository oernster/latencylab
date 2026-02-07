from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskInstance:
    instance_id: int
    run_id: int
    task_name: str
    context: str
    enqueue_time_ms: float
    start_time_ms: float
    end_time_ms: float
    queue_wait_ms: float
    duration_ms: float
    emitted_events: tuple[str, ...]
    parent_task_instance_id: int | None  # event-causality (or delay-causality)
    capacity_parent_instance_id: int | None  # slot causality


@dataclass(frozen=True)
class RunResult:
    run_id: int
    first_ui_event_time_ms: float | None
    last_ui_event_time_ms: float | None
    makespan_ms: float
    critical_path_ms: float
    critical_path_tasks: str
    failed: bool
    failure_reason: str | None


@dataclass(frozen=True)
class EventOccurrence:
    event_id: int
    name: str
    time_ms: float
    source_task_instance_id: int | None

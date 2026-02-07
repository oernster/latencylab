from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextDef:
    concurrency: int
    policy: str = "fifo"


@dataclass(frozen=True)
class EventDef:
    tags: tuple[str, ...] = ()

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


@dataclass(frozen=True)
class DurationDist:
    dist: str
    params: dict[str, float]


@dataclass(frozen=True)
class TaskDef:
    context: str
    duration_ms: DurationDist
    emit: tuple[str, ...] = ()


@dataclass(frozen=True)
class Model:
    version: int
    entry_event: str
    contexts: dict[str, ContextDef]
    events: dict[str, EventDef]
    tasks: dict[str, TaskDef]
    wiring: dict[str, tuple[str, ...]]

    @staticmethod
    def from_json(obj: dict[str, Any]) -> "Model":
        version = int(obj["version"])
        entry_event = str(obj["entry_event"])

        contexts: dict[str, ContextDef] = {}
        for name, c in obj.get("contexts", {}).items():
            contexts[str(name)] = ContextDef(
                concurrency=int(c["concurrency"]),
                policy=str(c.get("policy", "fifo")),
            )

        events: dict[str, EventDef] = {}
        for name, e in obj.get("events", {}).items():
            tags = tuple(str(t) for t in e.get("tags", []))
            events[str(name)] = EventDef(tags=tags)

        tasks: dict[str, TaskDef] = {}
        for name, t in obj.get("tasks", {}).items():
            d = t["duration_ms"]
            dist = str(d["dist"])
            params = {str(k): float(v) for k, v in d.items() if k != "dist"}
            duration = DurationDist(dist=dist, params=params)
            emit = tuple(str(ev) for ev in t.get("emit", []))
            tasks[str(name)] = TaskDef(
                context=str(t["context"]),
                duration_ms=duration,
                emit=emit,
            )

        wiring: dict[str, tuple[str, ...]] = {}
        for ev, listeners in obj.get("wiring", {}).items():
            wiring[str(ev)] = tuple(str(x) for x in listeners)

        return Model(
            version=version,
            entry_event=entry_event,
            contexts=contexts,
            events=events,
            tasks=tasks,
            wiring=wiring,
        )


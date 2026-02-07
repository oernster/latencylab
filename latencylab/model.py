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
class TaskMeta:
    category: str | None = None
    tags: tuple[str, ...] = ()
    labels: dict[str, str] = None  # type: ignore[assignment]

    @staticmethod
    def from_json(obj: dict[str, Any] | None) -> "TaskMeta | None":
        if not obj:
            return None
        category = obj.get("category")
        tags = tuple(str(t) for t in obj.get("tags", []))
        labels_raw = obj.get("labels", {})
        labels = {str(k): str(v) for k, v in labels_raw.items()} if labels_raw else {}
        return TaskMeta(
            category=str(category) if category is not None else None,
            tags=tags,
            labels=labels,
        )


@dataclass(frozen=True)
class WiringEdge:
    task: str
    delay_ms: DurationDist | None = None


@dataclass(frozen=True)
class TaskDef:
    context: str
    duration_ms: DurationDist
    emit: tuple[str, ...] = ()
    meta: TaskMeta | None = None


@dataclass(frozen=True)
class Model:
    version: int
    entry_event: str
    contexts: dict[str, ContextDef]
    events: dict[str, EventDef]
    tasks: dict[str, TaskDef]
    # v1-compatible wiring (event -> task names)
    wiring: dict[str, tuple[str, ...]]
    # v2 wiring with optional delay per edge (event -> edges)
    wiring_edges: dict[str, tuple[WiringEdge, ...]]

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
            meta = TaskMeta.from_json(t.get("meta"))
            tasks[str(name)] = TaskDef(
                context=str(t["context"]),
                duration_ms=duration,
                emit=emit,
                meta=meta,
            )

        def _parse_dist(dist_obj: Any) -> DurationDist:
            if isinstance(dist_obj, (int, float)):
                return DurationDist(dist="fixed", params={"value": float(dist_obj)})
            if not isinstance(dist_obj, dict):
                raise TypeError("delay_ms must be a number or a dist object")
            dname = str(dist_obj["dist"])
            params = {str(k): float(v) for k, v in dist_obj.items() if k != "dist"}
            return DurationDist(dist=dname, params=params)

        wiring_edges: dict[str, tuple[WiringEdge, ...]] = {}
        wiring_flat: dict[str, tuple[str, ...]] = {}
        for ev, listeners in obj.get("wiring", {}).items():
            ev_name = str(ev)
            edges: list[WiringEdge] = []
            flat: list[str] = []
            for item in listeners:
                if isinstance(item, str):
                    edges.append(WiringEdge(task=str(item), delay_ms=None))
                    flat.append(str(item))
                elif isinstance(item, dict):
                    task = str(item["task"])
                    delay = item.get("delay_ms")
                    delay_dist = _parse_dist(delay) if delay is not None else None
                    edges.append(WiringEdge(task=task, delay_ms=delay_dist))
                    flat.append(task)
                else:
                    raise TypeError("wiring listeners must be strings or objects")
            wiring_edges[ev_name] = tuple(edges)
            wiring_flat[ev_name] = tuple(flat)

        return Model(
            version=version,
            entry_event=entry_event,
            contexts=contexts,
            events=events,
            tasks=tasks,
            wiring=wiring_flat,
            wiring_edges=wiring_edges,
        )

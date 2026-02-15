from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComposerState:
    """Structured, schema-faithful model authoring state.

    Notes:
    - `model_name` is UI-only and never serialized into JSON.
    - `contexts`, `tasks`, and `wiring` are intentionally plain dicts so the UI
      can mutate them without needing Qt types.
    """

    model_name: str = "model"
    version: int = 2
    entry_event: str = "start"

    # name -> {"concurrency": int, "policy": "fifo"}
    contexts: dict[str, dict[str, Any]] = field(default_factory=dict)

    # task_name ->
    # {
    #   "context": str,
    #   "duration_ms": {"dist": str, ...params},
    #   "emit": list[str],
    #   "meta": {"category": str|None, "tags": list[str], "labels": {k:v}}  (v2)
    # }
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)

    # event -> list[{"task": str, "delay_ms": {"dist": str, ...} | number | None}]
    wiring: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def dumps_deterministic(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


def _split_csv(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").split(","):
        s = raw.strip()
        if s:
            out.append(s)
    return out


def parse_labels(text: str) -> dict[str, str]:
    """Parse labels from 'k=v, a=b' into a dict.

    Invalid segments are ignored (UI must never crash on intermediate state).
    """

    labels: dict[str, str] = {}
    for seg in _split_csv(text):
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        labels[k] = v
    return labels


def derive_events(state: ComposerState) -> dict[str, dict[str, Any]]:
    """Derive events deterministically per decision lock.

    - Union of: entry_event, all task.emit, all wiring keys.
    - Tags: entry_event -> ["entry"], else [].
    """

    events: set[str] = set()
    if state.entry_event.strip():
        events.add(state.entry_event.strip())

    for t in state.tasks.values():
        for ev in t.get("emit", []) or []:
            if str(ev).strip():
                events.add(str(ev).strip())

    for ev in state.wiring.keys():
        if str(ev).strip():
            events.add(str(ev).strip())

    out: dict[str, dict[str, Any]] = {}
    for name in sorted(events):
        if name == state.entry_event.strip():
            out[name] = {"tags": ["entry"]}
        else:
            out[name] = {"tags": []}
    return out


def build_raw_model_dict(state: ComposerState) -> dict[str, Any]:
    """Serialize ComposerState into a dict accepted by `Model.from_json()`.

    Raises:
        ValueError: on obviously-invalid high-level state (e.g. bad version).
    """

    version = int(state.version)
    if version not in (1, 2):
        raise ValueError(f"Unsupported schema version: {version}")

    raw: dict[str, Any] = {
        "schema_version": version,
        "entry_event": str(state.entry_event),
        "contexts": {},
        "events": {},
        "tasks": {},
    }

    # Contexts.
    for name in sorted(state.contexts.keys()):
        c = state.contexts[name] or {}
        raw["contexts"][str(name)] = {
            "concurrency": int(c.get("concurrency", 1)),
            "policy": "fifo",
        }

    # Tasks.
    for name in sorted(state.tasks.keys()):
        t = state.tasks[name] or {}
        d = t.get("duration_ms") or {}

        dist = str(d.get("dist", "fixed"))
        params = {k: float(v) for k, v in (d.items()) if k != "dist" and v is not None}
        duration_obj = {"dist": dist, **params}

        task_obj: dict[str, Any] = {
            "context": str(t.get("context", "")),
            "duration_ms": duration_obj,
        }
        emit_list = [str(e) for e in (t.get("emit") or []) if str(e).strip()]
        if emit_list:
            task_obj["emit"] = emit_list

        if version >= 2:
            meta = t.get("meta") or {}
            category = meta.get("category")
            tags = [str(x) for x in (meta.get("tags") or []) if str(x).strip()]
            labels = {str(k): str(v) for k, v in (meta.get("labels") or {}).items()}
            if category is not None or tags or labels:
                task_obj["meta"] = {
                    "category": str(category) if category is not None else None,
                    "tags": tags,
                    "labels": labels,
                }

        raw["tasks"][str(name)] = task_obj

    # Wiring.
    if state.wiring:
        wiring_obj: dict[str, Any] = {}
        for ev in sorted(state.wiring.keys()):
            listeners = state.wiring.get(ev) or []
            out_list: list[Any] = []
            for edge in listeners:
                task = str((edge or {}).get("task", "")).strip()
                if not task:
                    continue
                delay = (edge or {}).get("delay_ms")
                if delay is None or version == 1:
                    # MVP: no delays. Also keep v1 export simple (string listeners).
                    out_list.append(task)
                else:
                    out_list.append({"task": task, "delay_ms": delay})
            if out_list:
                wiring_obj[str(ev)] = out_list
        if wiring_obj:
            raw["wiring"] = wiring_obj

    # Derived events last so it includes emits/wiring.
    raw["events"] = derive_events(state)
    return raw


def build_stress_variant_state(state: ComposerState, *, multiplier: float) -> ComposerState:
    """Return a deep-copied stress variant per decision lock."""

    m = float(multiplier)
    if not (m > 0.0):
        raise ValueError("Stress multiplier must be > 0")

    s2 = copy.deepcopy(state)
    for t in s2.tasks.values():
        d = t.get("duration_ms") or {}
        dist = str(d.get("dist", "fixed"))
        if dist == "fixed":
            if "value" in d:
                d["value"] = float(d["value"]) * m
        elif dist == "normal":
            if "mean" in d:
                d["mean"] = float(d["mean"]) * m
            if "std" in d:
                d["std"] = float(d["std"]) * m
        elif dist == "lognormal":
            if "mu" in d:
                d["mu"] = float(d["mu"]) + math.log(m)

    # Optional: apply the same stress multiplier to wiring delays if present.
    for edges in s2.wiring.values():
        for edge in edges:
            delay = (edge or {}).get("delay_ms")
            if not isinstance(delay, dict):
                continue
            dist = str(delay.get("dist", "fixed"))
            if dist == "fixed" and "value" in delay:
                delay["value"] = float(delay["value"]) * m
            elif dist == "normal":
                if "mean" in delay:
                    delay["mean"] = float(delay["mean"]) * m
                if "std" in delay:
                    delay["std"] = float(delay["std"]) * m
            elif dist == "lognormal" and "mu" in delay:
                delay["mu"] = float(delay["mu"]) + math.log(m)

    s2.model_name = f"{state.model_name}_STRESS"
    return s2


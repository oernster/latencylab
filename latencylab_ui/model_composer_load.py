from __future__ import annotations

"""Putting an existing model back into the composer.

The composer was authoring-only: it could build a model and export it, and
nothing could put one back in, so a model you had just opened could not be
edited. Editing is the same surface driven from the other end, which is why
this is a setter across the four editors rather than a second editing mode.

It lives beside the dock rather than inside it for the same reason the main
window's dock switching does: the dock is at its size limit, and this is one
cohesive job with an order that needs explaining.
"""

from typing import Any

from latencylab_ui.model_composer_types import (
    read_schema_version,
    wiring_edges_from_raw,
)


def load_raw_model(dock, raw: dict[str, Any], *, model_name: str) -> None:
    """Fill `dock`'s editors from a parsed model.

    The order is load-bearing. Contexts go in first because a task card can
    only select a context the contexts table already knows about. The version
    goes in before the tasks because it decides whether a card shows its
    category field at all. Wiring goes last, once the task and event names it
    offers people are real ones.
    """

    version = read_schema_version(raw)

    dock._system.set_values(  # noqa: SLF001
        model_name=model_name,
        version=version,
        entry_event=str(raw.get("entry_event", "") or ""),
    )

    contexts = raw.get("contexts")
    dock._contexts.set_contexts(  # noqa: SLF001
        contexts if isinstance(contexts, dict) else {}
    )

    dock._tasks.set_version(version)  # noqa: SLF001
    dock._tasks.set_context_names(dock._contexts.context_names())  # noqa: SLF001
    tasks = raw.get("tasks")
    dock._tasks.set_tasks(tasks if isinstance(tasks, dict) else {})  # noqa: SLF001

    dock._wiring.set_task_names(dock._tasks.task_names())  # noqa: SLF001
    dock._wiring.set_wiring(wiring_edges_from_raw(raw.get("wiring")))  # noqa: SLF001

    dock.clear_validation()

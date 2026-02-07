from __future__ import annotations

from latencylab.model import Model


class ModelValidationError(ValueError):
    pass


def validate_model(model: Model) -> None:
    if model.version != 1:
        raise ModelValidationError(f"Unsupported model version: {model.version} (expected 1)")

    if model.entry_event not in model.events:
        raise ModelValidationError(
            f"entry_event '{model.entry_event}' must exist in events"
        )

    for ctx_name, ctx in model.contexts.items():
        if ctx.concurrency < 1:
            raise ModelValidationError(
                f"context '{ctx_name}' concurrency must be >= 1 (got {ctx.concurrency})"
            )
        if ctx.policy != "fifo":
            raise ModelValidationError(
                f"context '{ctx_name}' policy must be 'fifo' in MVP (got {ctx.policy!r})"
            )

    for task_name, task in model.tasks.items():
        if task.context not in model.contexts:
            raise ModelValidationError(
                f"task '{task_name}' references unknown context '{task.context}'"
            )

        dist = task.duration_ms.dist
        p = task.duration_ms.params
        if dist == "fixed":
            if "value" not in p:
                raise ModelValidationError(
                    f"task '{task_name}' fixed dist requires 'value'"
                )
            if p["value"] < 0:
                raise ModelValidationError(
                    f"task '{task_name}' fixed value must be >= 0"
                )
        elif dist == "normal":
            for k in ("mean", "std"):
                if k not in p:
                    raise ModelValidationError(
                        f"task '{task_name}' normal dist requires '{k}'"
                    )
            if p["std"] < 0:
                raise ModelValidationError(
                    f"task '{task_name}' normal std must be >= 0"
                )
            if "min" in p and p["min"] < 0:
                raise ModelValidationError(
                    f"task '{task_name}' normal min must be >= 0"
                )
        elif dist == "lognormal":
            for k in ("mu", "sigma"):
                if k not in p:
                    raise ModelValidationError(
                        f"task '{task_name}' lognormal dist requires '{k}'"
                    )
            if p["sigma"] < 0:
                raise ModelValidationError(
                    f"task '{task_name}' lognormal sigma must be >= 0"
                )
        else:
            raise ModelValidationError(
                f"task '{task_name}' has unsupported dist '{dist}'"
            )

        for ev in task.emit:
            if ev not in model.events:
                raise ModelValidationError(
                    f"task '{task_name}' emits unknown event '{ev}' (must exist in events)"
                )

    for ev, listeners in model.wiring.items():
        if ev not in model.events:
            raise ModelValidationError(f"wiring references unknown event '{ev}'")
        for t in listeners:
            if t not in model.tasks:
                raise ModelValidationError(
                    f"wiring for event '{ev}' references unknown task '{t}'"
                )


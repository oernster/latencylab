from __future__ import annotations

import pytest

from latencylab.model import Model
from latencylab.validate import ModelValidationError, validate_model


def test_rejects_unknown_context() -> None:
    model = Model.from_json(
        {
            "version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "missing",
                    "duration_ms": {"dist": "fixed", "value": 1},
                    "emit": [],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    with pytest.raises(ModelValidationError):
        validate_model(model)


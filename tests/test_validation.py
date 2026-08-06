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


def test_missing_schema_version_is_a_friendly_error() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        Model.from_json(
            {
                "entry_event": "e0",
                "contexts": {"ui": {"concurrency": 1}},
                "events": {"e0": {"tags": ["ui"]}},
                "tasks": {
                    "t": {
                        "context": "ui",
                        "duration_ms": {"dist": "fixed", "value": 1},
                        "emit": [],
                    }
                },
                "wiring": {"e0": ["t"]},
            }
        )


@pytest.mark.parametrize("key", ["schema_version", "version", "model_version"])
def test_schema_version_aliases_are_accepted(key: str) -> None:
    model = Model.from_json(
        {
            key: 2,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {
                "t": {
                    "context": "ui",
                    "duration_ms": {"dist": "fixed", "value": 1},
                    "emit": [],
                }
            },
            "wiring": {"e0": ["t"]},
        }
    )
    assert model.version == 2


def test_shipped_example_models_are_valid() -> None:
    """Every example in `examples/` must load and validate.

    These are the files a new user opens first, so one that no longer parses is
    worse than no example at all. Reading the directory rather than naming the
    files means a new example is covered the moment it is added.
    """
    import json
    from pathlib import Path

    examples = sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.json"))
    assert examples, "examples/ is empty, so this test is checking nothing"

    for path in examples:
        model = Model.from_json(json.loads(path.read_text(encoding="utf-8")))
        validate_model(model)

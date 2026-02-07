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


def test_stellody_model_is_valid() -> None:
    import json
    from pathlib import Path

    model = Model.from_json(json.loads(Path("stellody_music_discovery.json").read_text()))
    validate_model(model)

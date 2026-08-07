from __future__ import annotations

import pytest

from PySide6.QtWidgets import QApplication

from latencylab_ui.model_composer_contexts_editor import ContextsEditor
from latencylab_ui.model_composer_tasks_editor import TasksEditor
from latencylab_ui.model_composer_types import (
    DEFAULT_VERSION,
    read_schema_version,
    wiring_edges_from_raw,
)


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------- model shapes


@pytest.mark.parametrize(
    "raw",
    [
        {"schema_version": 1},
        {"version": 1},
        {"model_version": 1},
    ],
)
def test_every_version_key_the_engine_accepts_can_be_opened(raw: dict) -> None:
    """A model that runs must be a model that can be edited.

    The engine takes three spellings of the version key, so the editor has to
    read all three or a valid model becomes uneditable for a reason the user
    cannot see.
    """

    assert read_schema_version(raw) == 1


def test_an_absent_version_falls_back_to_the_current_schema() -> None:
    assert read_schema_version({}) == DEFAULT_VERSION


def test_an_unreadable_version_falls_back_rather_than_raising() -> None:
    assert read_schema_version({"schema_version": "two"}) == DEFAULT_VERSION


def test_a_bare_string_listener_becomes_an_edge_with_no_delay() -> None:
    edges = wiring_edges_from_raw({"e": ["task_a"]})

    assert edges == {"e": [{"task": "task_a", "delay_ms": None}]}


def test_a_task_object_without_a_delay_is_the_same_edge_as_a_bare_string() -> None:
    """The two spellings mean one thing, so they must not read differently."""

    assert wiring_edges_from_raw({"e": [{"task": "a"}]}) == wiring_edges_from_raw(
        {"e": ["a"]}
    )


def test_a_numeric_delay_is_widened_to_the_distribution_it_means() -> None:
    """The parser expands the shorthand, so the editor shows the same thing."""

    edges = wiring_edges_from_raw({"e": [{"task": "a", "delay_ms": 150}]})

    assert edges["e"][0]["delay_ms"] == {"dist": "fixed", "value": 150.0}


def test_a_distribution_delay_is_carried_across_unchanged() -> None:
    dist = {"dist": "normal", "mean": 5.0, "std": 1.0}
    edges = wiring_edges_from_raw({"e": [{"task": "a", "delay_ms": dist}]})

    assert edges["e"][0]["delay_ms"] == dist


@pytest.mark.parametrize(
    "listener",
    [
        {"task": "  "},
        {"no_task_key": 1},
        42,
        None,
    ],
)
def test_a_listener_naming_no_task_is_dropped(listener: object) -> None:
    assert wiring_edges_from_raw({"e": [listener]}) == {"e": []}


def test_a_boolean_delay_is_not_read_as_a_number() -> None:
    """`True` is an int in Python, and a delay of one millisecond is not what
    a model saying `true` meant."""

    edges = wiring_edges_from_raw({"e": [{"task": "a", "delay_ms": True}]})

    assert edges["e"][0]["delay_ms"] is None


def test_wiring_that_is_not_a_mapping_yields_nothing() -> None:
    assert wiring_edges_from_raw(None) == {}
    assert wiring_edges_from_raw([1, 2]) == {}


# ------------------------------------------------------------------- editors


def test_contexts_are_replaced_and_ordered_by_name(app: QApplication) -> None:
    editor = ContextsEditor()

    editor.set_contexts(
        {"workers": {"concurrency": 4}, "db": {"concurrency": 1}, "ui": {}}
    )

    assert editor.context_names() == ["db", "ui", "workers"]
    assert editor.to_contexts_dict()["workers"]["concurrency"] == 4
    # The default row is not left behind on top of the loaded ones.
    assert editor.table.rowCount() == 3

    editor.deleteLater()


def test_loading_an_empty_context_set_leaves_the_default_row(
    app: QApplication,
) -> None:
    """An empty table cannot name a context, so a task card could select none."""

    editor = ContextsEditor()

    editor.set_contexts({})

    assert editor.context_names() == ["ui"]

    editor.deleteLater()


def test_tasks_are_rebuilt_from_a_model(app: QApplication) -> None:
    editor = TasksEditor()
    editor.set_context_names(["ui", "net"])
    editor.set_version(2)

    editor.set_tasks(
        {
            "b_task": {
                "context": "net",
                "duration_ms": {"dist": "fixed", "value": 7.0},
                "emit": ["done", "progress"],
                "meta": {"category": "third-party"},
            },
            "a_task": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 2.0},
                "emit": [],
            },
        }
    )

    assert editor.task_names() == ["a_task", "b_task"]

    round_tripped = editor.to_tasks_dict(version=2)
    assert round_tripped["b_task"]["context"] == "net"
    assert round_tripped["b_task"]["emit"] == ["done", "progress"]
    assert round_tripped["b_task"]["meta"]["category"] == "third-party"
    assert round_tripped["a_task"]["duration_ms"]["value"] == 2.0

    editor.deleteLater()


def test_loading_tasks_twice_replaces_rather_than_appends(app: QApplication) -> None:
    editor = TasksEditor()
    editor.set_context_names(["ui"])

    task = {"context": "ui", "duration_ms": {"dist": "fixed", "value": 1.0}}
    editor.set_tasks({"one": dict(task)})
    editor.set_tasks({"two": dict(task)})

    assert editor.task_names() == ["two"]

    editor.deleteLater()


def test_a_task_naming_an_unknown_context_does_not_invent_one(
    app: QApplication,
) -> None:
    """The combo offers what the contexts table has, and nothing else."""

    editor = TasksEditor()
    editor.set_context_names(["ui"])

    editor.set_tasks(
        {
            "t": {
                "context": "nowhere",
                "duration_ms": {"dist": "fixed", "value": 1.0},
            }
        }
    )

    assert editor.to_tasks_dict(version=2)["t"]["context"] == "ui"

    editor.deleteLater()


def test_a_task_without_a_duration_object_is_left_at_its_default(
    app: QApplication,
) -> None:
    editor = TasksEditor()
    editor.set_context_names(["ui"])

    editor.set_tasks({"t": {"context": "ui", "duration_ms": "nonsense"}})

    assert editor.to_tasks_dict(version=2)["t"]["duration_ms"]["dist"] == "fixed"

    editor.deleteLater()

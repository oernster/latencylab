from __future__ import annotations

import json
from pathlib import Path

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from latencylab_ui import main_window_actions as actions


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _Controller(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
    finished = Signal(int, float)

    def is_running(self) -> bool:
        return False

    def is_cancelled(self, run_token: int) -> bool:
        return False

    def active_token(self) -> int | None:
        return None

    def shutdown(self) -> None:
        return None


# ------------------------------------------------------------ the whole path


def _window(app: QApplication):
    from latencylab_ui.main_window import MainWindow

    window = MainWindow(run_controller=_Controller())
    # Shown, because a dock inside a hidden window never reports itself visible
    # and the point of these tests is whether the composer comes up.
    window.show()
    app.processEvents()
    return window


def test_editing_a_loaded_model_fills_the_composer_and_opens_it(
    app: QApplication,
) -> None:
    from latencylab_ui.example_models import find_examples_dir

    examples = find_examples_dir()
    assert examples is not None
    checkout = examples / "checkout.json"

    window = _window(app)
    window._load_model(checkout)

    assert window._edit_btn.isEnabled() is True
    assert window._edit_btn.toolTip() == actions.EDIT_READY

    window._on_edit_model_clicked()
    app.processEvents()

    dock = window._model_composer
    assert dock.isVisible() is True

    raw = json.loads(checkout.read_text(encoding="utf-8"))
    assert dock._system.get_version() == raw["schema_version"]
    assert dock._system.get_entry_event() == raw["entry_event"]
    assert dock._system.get_model_name() == "checkout"
    assert sorted(dock._contexts.to_contexts_dict()) == sorted(raw["contexts"])
    assert dock._tasks.task_names() == sorted(raw["tasks"])
    # The debounce on the promotions branch survives the round trip.
    edges = dock._wiring.get_wiring()["checkout.started"]
    delays = [e["delay_ms"] for e in edges if e["delay_ms"] is not None]
    assert delays == [{"dist": "fixed", "value": 150.0}]

    window.close()
    window.deleteLater()


def test_edit_is_inert_and_says_why_until_a_model_is_loaded(
    app: QApplication,
) -> None:
    window = _window(app)

    assert window._edit_btn.isEnabled() is False
    assert window._edit_btn.toolTip() == actions.EDIT_NEEDS_MODEL
    assert window._edit_action.isEnabled() is False

    # Triggering it anyway is silent rather than an error: the control is
    # disabled, so this can only be reached programmatically.
    window._on_edit_model_clicked()
    assert window._model_composer.isVisible() is False

    window.close()
    window.deleteLater()


def test_editing_an_already_open_composer_does_not_toggle_it_shut(
    app: QApplication,
) -> None:
    from latencylab_ui.example_models import find_examples_dir

    examples = find_examples_dir()
    assert examples is not None

    window = _window(app)
    window._load_model(examples / "checkout.json")
    window._on_toggle_model_composer_clicked()
    app.processEvents()
    assert window._model_composer.isVisible() is True

    window._on_edit_model_clicked()
    app.processEvents()

    assert window._model_composer.isVisible() is True

    window.close()
    window.deleteLater()


def test_opening_another_model_updates_an_open_editor(app: QApplication) -> None:
    """A view of a model that keeps showing the previous one is just wrong."""

    from latencylab_ui.example_models import find_examples_dir

    examples = find_examples_dir()
    assert examples is not None

    window = _window(app)
    window._load_model(examples / "checkout.json")
    window._on_edit_model_clicked()
    app.processEvents()
    assert window._model_composer._system.get_model_name() == "checkout"

    window._load_model(examples / "interactive.json")
    app.processEvents()

    dock = window._model_composer
    assert dock.isVisible() is True
    assert dock._system.get_model_name() == "interactive"

    raw = json.loads((examples / "interactive.json").read_text(encoding="utf-8"))
    assert dock._system.get_entry_event() == raw["entry_event"]
    assert dock._tasks.task_names() == sorted(raw["tasks"])

    window.close()
    window.deleteLater()


def test_a_composer_holding_typed_work_is_not_overwritten_by_a_load(
    app: QApplication,
) -> None:
    """Replacing what the user typed would be data loss, not a refresh."""

    from latencylab_ui.example_models import find_examples_dir

    examples = find_examples_dir()
    assert examples is not None

    window = _window(app)
    # Opened via Compose, so it holds authored state rather than a loaded model.
    window._on_toggle_model_composer_clicked()
    app.processEvents()
    dock = window._model_composer
    assert dock.isVisible() is True
    assert dock.is_showing_loaded_model() is False

    dock._system.set_values(model_name="mine", version=2, entry_event="typed.start")

    window._load_model(examples / "checkout.json")
    app.processEvents()

    assert dock._system.get_model_name() == "mine"
    assert dock._system.get_entry_event() == "typed.start"

    window.close()
    window.deleteLater()


def test_a_closed_editor_is_not_refreshed_behind_the_users_back(
    app: QApplication,
) -> None:
    """Nothing to keep in step, and Edit reloads from disk when next pressed."""

    from latencylab_ui.example_models import find_examples_dir

    examples = find_examples_dir()
    assert examples is not None

    window = _window(app)
    window._load_model(examples / "checkout.json")
    window._on_edit_model_clicked()
    app.processEvents()

    # Closed the way a dialog is closed, rather than by pressing Compose again:
    # that used to toggle a dock and now only ever opens.
    window._model_composer.reject()
    app.processEvents()
    assert window._model_composer.isVisible() is False

    window._load_model(examples / "interactive.json")
    app.processEvents()
    assert window._model_composer._system.get_model_name() == "checkout"

    # Reopening via Edit shows the model that is actually loaded.
    window._on_edit_model_clicked()
    app.processEvents()
    assert window._model_composer._system.get_model_name() == "interactive"

    window.close()
    window.deleteLater()


def test_editing_a_v1_model_hides_the_v2_only_field(
    app: QApplication, tmp_path: Path
) -> None:
    model = {
        "version": 1,
        "entry_event": "start",
        "events": {"start": {"tags": ["ui"]}},
        "contexts": {"ui": {"concurrency": 1}},
        "tasks": {
            "t": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 1.0},
                "emit": [],
            }
        },
        "wiring": {"start": ["t"]},
    }
    path = tmp_path / "v1.json"
    path.write_text(json.dumps(model), encoding="utf-8")

    window = _window(app)
    window._load_model(path)
    window._on_edit_model_clicked()
    app.processEvents()

    assert window._model_composer._system.get_version() == 1

    window.close()
    window.deleteLater()

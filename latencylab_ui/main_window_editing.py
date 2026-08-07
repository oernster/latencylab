from __future__ import annotations

"""Opening the loaded model in the composer, and keeping it in step.

Composing and editing are the same surface reached from two ends, so there is
no second dock here: editing is the compose action with the loaded model put
into the editors first. This lives beside the window for the same reason the
dock switching does, which is that the window is at its size limit and this is
one cohesive job with a rule worth stating.
"""

import json

from latencylab_ui.main_window_dock_switching import toggle_or_switch_to_model_composer


def open_loaded_model_for_editing(window) -> None:
    """Show the composer, filled with the model that is already loaded.

    Silent when nothing is loaded. The control that reaches this is disabled
    and wearing a red ring that says why, so there is nothing left to tell.
    """

    if not load_into_composer(window):
        return
    if not window._model_composer_dock.isVisible():  # noqa: SLF001
        toggle_or_switch_to_model_composer(window)


def load_into_composer(window) -> bool:
    """Put the loaded model into the composer; False when there is none.

    Read from disk rather than from the parsed model the window is holding,
    because the composer edits the FILE's shape: the version key it used, the
    listener spellings it chose, the fields the parser filled in defaults for.
    Round-tripping through the parsed form would quietly rewrite the document.
    """

    loaded = window._loaded_model  # noqa: SLF001
    if loaded is None:
        return False

    raw = json.loads(loaded.path.read_text(encoding="utf-8"))
    window._model_composer_dock.load_raw_model(  # noqa: SLF001
        raw, model_name=loaded.path.stem
    )
    return True


def refresh_open_editor(window) -> None:
    """Keep an open editor in step with the model that was just opened.

    An editor showing a model is a view of that model, and a view that keeps
    displaying the previous one after another file is opened is simply wrong.

    It follows only while it is BOTH open and showing a loaded model. A
    composer holding something typed from scratch is the user's own work, and
    replacing that would be data loss rather than a refresh.
    """

    dock = window._model_composer_dock  # noqa: SLF001
    if dock.isVisible() and dock.is_showing_loaded_model():
        load_into_composer(window)

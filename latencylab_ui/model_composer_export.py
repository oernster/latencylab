from __future__ import annotations

"""Getting a composed model back out of the composer.

Writing a model out is the mirror of `model_composer_load` reading one in, and
it is kept beside the dock for the same reason: the dock is at its size limit,
and this is one cohesive job (validate, ask where, write deterministically,
optionally hand it to the main window) rather than part of building the UI.

Every path validates first and refuses rather than writing a model the engine
would reject. A file on disk that cannot be run is worse than no file: it looks
like work that was saved.
"""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from latencylab_ui.model_composer_types import (
    build_raw_model_dict,
    build_stress_variant_state,
    dumps_deterministic,
)
from latencylab_ui.user_paths import default_dialog_dir

STRESS_SUFFIX = "_STRESS"
MODEL_SUFFIX = ".json"


def default_export_dir(dock) -> Path:
    """Where a save dialog should open.

    Beside the model being edited when there is one, because that is where its
    siblings live and where an edited copy belongs. Otherwise Downloads, which
    is where the rest of the application's dialogs start.
    """

    loaded = getattr(dock.parent(), "_loaded_model", None)
    path = getattr(loaded, "path", None)
    if path is not None:
        return Path(path).parent

    directory = default_dialog_dir()
    return Path(directory) if directory else Path(".").resolve()


def prompt_save_path(dock, *, default_filename: str) -> Path | None:
    """Ask where to write, and insist on the extension the engine reads."""

    start_dir = default_export_dir(dock)
    chosen, _ = QFileDialog.getSaveFileName(
        dock,
        "Save model JSON",
        str(start_dir / default_filename),
        "JSON files (*.json);;All files (*)",
    )
    if not chosen:
        return None

    out = Path(chosen)
    if out.suffix.lower() != MODEL_SUFFIX:
        out = out.with_suffix(MODEL_SUFFIX)
    return out


def _write(dock, path: Path, raw: dict) -> bool:
    try:
        path.write_text(dumps_deterministic(raw), encoding="utf-8")
    except OSError as error:
        QMessageBox.critical(dock, "Export failed", str(error))
        return False
    return True


def export_model(dock, *, load_after: bool) -> None:
    """Write the composed model, and optionally open what was just written."""

    if not dock.validate_now(show_dialog=True):
        return

    dock.sync_from_ui()
    state = dock.state
    raw = build_raw_model_dict(state)

    path = prompt_save_path(dock, default_filename=f"{state.model_name}{MODEL_SUFFIX}")
    if path is None:
        return
    if not _write(dock, path, raw):
        return

    if load_after:
        load_into_main_ui(dock, path)


def export_stress_variant(dock, *, multiplier: float) -> None:
    """Write a heavier version of the composed model, then open it.

    Always loaded afterwards, unlike a plain export: a stress variant exists to
    be run against the model it came from, and a copy nobody opened answers
    nothing.
    """

    if not dock.validate_now(show_dialog=True):
        return

    dock.sync_from_ui()
    state = dock.state

    try:
        stress = build_stress_variant_state(state, multiplier=multiplier)
        raw = build_raw_model_dict(stress)
    except (ValueError, TypeError, KeyError) as error:
        QMessageBox.critical(dock, "Stress generation failed", str(error))
        return

    path = prompt_save_path(
        dock, default_filename=f"{state.model_name}{STRESS_SUFFIX}{MODEL_SUFFIX}"
    )
    if path is None:
        return
    if not _write(dock, path, raw):
        return

    load_into_main_ui(dock, path)


def load_into_main_ui(dock, path: Path) -> None:
    """Hand a written model to the window, as if it had been opened."""

    window = dock.parent()
    loader = getattr(window, "_load_model", None)
    if loader is None:
        return
    try:
        loader(path)
    except (OSError, RuntimeError) as error:
        # RuntimeError belongs here as much as OSError does: the window's own
        # loader reports its failures itself, so what reaches this is a dead
        # C++ object, which is exactly what PySide raises RuntimeError for.
        QMessageBox.critical(dock, "Load failed", str(error))

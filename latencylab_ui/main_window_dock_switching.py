from __future__ import annotations

"""MainWindow dock switching helpers.

This module exists to keep `main_window.py` small (see codebase size guardrails)
and to isolate UI policies around mutually-exclusive docks.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


def toggle_or_switch_to_model_composer(window) -> None:
    """Handle the Compose Model button click.

    Policy:
    - If the Model Composer dock is visible *and* Distributions is not, then this
      behaves as a toggle-off (hide composer).
    - Otherwise, this behaves as a "switch to compose" action:
        - Optionally prompt to export if there are unexported outputs.
        - Hide Distributions.
        - Ensure the composer dock is shown, raised, and sized sanely.
    """

    composer_visible = window._model_composer_dock.isVisible()  # noqa: SLF001
    dist_visible = window._distributions_dock.isVisible()  # noqa: SLF001

    if composer_visible and not dist_visible:
        window._model_composer_dock.hide()  # noqa: SLF001
        return

    try:
        _prompt_export_if_needed(window)
    except _UserCancelledCompose:
        return

    if window._distributions_dock.isVisible():  # noqa: SLF001
        window._distributions_dock.hide()  # noqa: SLF001

    if not window._model_composer_dock.isVisible():  # noqa: SLF001
        window._model_composer_dock.show()  # noqa: SLF001
    window._model_composer_dock.raise_()  # noqa: SLF001

    _ensure_composer_sane_size(window)


def _prompt_export_if_needed(window) -> None:
    # Early-return branches are kept deliberately simple and are covered by unit
    # tests in `tests/test_ui_main_window_dock_switching_coverage.py`.
    if not getattr(window, "_have_unexported_outputs", False):
        return
    if getattr(window, "_last_outputs", None) is None:
        return

    res = QMessageBox.question(
        window,
        "Export runs?",
        "You have unexported run results. Export runs before composing a model?",
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Yes,
    )

    if res == QMessageBox.StandardButton.Cancel:
        # Use an exception-free early exit that the caller can interpret by
        # leaving the UI unchanged.
        raise _UserCancelledCompose

    if res == QMessageBox.StandardButton.Yes:
        window._on_save_log_clicked()  # noqa: SLF001
        if getattr(window, "_have_unexported_outputs", False):
            # Export was cancelled/failed.
            raise _UserCancelledCompose


def _ensure_composer_sane_size(window) -> None:
    dock = window._model_composer_dock  # noqa: SLF001

    # Avoid becoming effectively invisible due to a previous split/collapse.
    min_w = max(420, int(dock.minimumWidth()))
    min_h = max(600, int(dock.minimumHeight()))

    window.resizeDocks([dock], [min_w], Qt.Orientation.Horizontal)
    window.resizeDocks([dock], [min_h], Qt.Orientation.Vertical)


class _UserCancelledCompose(Exception):
    """Internal control-flow signal used to abort compose switching."""


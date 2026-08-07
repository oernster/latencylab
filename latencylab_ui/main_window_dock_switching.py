from __future__ import annotations

"""MainWindow panel policies.

This module exists to keep `main_window.py` small (see codebase size guardrails)
and to isolate the rules about which panel is showing.
"""

from PySide6.QtWidgets import QMessageBox


def open_model_composer(window) -> None:
    """Handle the Compose Model button click.

    Policy:
    - Optionally prompt to export if there are unexported outputs.
    - Open the composer, modal, over the whole window.

    There is no toggle-off case any more and no dock to hide. The composer used
    to share the right-hand area with Distributions, so opening one was a
    question about the other; a modal dialog answers that question by covering
    the window while it is up and giving it straight back when it closes.

    The export prompt stays, because it was never about the layout: it asks
    whether to keep results that are about to stop being the thing on screen.
    """

    try:
        _prompt_export_if_needed(window)
    except _UserCancelledCompose:
        return

    # Shown rather than exec'd. Both are modal, because the dialog says it is;
    # the difference is that `exec` also starts a nested event loop and does not
    # return until the dialog closes, which turns opening a panel into a call
    # that never comes back. Nothing here has anything to do after the composer
    # opens, so the loop would buy nothing and cost the caller its stack.
    composer = window._model_composer  # noqa: SLF001
    composer.show()
    composer.raise_()
    composer.activateWindow()


def toggle_distributions(window) -> None:
    """Handle the Distributions button click: show it, or put it away.

    Deliberately NOT the mirror of compose. Compose has a switch-to policy
    because it is going somewhere, away from results that may not have been
    exported. This one is only saying whether a panel is up, so it leaves the
    composer alone: the two are allowed to be up together, which is the case
    `toggle_or_switch_to_model_composer` reads as "switch" rather than "off".

    A plain toggle rather than an opener, because a control that only ever
    opens leaves the dock's own close cross as the only way to undo one press.
    """

    if window._distributions_dock.isVisible():  # noqa: SLF001
        window._distributions_dock.hide()  # noqa: SLF001
        return

    window._show_distributions_dock()  # noqa: SLF001


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


class _UserCancelledCompose(Exception):
    """Internal control-flow signal used to abort compose switching."""

from __future__ import annotations

"""The run lifecycle: what the window does as a run starts, ends or is stopped.

Split out of the window when the cancellation work pushed that file past the
size cap. It is one concern and reads as one: each function here handles one
thing the controller says, in the order it says them.

Free functions taking the window, matching main_window_file_io beside it, so
the window stays a thing that is BUILT and these stay things that HAPPEN to it.
"""

import time

from PySide6.QtWidgets import QMessageBox

from latencylab_ui import main_window_actions as actions
from latencylab_ui.run_controller import RunOutputs

RUNNING_STATUS = "Running…"
COMPLETED_STATUS = "Completed"
FAILED_STATUS = "Failed"
FAILED_TITLE = "Simulation failed"

# What the elapsed label reads the moment a run begins, before the first tick.
INITIAL_ELAPSED = "0.0s"


def _was_cancelled(window, run_token: int) -> bool:
    """Whether this run is one the user stopped.

    Two sources because they answer at different moments: the controller knows
    which tokens were cancelled, and the window knows that Cancel was pressed
    for the run it is currently watching.
    """

    return window._controller.is_cancelled(run_token) or window._active_cancelled


def on_run_started(window, run_token: int) -> None:
    window._active_run_token = run_token
    window._dist_dock_closed_during_run = False
    window._auto_open_distributions_on_finish = False
    window._set_running(True)
    window._status_label.setText(RUNNING_STATUS)
    window._elapsed_started_at = time.monotonic()
    window._elapsed_label.setText(INITIAL_ELAPSED)
    window._elapsed_timer.start()


def on_run_succeeded(window, run_token: int, outputs_obj: object) -> None:
    if _was_cancelled(window, run_token):
        # A cancelled run produces no outputs at all: the simulator refuses to
        # return a partial set rather than hand back aggregates that describe a
        # system nobody asked about.
        return

    if isinstance(outputs_obj, RunOutputs):
        window._last_outputs = outputs_obj
        window._have_unexported_outputs = True
        window._outputs_view.render(outputs_obj)
        window._run_select.setEnabled(True)

        # Refreshed against the controller's ACTUAL state, which is still
        # running at this point: `succeeded` arrives before `finished`. Claiming
        # otherwise here is what previously let the export button arm mid-run
        # while the distributions button correctly did not.
        window._refresh_actions()

        # Render distributions from the same deterministic outputs.
        window._distributions_dock.render(outputs_obj)

    window._status_label.setText(COMPLETED_STATUS)

    # Auto-open exactly once per successful completion, unless the user closed
    # the dock during the run. The open waits for `finished`, so the window is
    # no longer in its running state by the time it happens.
    window._auto_open_distributions_on_finish = not window._dist_dock_closed_during_run


def on_run_failed(window, run_token: int, error_text: str) -> None:
    if _was_cancelled(window, run_token):
        window._status_label.setText(actions.CANCELLED_STATUS)
        return

    window._status_label.setText(FAILED_STATUS)
    QMessageBox.critical(window, FAILED_TITLE, error_text)
    window._auto_open_distributions_on_finish = False
    window._refresh_actions()


def on_run_finished(window, run_token: int, elapsed_seconds: float) -> None:
    window._elapsed_timer.stop()
    window._elapsed_label.setText(f"{elapsed_seconds:0.2f}s")
    window._elapsed_started_at = None
    window._set_running(False)

    if _was_cancelled(window, run_token):
        # The `cancelled` signal has already said how far the run got, and it
        # knows the exact count; leave its message alone rather than replacing
        # it with a vaguer one.
        window._auto_open_distributions_on_finish = False
        return

    if window._auto_open_distributions_on_finish and window._last_outputs is not None:
        window._auto_open_distributions_on_finish = False
        window._show_distributions_dock()

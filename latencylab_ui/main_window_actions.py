from __future__ import annotations

"""What is available to do, and why it is not.

Every "can the user press this" rule in the main window lives here, as one pure
function over three facts. It is separated from the window for the same reason
the installer separates its decisions from its side effects: the rules are worth
testing on their own, and scattered across half a dozen `setEnabled` calls they
could not be read as a set.

The reasons live here too. A disabled control paints a permanent red ring, which
says "present but inert" without saying why, so every control that can be inert
carries a tooltip explaining what would make it live. That tooltip and the rule
that disables it are the same fact, so they are written in the same place.
"""

from dataclasses import dataclass

RUN_READY = "Run the simulation"
RUN_NEEDS_MODEL = "Open a model first"
RUN_IN_PROGRESS = "A run is already in progress"

CANCEL_READY = "Stop the run"
CANCEL_IDLE = "Nothing is running"

# Cancel now genuinely stops the work, at the boundary between one run and the
# next, so the copy says "stopping" rather than the old "results will be
# discarded when it finishes".
CANCELLING_STATUS = "Stopping at the end of the run in progress…"
CANCELLED_STATUS = "Cancelled"

SAVE_READY = "Export runs as zip…"
SAVE_NEEDS_OUTPUTS = "Run a simulation first, then the runs can be exported"

DISTRIBUTIONS_READY = "Show latency and critical-path distributions"
DISTRIBUTIONS_NEEDS_OUTPUTS = (
    "Run a simulation first, then its distributions appear here"
)


@dataclass(frozen=True, slots=True)
class ActionAvailability:
    """Which of the window's actions can be taken right now."""

    run: bool
    cancel: bool
    inputs: bool
    save_log: bool
    distributions: bool


def availability(
    *, running: bool, model_loaded: bool, have_outputs: bool
) -> ActionAvailability:
    """Decide what is available from the only three facts that matter.

    Run is gated on a loaded model rather than being pressable and then
    complaining. A button that can always be pressed and sometimes answers with
    a dialog teaches the user nothing until they have already been interrupted;
    a button that is visibly inert until a model is open answers the question
    before it is asked.
    """

    return ActionAvailability(
        run=model_loaded and not running,
        cancel=running,
        inputs=not running,
        # Post-run inspection: only once there is something to inspect, and
        # never while a fresh run is replacing it.
        save_log=have_outputs and not running,
        distributions=have_outputs and not running,
    )


def run_tooltip(*, running: bool, model_loaded: bool) -> str:
    if running:
        return RUN_IN_PROGRESS
    return RUN_READY if model_loaded else RUN_NEEDS_MODEL


def cancel_tooltip(*, running: bool) -> str:
    return CANCEL_READY if running else CANCEL_IDLE


def save_tooltip(*, available: bool) -> str:
    return SAVE_READY if available else SAVE_NEEDS_OUTPUTS


def distributions_tooltip(*, available: bool) -> str:
    return DISTRIBUTIONS_READY if available else DISTRIBUTIONS_NEEDS_OUTPUTS


def cancelled_status(completed_runs: int) -> str:
    """What a cancelled run reports.

    The count is exact rather than approximate, because the stop happens at a
    run boundary: it tells the user whether Cancel caught the run early or
    almost at the end, which is the only thing they can act on.
    """

    if completed_runs == 1:
        return f"{CANCELLED_STATUS} after 1 run"
    return f"{CANCELLED_STATUS} after {completed_runs} runs"

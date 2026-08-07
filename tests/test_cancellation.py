from __future__ import annotations

import pytest

from latencylab.cancellation import RunCancelled, should_stop
from latencylab.model import Model
from latencylab.sim import simulate_many

MANY_RUNS = 50
STOP_AFTER = 7

MODEL_JSON = {
    "schema_version": 2,
    "entry_event": "e0",
    "contexts": {"ui": {"concurrency": 1}},
    "events": {"e0": {"tags": ["ui"]}},
    "tasks": {},
}


class _StopAfter:
    """Says stop once it has been ASKED a given number of times.

    Counting the asks is what proves the check happens once per run rather than
    once per event or once per call: the count and the completed-run count have
    to agree.
    """

    def __init__(self, after: int) -> None:
        self._after = after
        self.asked = 0

    def is_cancelled(self) -> bool:
        self.asked += 1
        return self.asked > self._after


class _NeverCancels:
    def is_cancelled(self) -> bool:
        return False


class _RecordingFlag:
    """Stands in for the CancelFlag so the controller's use of it is visible."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


@pytest.fixture()
def qapp_window():
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.main_window import MainWindow

    class _IdleController(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        cancelled = Signal(int, int)
        finished = Signal(int, float)

        def is_running(self) -> bool:
            return False

        def is_cancelled(self, run_token: int) -> bool:
            return False

        def shutdown(self) -> None:
            return None

    app = QApplication.instance() or QApplication([])
    window = MainWindow(run_controller=_IdleController())
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def _model() -> Model:
    return Model.from_json(MODEL_JSON)


def test_no_signal_never_reads_as_cancelled() -> None:
    """The absence of a signal must not be mistaken for a request to stop."""

    assert should_stop(None) is False
    assert should_stop(_NeverCancels()) is False


def test_a_run_set_completes_untouched_when_nothing_asks_it_to_stop() -> None:
    runs, _trace = simulate_many(
        model=_model(),
        runs=MANY_RUNS,
        seed=1,
        max_tasks_per_run=1000,
        want_trace=False,
    )
    assert len(runs) == MANY_RUNS


def test_cancelling_stops_the_work_rather_than_letting_it_finish() -> None:
    """The point of the whole change: the runs after the stop never happen."""

    signal = _StopAfter(STOP_AFTER)

    with pytest.raises(RunCancelled) as raised:
        simulate_many(
            model=_model(),
            runs=MANY_RUNS,
            seed=1,
            max_tasks_per_run=1000,
            want_trace=False,
            cancel=signal,
        )

    assert raised.value.completed_runs == STOP_AFTER
    assert signal.asked == STOP_AFTER + 1, "asked once per run, and only once"


def test_a_cancelled_run_returns_nothing_at_all() -> None:
    """Not a shorter list of runs: an exception.

    Aggregating a partial set would produce percentiles that look exactly like
    real ones while describing a system nobody asked about. Refusing to return
    anything is what makes that impossible rather than merely discouraged.
    """

    with pytest.raises(RunCancelled):
        simulate_many(
            model=_model(),
            runs=MANY_RUNS,
            seed=1,
            max_tasks_per_run=1000,
            want_trace=False,
            cancel=_StopAfter(1),
        )


def test_cancelling_before_the_first_run_stops_immediately() -> None:
    with pytest.raises(RunCancelled) as raised:
        simulate_many(
            model=_model(),
            runs=MANY_RUNS,
            seed=1,
            max_tasks_per_run=1000,
            want_trace=False,
            cancel=_StopAfter(0),
        )
    assert raised.value.completed_runs == 0


def test_the_message_says_how_far_it_got() -> None:
    assert "3" in str(RunCancelled(completed_runs=3))


def test_the_legacy_executor_stops_at_the_same_boundary() -> None:
    """Schema version 1 routes to the NumPy executor, which is separate code."""

    pytest.importorskip("numpy")

    legacy = Model.from_json({**MODEL_JSON, "schema_version": 1})
    signal = _StopAfter(STOP_AFTER)

    with pytest.raises(RunCancelled) as raised:
        simulate_many(
            model=legacy,
            runs=MANY_RUNS,
            seed=1,
            max_tasks_per_run=1000,
            want_trace=False,
            cancel=signal,
        )
    assert raised.value.completed_runs == STOP_AFTER


def test_the_cancelled_status_counts_runs_and_gets_the_grammar_right() -> None:
    """It is the only number the user can act on, so it is worth saying well."""

    from latencylab_ui import main_window_actions as actions

    assert actions.cancelled_status(1) == "Cancelled after 1 run"
    assert actions.cancelled_status(0) == "Cancelled after 0 runs"
    assert actions.cancelled_status(42) == "Cancelled after 42 runs"


def test_the_window_reports_how_far_a_cancelled_run_got(qapp_window) -> None:
    from latencylab_ui import main_window_actions as actions

    window = qapp_window
    window._auto_open_distributions_on_finish = True

    window._on_run_cancelled(run_token=1, completed_runs=12)

    assert window._status_label.text() == actions.cancelled_status(12)
    assert window._auto_open_distributions_on_finish is False


def test_cancelling_an_active_run_sets_the_flag_the_worker_reads() -> None:
    """Marking the token is not enough on its own: the flag is what stops it."""

    from latencylab_ui.run_controller import RunController

    controller = RunController()
    assert controller.cancel_active() is None, "no active run: nothing to do"

    flag = _RecordingFlag()
    controller._active_token = 5
    controller._cancel_flag = flag

    controller.cancel_active()

    assert controller.is_cancelled(5) is True
    assert flag.cancelled is True


def test_a_worker_that_is_cancelled_reports_it_as_its_own_outcome(
    tmp_path,
) -> None:
    """Not a failure: a traceback in a message box is not the answer to a
    button press the user made on purpose.
    """

    import json

    import latencylab_ui.run_controller as rc

    model_path = tmp_path / "m.json"
    model_path.write_text(json.dumps(MODEL_JSON), encoding="utf-8")

    seen: dict[str, object] = {}
    worker = rc.RunWorker(
        run_token=3,
        request=rc.RunRequest(model_path=model_path, runs=MANY_RUNS, seed=1),
        cancel=_StopAfter(2),
    )
    worker.cancelled.connect(
        lambda token, done: seen.update(token=token, completed=done)
    )
    worker.failed.connect(lambda *_a: seen.update(failed=True))
    worker.run()

    assert seen == {"token": 3, "completed": 2}


def test_the_cancel_flag_crosses_the_thread_boundary() -> None:
    """Set on the interface thread, read on the worker thread."""

    from latencylab_ui.run_controller import CancelFlag

    flag = CancelFlag()
    assert flag.is_cancelled() is False

    results: list[bool] = []

    def _read() -> None:
        results.append(flag.is_cancelled())

    import threading

    flag.cancel()
    worker = threading.Thread(target=_read)
    worker.start()
    worker.join()

    assert results == [True]

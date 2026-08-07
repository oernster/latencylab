from __future__ import annotations

import json
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from latencylab.cancellation import RunCancelled
from latencylab.metrics import add_task_metadata, aggregate_runs
from latencylab.model import Model
from latencylab.sim import simulate_many
from latencylab.types import RunResult
from latencylab.validate import ModelValidationError, validate_model


@dataclass(frozen=True)
class RunRequest:
    model_path: Path
    runs: int
    seed: int
    max_tasks_per_run: int = 200_000
    want_trace: bool = False


@dataclass(frozen=True)
class RunOutputs:
    model: Model
    runs: list[RunResult]
    summary: dict[str, Any]


class CancelFlag:
    """The cancellation signal, shared across the thread boundary.

    A `threading.Event` rather than a plain bool: it is set on the interface
    thread and read on the worker thread, and an Event is the primitive that
    makes that safe without a lock at either end.
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


class RunWorker(QObject):
    succeeded = Signal(int, object)  # (run_token, RunOutputs)
    failed = Signal(int, str)  # (run_token, error_text)
    cancelled = Signal(int, int)  # (run_token, completed_runs)
    finished = Signal(int)  # (run_token)

    def __init__(
        self, *, run_token: int, request: RunRequest, cancel: CancelFlag
    ) -> None:
        super().__init__()
        self._run_token = run_token
        self._request = request
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            raw = json.loads(self._request.model_path.read_text(encoding="utf-8"))
            model = Model.from_json(raw)
            validate_model(model)

            runs, _trace = simulate_many(
                model=model,
                runs=int(self._request.runs),
                seed=int(self._request.seed),
                max_tasks_per_run=int(self._request.max_tasks_per_run),
                want_trace=bool(self._request.want_trace),
                cancel=self._cancel,
            )

            summary = aggregate_runs(model=model, runs=runs)
            summary = add_task_metadata(summary, model=model)

            self.succeeded.emit(
                self._run_token, RunOutputs(model=model, runs=runs, summary=summary)
            )
        except RunCancelled as cancelled:
            # Its own signal, not a failure: the user asked for this, and a
            # traceback in a message box is not the answer to a button press.
            self.cancelled.emit(self._run_token, cancelled.completed_runs)
        except ModelValidationError as e:
            self.failed.emit(self._run_token, str(e))
        except Exception:  # noqa: BLE001 - show traceback for unexpected failures
            self.failed.emit(self._run_token, traceback.format_exc())
        finally:
            self.finished.emit(self._run_token)


class RunController(QObject):
    """Owns the background-run lifecycle.

    Cancellation genuinely stops the work. The simulator is CPU-bound and
    cannot be interrupted from outside, so it is ASKED to stop, at the boundary
    between one run and the next. The worst case is therefore one run's worth of
    delay, and no run is ever left half simulated.
    """

    started = Signal(int)  # run_token
    succeeded = Signal(int, object)  # (run_token, RunOutputs)
    failed = Signal(int, str)  # (run_token, error_text)
    cancelled = Signal(int, int)  # (run_token, completed_runs)
    finished = Signal(int, float)  # (run_token, elapsed_seconds)

    def __init__(self) -> None:
        super().__init__()
        self._next_token = 1
        self._active_token: int | None = None
        self._cancelled_tokens: set[int] = set()
        self._cancel_flag: CancelFlag | None = None

        # Keep strong references to QThread/QObject wrappers until the thread has
        # actually finished. Dropping the last Python ref before the underlying
        # thread stops can trigger:
        #   QThread: Destroyed while thread '' is still running
        self._thread: QThread | None = None
        self._worker: RunWorker | None = None
        self._started_at: float | None = None

    def is_running(self) -> bool:
        return self._active_token is not None

    def is_cancelled(self, run_token: int) -> bool:
        return run_token in self._cancelled_tokens

    def active_token(self) -> int | None:
        return self._active_token

    def start(self, request: RunRequest) -> int:
        if self._thread is not None:
            raise RuntimeError("Run already active")

        run_token = self._next_token
        self._next_token += 1
        self._active_token = run_token
        self._started_at = time.monotonic()

        cancel_flag = CancelFlag()
        thread = QThread()
        worker = RunWorker(run_token=run_token, request=request, cancel=cancel_flag)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.succeeded.connect(self.succeeded)
        worker.failed.connect(self.failed)
        worker.cancelled.connect(self.cancelled)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._cancel_flag = cancel_flag

        self.started.emit(run_token)
        thread.start()
        return run_token

    def cancel_active(self) -> None:
        """Ask the active run to stop at the next run boundary."""

        if self._active_token is None:
            return
        self._cancelled_tokens.add(self._active_token)
        if self._cancel_flag is not None:
            self._cancel_flag.cancel()

    @Slot()
    def shutdown(self) -> None:
        """Stop any active run, then wait for its thread to end.

        The wait is still here and still necessary, because the thread has to
        have actually stopped before its wrapper is dropped or Qt warns that a
        running thread was destroyed. What has changed is how long it waits:
        the run now stops at the next boundary rather than running to
        completion, so closing the window mid-run no longer blocks on the whole
        remaining run set.
        """

        if self._thread is None:
            return

        self.cancel_active()

        try:
            self._thread.wait()
        except RuntimeError:
            # Can happen during interpreter teardown.
            pass

    @Slot(int)
    def _on_worker_finished(self, run_token: int) -> None:
        elapsed = 0.0
        if self._started_at is not None:
            elapsed = max(0.0, time.monotonic() - self._started_at)

        # Important: don't clear thread/worker references here. The worker emits
        # `finished` before the QThread has fully stopped. We clear refs in
        # `_on_thread_finished` to avoid premature GC of the wrappers.
        self.finished.emit(run_token, elapsed)

    @Slot()
    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._active_token = None
        self._started_at = None
        self._cancel_flag = None

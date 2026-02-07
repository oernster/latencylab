from __future__ import annotations

import json
from pathlib import Path

import pytest


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_model(tmp_path: Path, *, concurrency: int = 1) -> Path:
    raw = {
        "schema_version": 1,
        "entry_event": "e0",
        "contexts": {"ui": {"concurrency": concurrency}},
        "events": {"e0": {"tags": ["ui"]}},
        "tasks": {},
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


def test_run_worker_success_and_error_paths(monkeypatch, tmp_path: Path) -> None:
    _ensure_qapp()

    import latencylab_ui.run_controller as rc
    from latencylab.validate import ModelValidationError

    req = rc.RunRequest(model_path=_write_model(tmp_path), runs=1, seed=1)

    # Success path.
    monkeypatch.setattr(rc, "simulate_many", lambda **_k: ([], None))
    monkeypatch.setattr(rc, "aggregate_runs", lambda **_k: {"ok": True})
    monkeypatch.setattr(rc, "add_task_metadata", lambda summary, **_k: summary)

    w = rc.RunWorker(run_token=7, request=req)
    seen = {"succeeded": False, "failed": False, "finished": False}
    w.succeeded.connect(lambda tok, obj: seen.__setitem__("succeeded", tok == 7 and obj is not None))
    w.failed.connect(lambda *_a: seen.__setitem__("failed", True))
    w.finished.connect(lambda tok: seen.__setitem__("finished", tok == 7))
    w.run()
    assert seen == {"succeeded": True, "failed": False, "finished": True}

    # Validation error path.
    monkeypatch.setattr(
        rc,
        "validate_model",
        lambda _m: (_ for _ in ()).throw(ModelValidationError("bad")),
    )
    w2 = rc.RunWorker(run_token=8, request=req)
    out2 = {"failed": False, "finished": False}
    w2.failed.connect(lambda tok, txt: out2.__setitem__("failed", tok == 8 and "bad" in txt))
    w2.finished.connect(lambda tok: out2.__setitem__("finished", tok == 8))
    w2.run()
    assert out2 == {"failed": True, "finished": True}

    # Unexpected exception path.
    monkeypatch.setattr(rc, "validate_model", lambda _m: None)
    monkeypatch.setattr(
        rc,
        "simulate_many",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    w3 = rc.RunWorker(run_token=9, request=req)
    out3 = {"failed": False, "finished": False}
    w3.failed.connect(
        lambda tok, txt: out3.__setitem__("failed", tok == 9 and "RuntimeError" in txt)
    )
    w3.finished.connect(lambda tok: out3.__setitem__("finished", tok == 9))
    w3.run()
    assert out3 == {"failed": True, "finished": True}


def test_run_controller_lifecycle_paths(monkeypatch, tmp_path: Path) -> None:
    _ensure_qapp()
    import latencylab_ui.run_controller as rc

    req = rc.RunRequest(model_path=_write_model(tmp_path), runs=1, seed=1)

    # Start: thread/worker are faked so we can deterministically cover signal wiring.
    class _Sig:
        def __init__(self) -> None:
            self._subs: list[object] = []

        def connect(self, fn) -> None:
            self._subs.append(fn)

        def emit(self, *a):
            for fn in list(self._subs):
                if hasattr(fn, "emit"):
                    fn.emit(*a)
                else:
                    try:
                        fn(*a)
                    except TypeError:
                        # Some callbacks (e.g. thread.quit) take no positional args.
                        fn()

    class _FakeThread:
        def __init__(self) -> None:
            self.started = _Sig()
            self.finished = _Sig()

        def start(self) -> None:
            self.started.emit()

        def quit(self, *_a) -> None:
            self.finished.emit()

        def wait(self) -> None:
            return None

        def deleteLater(self) -> None:  # noqa: N802
            return None

    class _FakeWorker:
        def __init__(self, *, run_token: int, request) -> None:
            self.succeeded = _Sig()
            self.failed = _Sig()
            self.finished = _Sig()
            self._run_token = run_token

        def moveToThread(self, _t) -> None:  # noqa: N802
            return None

        def run(self) -> None:
            # Match expected signal signatures.
            self.succeeded.emit(self._run_token, object())
            self.finished.emit(self._run_token)

        def deleteLater(self) -> None:  # noqa: N802
            return None

    monkeypatch.setattr(rc, "QThread", _FakeThread)
    monkeypatch.setattr(rc, "RunWorker", _FakeWorker)

    c = rc.RunController()

    tok = c.start(req)
    assert tok == 1
    assert c.active_token() is None
    assert not c.is_running()

    # Start again: should work because the fake thread finished.
    tok2 = c.start(req)
    assert tok2 == 2

    # start(): already active -> raises.
    c._thread = object()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="Run already active"):
        c.start(req)
    c._thread = None

    # Cancel.
    c._active_token = None
    c.cancel_active()
    c._active_token = 42
    c.cancel_active()
    assert c.is_cancelled(42)

    # Shutdown: no thread.
    c._thread = None
    c.shutdown()

    # Shutdown: wait raises RuntimeError branch.
    class _BadThread(_FakeThread):
        def wait(self) -> None:
            raise RuntimeError("teardown")

    c._thread = _BadThread()
    c._active_token = 99
    c.shutdown()

    # _on_worker_finished with started_at unset.
    c._started_at = None
    c._on_worker_finished(123)

    # _on_thread_finished clears internal refs.
    c._on_thread_finished()
    assert c.active_token() is None


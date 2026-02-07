from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import runpy

import pytest


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _minimal_v2_model() -> dict:
    return {
        "schema_version": 2,
        "entry_event": "e0",
        "contexts": {"ui": {"concurrency": 1}},
        "events": {"e0": {"tags": ["ui"]}, "ui.done": {"tags": ["ui"]}},
        "tasks": {
            "t": {
                "context": "ui",
                "duration_ms": {"dist": "fixed", "value": 1.0},
                "emit": ["ui.done"],
            }
        },
        "wiring": {"e0": ["t"]},
    }


def test_cli_simulate_writes_summary_runs_and_trace(tmp_path: Path) -> None:
    from latencylab.cli import main

    model_path = tmp_path / "m.json"
    _write_json(model_path, _minimal_v2_model())

    out_summary = tmp_path / "summary.json"
    out_runs = tmp_path / "runs.csv"
    out_trace = tmp_path / "trace.csv"

    rc = main(
        [
            "simulate",
            "--model",
            str(model_path),
            "--runs",
            "2",
            "--seed",
            "123",
            "--out-summary",
            str(out_summary),
            "--out-runs",
            str(out_runs),
            "--out-trace",
            str(out_trace),
        ]
    )
    assert rc == 0
    assert out_summary.exists()
    assert out_runs.exists()
    assert out_trace.exists()


def test_cli_unhandled_command_raises_assertion(monkeypatch: pytest.MonkeyPatch) -> None:
    import latencylab.cli

    class _DummyParser:
        def parse_args(self, _argv: list[str] | None) -> object:
            return SimpleNamespace(cmd="nope")

    monkeypatch.setattr(latencylab.cli, "_build_parser", lambda: _DummyParser())
    with pytest.raises(AssertionError, match="Unhandled command"):
        latencylab.cli.main(["anything"])


def test_python_m_latencylab_executes_main(tmp_path: Path) -> None:
    model_path = tmp_path / "m.json"
    _write_json(model_path, _minimal_v2_model())

    out_summary = tmp_path / "summary.json"
    out_runs = tmp_path / "runs.csv"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "latencylab",
            "simulate",
            "--model",
            str(model_path),
            "--runs",
            "1",
            "--seed",
            "1",
            "--out-summary",
            str(out_summary),
            "--out-runs",
            str(out_runs),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_summary.exists()
    assert out_runs.exists()


def test___main___module_runs_inprocess_and_exits_zero(tmp_path: Path) -> None:
    model_path = tmp_path / "m.json"
    _write_json(model_path, _minimal_v2_model())

    out_summary = tmp_path / "summary.json"
    out_runs = tmp_path / "runs.csv"

    old_argv = sys.argv[:]
    try:
        sys.argv = [
            "python -m latencylab",
            "simulate",
            "--model",
            str(model_path),
            "--runs",
            "1",
            "--seed",
            "1",
            "--out-summary",
            str(out_summary),
            "--out-runs",
            str(out_runs),
        ]
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("latencylab.__main__", run_name="__main__")
        assert exc.value.code == 0
    finally:
        sys.argv = old_argv

    assert out_summary.exists()
    assert out_runs.exists()


def test_io_writers_roundtrip(tmp_path: Path) -> None:
    from latencylab.io import write_runs_csv, write_summary_json, write_trace_csv
    from latencylab.types import RunResult, TaskInstance

    out_summary = tmp_path / "out" / "summary.json"
    out_runs = tmp_path / "out" / "runs.csv"
    out_trace = tmp_path / "out" / "trace.csv"

    summary = {"hello": "world"}
    write_summary_json(out_summary, summary)
    assert json.loads(out_summary.read_text(encoding="utf-8")) == summary

    runs = [
        RunResult(
            run_id=0,
            first_ui_event_time_ms=0.0,
            last_ui_event_time_ms=1.0,
            makespan_ms=1.0,
            critical_path_ms=1.0,
            critical_path_tasks="t",
            failed=False,
            failure_reason=None,
        )
    ]
    write_runs_csv(out_runs, runs)
    txt = out_runs.read_text(encoding="utf-8")
    assert "run_id" in txt and "critical_path_tasks" in txt

    trace = [
        TaskInstance(
            instance_id=1,
            run_id=0,
            task_name="t",
            context="ui",
            enqueue_time_ms=0.0,
            start_time_ms=0.0,
            end_time_ms=1.0,
            queue_wait_ms=0.0,
            duration_ms=1.0,
            emitted_events=("e1", "e2"),
            parent_task_instance_id=None,
            capacity_parent_instance_id=None,
        )
    ]
    write_trace_csv(out_trace, trace)
    txt = out_trace.read_text(encoding="utf-8")
    assert "e1;e2" in txt


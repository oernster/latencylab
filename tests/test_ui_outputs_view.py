from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_outputs_view_render_and_switch() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QComboBox, QPlainTextEdit

    from latencylab.model import Model
    from latencylab.types import RunResult
    from latencylab_ui.outputs_view import OutputsView
    from latencylab_ui.run_controller import RunOutputs

    summary = QPlainTextEdit()
    run_select = QComboBox()
    crit = QPlainTextEdit()

    view = OutputsView(
        summary_text=summary,
        run_select=run_select,
        critical_path_text=crit,
    )

    model = Model.from_json(
        {
            "schema_version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {},
        }
    )

    outputs = RunOutputs(
        model=model,
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=1.0,
                critical_path_ms=1.0,
                critical_path_tasks="t0 -> t1",
                failed=False,
                failure_reason=None,
            ),
            RunResult(
                run_id=1,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=2.0,
                critical_path_ms=2.0,
                critical_path_tasks="",
                failed=True,
                failure_reason="boom",
            ),
        ],
        summary={
            "runs_requested": 2,
            "runs_ok": 1,
            "runs_failed": 1,
            "latency_ms": {
                "first_ui": {"p50": 1, "p90": 2, "p95": 3, "p99": 4},
                "last_ui": {"p50": 5, "p90": 6, "p95": 7, "p99": 8},
                "makespan": {"p50": 9, "p90": 10, "p95": 11, "p99": 12},
            },
            "critical_path": {"top_paths": [{"tasks": "t0 -> t1", "count": 1}]},
        },
    )

    view.render(outputs)
    assert "Runs requested" in summary.toPlainText()
    assert run_select.count() == 2

    view.on_run_selected(0)
    assert crit.toPlainText() == "t0 -> t1"

    view.on_run_selected(1)
    assert crit.toPlainText() == "(no critical path)"

    view.on_run_selected(-1)
    assert crit.toPlainText() == "(no critical path)"

    view.on_run_selected(999)
    assert crit.toPlainText() == "(no critical path)"


def test_outputs_view_formats_critical_path_for_display() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QComboBox, QPlainTextEdit

    from latencylab.model import Model
    from latencylab.types import RunResult
    from latencylab_ui.outputs_view import OutputsView
    from latencylab_ui.run_controller import RunOutputs

    summary = QPlainTextEdit()
    run_select = QComboBox()
    crit = QPlainTextEdit()

    view = OutputsView(
        summary_text=summary,
        run_select=run_select,
        critical_path_text=crit,
    )

    model = Model.from_json(
        {
            "schema_version": 1,
            "entry_event": "e0",
            "contexts": {"ui": {"concurrency": 1}},
            "events": {"e0": {"tags": ["ui"]}},
            "tasks": {},
        }
    )

    outputs = RunOutputs(
        model=model,
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=1.0,
                critical_path_ms=1.0,
                critical_path_tasks="a>b,c) d",
                failed=False,
                failure_reason=None,
            )
        ],
        summary={
            "runs_requested": 1,
            "runs_ok": 1,
            "runs_failed": 0,
            "latency_ms": {"makespan": {"p50": 1, "p90": 1, "p95": 1, "p99": 1}},
            "critical_path": {"top_paths": []},
        },
    )

    view.render(outputs)
    view.on_run_selected(0)

    assert crit.toPlainText() == "a>\nb,\nc)\nd"

    # Ensure we do not split the common arrow token "->".
    outputs2 = RunOutputs(
        model=model,
        runs=[
            RunResult(
                run_id=0,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=1.0,
                critical_path_ms=1.0,
                critical_path_tasks="t0 -> t1",
                failed=False,
                failure_reason=None,
            )
        ],
        summary={
            "runs_requested": 1,
            "runs_ok": 1,
            "runs_failed": 0,
            "latency_ms": {"makespan": {"p50": 1, "p90": 1, "p95": 1, "p99": 1}},
            "critical_path": {"top_paths": []},
        },
    )
    view.render(outputs2)
    view.on_run_selected(0)
    assert crit.toPlainText() == "t0 -> t1"


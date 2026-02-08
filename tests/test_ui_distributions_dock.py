from __future__ import annotations

import time


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _spin(app, *, seconds: float = 0.05) -> None:
    """Let Qt process paint/update events deterministically."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_distributions_dock_renders_and_paints_with_data() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab.model import Model
    from latencylab.types import RunResult
    from latencylab_ui.distributions_dock import DistributionsDock
    from latencylab_ui.run_controller import RunOutputs

    host = QMainWindow()
    dock = DistributionsDock(host)
    host.addDockWidget(dock.allowedAreas(), dock)

    model = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )

    # Create enough distinct paths to force the "Other (long tail)" bucket.
    # Also include long tokens so wrapping/eliding paths remains stable.
    runs: list[RunResult] = [
        RunResult(
            run_id=0,
            first_ui_event_time_ms=None,
            last_ui_event_time_ms=None,
            makespan_ms=10.0,
            critical_path_ms=10.0,
            critical_path_tasks="A>B>C",
            failed=False,
            failure_reason=None,
        ),
        RunResult(
            run_id=1,
            first_ui_event_time_ms=None,
            last_ui_event_time_ms=None,
            makespan_ms=20.0,
            critical_path_ms=20.0,
            critical_path_tasks="A>B>C",
            failed=False,
            failure_reason=None,
        ),
    ]
    for i in range(20):
        runs.append(
            RunResult(
                run_id=2 + i,
                first_ui_event_time_ms=None,
                last_ui_event_time_ms=None,
                makespan_ms=30.0,
                critical_path_ms=30.0,
                critical_path_tasks=f"ui.handle_click>bg.fetch_recommendations>delay(bg.super_long_segment_{i:02d})",
                failed=False,
                failure_reason=None,
            )
        )

    outputs = RunOutputs(
        model=model,
        runs=runs,
        summary={
            "latency_ms": {
                "makespan": {"p50": 20.0, "p90": 30.0, "p95": 30.0, "p99": 30.0}
            }
        },
    )

    host.resize(900, 600)
    host.show()
    _spin(app)

    dock.render(outputs)
    dock.show()
    _spin(app)

    # List renders, and hovering any row should expose full path via tooltips.
    assert dock._cp_list._rows  # noqa: SLF001
    tip = dock._cp_list._rows[0].toolTip() or ""  # noqa: SLF001
    assert "A>B>C" in tip

    # Long-tail bucket exists and uses the special readability format.
    tips = [r.toolTip() or "" for r in dock._cp_list._rows]  # noqa: SLF001
    assert any("Other (long tail):" in t for t in tips)

    # Other (long tail) is only shown when there are > TopN distinct paths; this
    # fixture has only 2.

    host.close()
    _spin(app)


def test_distributions_dock_renders_and_paints_empty() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab.model import Model
    from latencylab_ui.distributions_dock import DistributionsDock
    from latencylab_ui.run_controller import RunOutputs

    host = QMainWindow()
    dock = DistributionsDock(host)
    host.addDockWidget(dock.allowedAreas(), dock)

    model = Model(
        version=2,
        entry_event="start",
        contexts={},
        events={},
        tasks={},
        wiring={},
        wiring_edges={},
    )

    host.resize(700, 500)
    host.show()
    _spin(app)

    dock.render(RunOutputs(model=model, runs=[], summary={}))
    dock.show()
    _spin(app)

    host.close()
    _spin(app)


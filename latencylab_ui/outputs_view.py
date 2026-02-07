from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QComboBox, QPlainTextEdit

from latencylab_ui.run_controller import RunOutputs


@dataclass(frozen=True)
class _RunItem:
    run_id: int
    failed: bool
    critical_path_tasks: str


class OutputsView:
    """Binds simulation outputs to the right-panel widgets."""

    def __init__(
        self,
        *,
        summary_text: QPlainTextEdit,
        run_select: QComboBox,
        critical_path_text: QPlainTextEdit,
    ) -> None:
        self._summary_text = summary_text
        self._run_select = run_select
        self._critical_path_text = critical_path_text
        self._runs: list[_RunItem] = []

    def render(self, outputs: RunOutputs) -> None:
        self._summary_text.setPlainText(format_summary_text(outputs))

        self._runs = [
            _RunItem(
                run_id=r.run_id,
                failed=r.failed,
                critical_path_tasks=r.critical_path_tasks,
            )
            for r in outputs.runs
        ]

        self._run_select.blockSignals(True)
        self._run_select.clear()
        for r in self._runs:
            status = "failed" if r.failed else "ok"
            self._run_select.addItem(f"Run {r.run_id} ({status})", r.run_id)
        self._run_select.blockSignals(False)

        if self._runs:
            self._run_select.setCurrentIndex(0)
            self.show_run_critical_path(0)

    def on_run_selected(self, idx: int) -> None:
        if idx < 0:
            return
        self.show_run_critical_path(idx)

    def show_run_critical_path(self, idx: int) -> None:
        if idx >= len(self._runs):
            return

        r = self._runs[idx]
        if r.critical_path_tasks:
            self._critical_path_text.setPlainText(r.critical_path_tasks)
        else:
            self._critical_path_text.setPlainText("(no critical path)")


def format_summary_text(outputs: RunOutputs) -> str:
    """Format the right-panel summary as plain text.

    Kept Qt-free so it can also be reused by export code.
    """

    s = outputs.summary
    lines: list[str] = [
        f"Model schema_version: {outputs.model.version}",
        f"Runs requested: {s.get('runs_requested')}",
        f"Runs ok: {s.get('runs_ok')}  failed: {s.get('runs_failed')}",
    ]

    lat = s.get("latency_ms", {})
    for key in ("first_ui", "last_ui", "makespan"):
        p = lat.get(key, {})
        lines.append(
            f"{key}: p50={p.get('p50')}, p90={p.get('p90')}, p95={p.get('p95')}, p99={p.get('p99')}"
        )

    crit = s.get("critical_path", {})
    top = crit.get("top_paths", [])
    lines.append("")
    lines.append("Top critical paths:")
    for item in top:
        tasks = item.get("tasks")
        count = item.get("count")
        lines.append(f"- ({count}) {tasks}")

    return "\n".join(lines)


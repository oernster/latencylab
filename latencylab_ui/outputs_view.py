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
            self._critical_path_text.setPlainText(_format_critical_path_for_display(r.critical_path_tasks))
        else:
            self._critical_path_text.setPlainText("(no critical path)")


def _format_critical_path_for_display(text: str) -> str:
    """Format a critical-path string for readability in a narrow text box.

    Deterministic, v1 UI-only behavior:
    - Insert line breaks after: '>', ',', ')'
    - Collapse accidental whitespace around inserted breaks

    The underlying model/run output remains unchanged (tooltips/exports still use
    the original strings).
    """

    # Insert breaks deterministically. We avoid splitting the common arrow token
    # "->" because it reads better on a single line.
    chars = list(text)
    out_parts: list[str] = []
    for i, ch in enumerate(chars):
        out_parts.append(ch)
        if ch == ">":
            # Don't break inside "->".
            if i > 0 and chars[i - 1] == "-":
                continue
            out_parts.append("\n")
        elif ch in (",", ")"):
            out_parts.append("\n")

    out = "".join(out_parts)

    # Normalize whitespace around newlines deterministically.
    lines = [ln.strip() for ln in out.splitlines()]
    # Preserve intentional blank lines (unlikely in critical paths, but safe).
    return "\n".join(lines)


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


from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


HOW_TO_READ_TEXT = """How to Read LatencyLab Output

LatencyLab does not tell you what is slow.
It tells you why the user waited.

LatencyLab exists to make latency behavior visible before code hardens and before intuition becomes political. It does this by running explicit models many times and showing how often different outcomes occur. The goal is not prediction. The goal is understanding.

Real systems are stochastic. Contention, scheduling, cache state, coordination delays, and external dependencies are not “noise” that can be averaged away. They are the system. Multiple runs exist because a single run is not representative of user experience.

Users do not experience averages. Averages hide risk. Percentiles describe experience and exposure: p50 reflects what typically happens, while p90, p95, and p99 describe how often the system behaves badly. The shape of the distribution matters more than any single percentile. If you are arguing about whether p90 or p95 matters more, you are already past the point where this tool helps.

The makespan distribution shows how long end-to-end work takes across many runs. It should be read as a shape, not a target. Percentile markers annotate the distribution; they are not goals to optimise toward. Lowering one percentile without understanding the shape usually shifts cost elsewhere.

A critical path is not “what was slow”. It is the chain of work that prevented progress in a single run. If work is not on the critical path, it did not delay the user in that run, regardless of how expensive or visible it appears in isolation. Expensive work that does not block progress is often irrelevant to perceived latency.

Some critical paths appear repeatedly. These are dominant paths: critical paths that occur in a significant fraction of runs, typically more than twenty percent. Dominant paths represent behavioral modes: recurring coordination patterns that describe how the system usually behaves. They are not bugs by default. They are structure.

Rare critical paths form a long tail. The long tail usually does not influence typical user experience and can be ignored unless you are designing for strict worst-case guarantees. Fixing long-tail behavior often has no effect on how the system feels to users.

A representative run is a single run chosen to illustrate a behavioral mode, commonly the median or p95 run within that mode. Representative runs exist to make dominant behavior concrete, not to explain every outcome.

Do not read every run. Name dominant behaviors before proposing fixes. If a task never appears on a dominant path, it does not matter. Optimising rare worst cases often makes systems more complex without making them feel faster.

LatencyLab does not optimise systems.
It exposes structure.
"""


class HowToReadDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("How to Read LatencyLab Output")

        # Human-readable default size; still resizable by the user.
        # Width: 9/10 of the previously requested 3/4-width setting (675px).
        self.resize(608, 700)

        # Non-modal: documentation should not block inspection.
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        text = QPlainTextEdit(self)
        text.setReadOnly(True)
        text.setPlainText(HOW_TO_READ_TEXT)
        root.addWidget(text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


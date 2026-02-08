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

1) Why multiple runs exist
Real systems are stochastic.
Contention, scheduling, cache state, and external dependencies are not “noise.”
They are the system.

2) Why percentiles matter more than averages
Users do not experience averages.
Percentiles show typical experience (p50) and risk (p90/p95/p99).

3) What a critical path represents
The critical path is the chain of work that determines end-to-end latency in a run.
If work is not on the critical path, it did not delay the user in that run.

4) Dominant paths, behavioral modes, and the long tail
Dominant Path:
  A critical path that appears in a significant fraction of runs (typically >20%).

Behavioral Mode:
  A distinct dominant path representing a recurring coordination pattern in the system.
  Example modes:
    - Mode A: recommendations-first
    - Mode B: playlist-build-first

Long Tail:
  Rare critical paths that occur infrequently and do not materially affect typical user experience.

Representative Run:
  A single run selected to illustrate a behavioral mode (usually median or p95 within that mode).

5) Guidance
- Do not read every run.
- Name dominant behaviors before proposing fixes.
- If a task is never on a dominant path, it does not matter.
- Fixing rare worst cases often does nothing for perceived latency.
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


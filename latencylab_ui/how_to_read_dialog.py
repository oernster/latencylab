from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.auto_scroller import attach
from latencylab_ui.first_stop_dialog import FirstStopDialog

HOW_TO_READ_TEXT = """How to Read LatencyLab Output

LatencyLab does not tell you what is slow.
It tells you why the user waited.

LatencyLab exists to make latency behavior visible before code hardens and before intuition becomes political. It does this by running explicit models many times and showing how often different outcomes occur. The goal is not prediction. The goal is understanding.

The screen, element by element.

The histogram is the makespan distribution: each bar counts runs by how long the whole flow took. Read the shape. A tight cluster means predictable latency; a long right tail means some runs go badly; two humps mean the system has two distinct behavioural modes, which is a structural fact worth explaining before you optimise anything.

The percentiles, p50 through p99, annotate that shape. p50 is the typical experience; p99 is what 1 in 100 users hits. They describe exposure, not targets to game.

The critical path is the named chain of tasks, queue waits and delays that set the finish time of a run. Read it left to right as "this is literally why the user waited". Critical does not mean slow: a fast task on the path matters and a slow task off it does not.

The critical-path frequency chart counts how often each distinct chain was the bottleneck across all runs. A path dominating, say more than a fifth of runs, is how your design behaves rather than a fluke: that is the thing to design against. This chart is the tool's real answer; the histogram is context for it.

A worked example, using the shipped Checkout model. A click fires user.checkout_clicked, a UI task handles it and emits checkout.started, which fans out to four backend tasks at once. Two of them, db.load_cart and db.load_saved_cards, share a database context with concurrency 1, so one always queues behind the other. A fixed 150 ms delay sits on the wiring to net.fetch_promotions: a debounce, added for politeness. Intuition says the slowest backend, the shipping quote, dominates. The frequency chart says the chain through the debounce and the totals render is the critical path in most runs. A politeness feature owns the median latency; no profiler could have told you that before the system existed. That is the kind of finding this tool exists to produce.

What follows is why the output is shaped this way.

Real systems are stochastic. Contention, scheduling, cache state, coordination delays and external dependencies are not “noise” that can be averaged away. They are the system. Multiple runs exist because a single run is not representative of user experience.

Users do not experience averages. Averages hide risk. Percentiles describe experience and exposure: p50 reflects what typically happens, while p90, p95 and p99 describe how often the system behaves badly. The shape of the distribution matters more than any single percentile. If you are arguing about whether p90 or p95 matters more, you are already past the point where this tool helps.

The makespan distribution shows how long end-to-end work takes across many runs. It should be read as a shape, not a target. Percentile markers annotate the distribution; they are not goals to optimise toward. Lowering one percentile without understanding the shape usually shifts cost elsewhere.

A critical path is not “what was slow”. It is the chain of work that prevented progress in a single run. If work is not on the critical path, it did not delay the user in that run, regardless of how expensive or visible it appears in isolation. Expensive work that does not block progress is often irrelevant to perceived latency.

Some critical paths appear repeatedly. These are dominant paths: critical paths that occur in a significant fraction of runs, typically more than twenty percent. Dominant paths represent behavioral modes: recurring coordination patterns that describe how the system usually behaves. They are not bugs by default. They are structure.

Rare critical paths form a long tail. The long tail usually does not influence typical user experience and can be ignored unless you are designing for strict worst-case guarantees. Fixing long-tail behavior often has no effect on how the system feels to users.

A representative run is a single run chosen to illustrate a behavioral mode, commonly the median or p95 run within that mode. Representative runs exist to make dominant behavior concrete, not to explain every outcome.

Do not read every run. Name dominant behaviors before proposing fixes. If a task never appears on a dominant path, it does not matter. Optimising rare worst cases often makes systems more complex without making them feel faster.

LatencyLab does not optimise systems.
It exposes structure.
"""


class HowToReadDialog(FirstStopDialog):
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

        text = QTextBrowser(self)
        text.setReadOnly(True)
        text.setPlainText(HOW_TO_READ_TEXT)
        root.addWidget(text, 1)
        attach(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

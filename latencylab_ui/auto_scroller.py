from __future__ import annotations

"""Content that reads itself, gently.

A long licence or a page of guidance holds still for a moment when it opens,
then descends slowly, holds at the end, rewinds fast and repeats. The reader can
take over at any moment; the cycle suspends and picks up again from wherever
they left it, never from the top and never switched off for good.

The constants below are the application's, not each surface's. A per-dialog pace
was tried elsewhere in this portfolio and immediately standardised away: if one
surface needs a different speed, the speed is wrong everywhere.
"""

from enum import Enum, auto

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QWidget

TICK_MS = 40

# Still on open, so the reader can orient before anything moves.
START_HOLD_MS = 5000

# One pixel every SECOND tick. The first cut of this read too fast for many
# readers, so the pace is halved by counting ticks rather than by lengthening
# the timer, which would coarsen every wait in the cycle with it.
DESCENT_PX = 1
TICKS_PER_DESCENT = 2

# Long enough to finish reading the tail before the rewind takes it away.
BOTTOM_HOLD_MS = 5000

# A reposition, not a reading pass, so it travels fast.
REWIND_PX = 15

TOP_HOLD_MS = 2000

# Stillness required after a manual scroll before the cycle picks up again.
MANUAL_RESUME_MS = 2500


class Phase(Enum):
    DOWN = auto()
    PAUSE_BOTTOM = auto()
    UP = auto()
    PAUSE_TOP = auto()
    MANUAL = auto()


class AutoScroller(QObject):
    """Drives one scrollable surface through the reading cycle."""

    def __init__(self, area: QAbstractScrollArea) -> None:
        super().__init__(area)
        self._area = area
        # Seeded as a top hold carrying the start hold, which is what makes a
        # freshly opened surface sit still before its first descent.
        self._phase = Phase.PAUSE_TOP
        self._wait_ms = START_HOLD_MS
        self._ticks_to_step = TICKS_PER_DESCENT

        area.viewport().installEventFilter(self)
        area.installEventFilter(self)

        bar = area.verticalScrollBar()
        bar.sliderPressed.connect(self._suspend)
        bar.sliderReleased.connect(self._suspend)
        bar.sliderMoved.connect(lambda _value: self._suspend())

        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TICK_MS)

    # ------------------------------------------------------------- suspension

    def _suspend(self) -> None:
        """Hand the surface to the reader, for a while.

        Never a disable: taking over by hand must not switch the feature off for
        the rest of the surface's life.
        """

        self._phase = Phase.MANUAL
        self._wait_ms = MANUAL_RESUME_MS

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if event.type() in (
            event.Type.Wheel,
            event.Type.MouseButtonPress,
            event.Type.KeyPress,
        ):
            self._suspend()
        return super().eventFilter(watched, event)

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Focus arriving anywhere inside counts as reading by hand.

        A child taking focus never sees the surface's own event filter, so the
        application-wide signal plus an ancestry test is the only way to catch
        it. This is also what stops the cycle fighting keyboard navigation.
        """

        if new is not None and (new is self._area or self._area.isAncestorOf(new)):
            self._suspend()

    # ------------------------------------------------------------------ ticks

    def _is_frozen(self) -> bool:
        """Whether a modal above this surface owns the screen.

        Two surfaces reading at once compete for the eye, so anything beneath a
        modal is FROZEN rather than suspended: the tick returns before consuming
        any wait, so phase, position and remaining hold are all exactly where
        they were when the modal closes.
        """

        modal = QApplication.activeModalWidget()
        if modal is None:
            return False
        return not (modal is self._area.window() or modal.isAncestorOf(self._area))

    def _tick(self) -> None:
        bar = self._area.verticalScrollBar()
        if bar is None or bar.maximum() == 0:
            # Nothing overflows, so there is nothing to read. Attaching this to a
            # surface that happens to fit is free rather than wrong.
            return
        if self._is_frozen():
            return

        if self._wait_ms > 0:
            self._wait_ms -= TICK_MS
            if self._wait_ms > 0:
                return
            self._phase = self._phase_after_wait(bar)
            return

        if self._phase == Phase.DOWN:
            self._descend(bar)
        elif self._phase == Phase.UP:
            self._rewind(bar)

    def _phase_after_wait(self, bar) -> Phase:
        """Where the cycle goes once a hold runs out.

        After a manual pause with the bar already at the bottom the only way on
        is to rewind; otherwise the reader is carried on downwards from exactly
        where they stopped.
        """

        if self._phase == Phase.PAUSE_BOTTOM:
            return Phase.UP
        if self._phase == Phase.MANUAL and bar.value() >= bar.maximum():
            return Phase.UP
        return Phase.DOWN

    def _descend(self, bar) -> None:
        self._ticks_to_step -= 1
        if self._ticks_to_step > 0:
            return
        self._ticks_to_step = TICKS_PER_DESCENT

        if bar.value() >= bar.maximum():
            self._phase = Phase.PAUSE_BOTTOM
            self._wait_ms = BOTTOM_HOLD_MS
            return
        bar.setValue(bar.value() + DESCENT_PX)

    def _rewind(self, bar) -> None:
        if bar.value() <= bar.minimum():
            self._phase = Phase.PAUSE_TOP
            self._wait_ms = TOP_HOLD_MS
            return
        bar.setValue(bar.value() - REWIND_PX)


def attach(area: QAbstractScrollArea) -> AutoScroller:
    """Give a surface the reading cycle.

    The surface is the scroller's Qt parent, so the scroller lives and dies with
    it and no caller has to hold a reference to keep it alive.
    """

    return AutoScroller(area)

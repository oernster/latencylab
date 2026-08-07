from __future__ import annotations

import pytest

from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QWidget

from latencylab_ui import auto_scroller
from latencylab_ui.auto_scroller import AutoScroller, Phase, attach

# Enough text that the pane must overflow whatever the offscreen metrics are.
LONG_TEXT = "\n".join(f"line {n}" for n in range(400))

PANE_W = 200
PANE_H = 80


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def pane(app: QApplication) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setPlainText(LONG_TEXT)
    widget.resize(PANE_W, PANE_H)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def _run_ticks(scroller: AutoScroller, count: int) -> None:
    """Drive the cycle by hand.

    Real time is never waited on: a five-second hold would be five seconds of
    test, and a test that sleeps is a test nobody runs.
    """

    for _ in range(count):
        scroller._tick()


def _ticks_for(milliseconds: int) -> int:
    return milliseconds // auto_scroller.TICK_MS


def test_a_fresh_surface_holds_still_before_it_reads(pane, app) -> None:
    """The reader orients before anything moves."""

    scroller = attach(pane)
    bar = pane.verticalScrollBar()
    assert bar.maximum() > 0, "the pane must overflow for any of this to apply"

    _run_ticks(scroller, _ticks_for(auto_scroller.START_HOLD_MS) - 1)
    assert bar.value() == 0
    assert scroller._phase is Phase.PAUSE_TOP

    _run_ticks(scroller, 2)
    assert scroller._phase is Phase.DOWN


def test_the_descent_is_half_pace_and_the_rewind_is_not(pane, app) -> None:
    """Reading and repositioning are different jobs at different speeds."""

    scroller = attach(pane)
    bar = pane.verticalScrollBar()

    _run_ticks(scroller, _ticks_for(auto_scroller.START_HOLD_MS) + 1)
    assert scroller._phase is Phase.DOWN

    start = bar.value()
    _run_ticks(scroller, 20)
    descended = bar.value() - start
    assert descended == 20 // auto_scroller.TICKS_PER_DESCENT

    # The rewind covers far more ground per tick than the descent does. Started
    # from the bottom so the step has room: from ten pixels down it would clamp
    # at zero and measure the clamp rather than the pace.
    scroller._phase = Phase.UP
    bar.setValue(bar.maximum())
    before = bar.value()
    _run_ticks(scroller, 1)
    assert before - bar.value() == auto_scroller.REWIND_PX
    assert auto_scroller.REWIND_PX > auto_scroller.DESCENT_PX


def test_the_cycle_turns_round_at_both_ends(pane, app) -> None:
    scroller = attach(pane)
    bar = pane.verticalScrollBar()

    scroller._phase = Phase.DOWN
    scroller._wait_ms = 0
    bar.setValue(bar.maximum())
    _run_ticks(scroller, auto_scroller.TICKS_PER_DESCENT)
    assert scroller._phase is Phase.PAUSE_BOTTOM

    _run_ticks(scroller, _ticks_for(auto_scroller.BOTTOM_HOLD_MS) + 1)
    assert scroller._phase is Phase.UP

    bar.setValue(bar.minimum())
    _run_ticks(scroller, 1)
    assert scroller._phase is Phase.PAUSE_TOP

    _run_ticks(scroller, _ticks_for(auto_scroller.TOP_HOLD_MS) + 1)
    assert scroller._phase is Phase.DOWN


def test_reading_by_hand_suspends_and_then_resumes_in_place(pane, app) -> None:
    """Taking over must never switch the feature off, nor rewind to the top."""

    scroller = attach(pane)
    bar = pane.verticalScrollBar()

    scroller._phase = Phase.DOWN
    scroller._wait_ms = 0
    bar.setValue(50)

    scroller._suspend()
    assert scroller._phase is Phase.MANUAL

    held = bar.value()
    _run_ticks(scroller, _ticks_for(auto_scroller.MANUAL_RESUME_MS) - 1)
    assert bar.value() == held, "nothing moves while the reader has it"

    _run_ticks(scroller, 2)
    assert scroller._phase is Phase.DOWN
    assert bar.value() == held, "and it carries on from there, not from the top"


def test_a_manual_pause_at_the_very_bottom_rewinds(pane, app) -> None:
    """Continuing downwards is not available, so the only way on is back."""

    scroller = attach(pane)
    bar = pane.verticalScrollBar()

    bar.setValue(bar.maximum())
    scroller._suspend()
    _run_ticks(scroller, _ticks_for(auto_scroller.MANUAL_RESUME_MS) + 1)

    assert scroller._phase is Phase.UP


def test_focus_arriving_anywhere_inside_counts_as_reading_by_hand(pane, app) -> None:
    """Otherwise the cycle fights the keyboard the moment someone tabs in."""

    scroller = attach(pane)
    scroller._phase = Phase.DOWN
    scroller._wait_ms = 0

    scroller._on_focus_changed(None, pane)
    assert scroller._phase is Phase.MANUAL

    scroller._phase = Phase.DOWN
    scroller._on_focus_changed(None, None)
    assert scroller._phase is Phase.DOWN

    scroller._on_focus_changed(None, QWidget())
    assert scroller._phase is Phase.DOWN, "an unrelated widget is not our business"


def test_a_wheel_or_a_keypress_on_the_surface_suspends_it(pane, app) -> None:
    """The filter watches the viewport AND the widget, because they see
    different halves of it: the viewport gets the wheel and the clicks, the
    widget gets the keys.
    """

    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QWheelEvent

    scroller = attach(pane)

    scroller._phase = Phase.DOWN
    wheel = QWheelEvent(
        QPointF(0, 0),
        QPointF(0, 0),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    scroller.eventFilter(pane.viewport(), wheel)
    assert scroller._phase is Phase.MANUAL

    scroller._phase = Phase.DOWN
    key = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier
    )
    scroller.eventFilter(pane, key)
    assert scroller._phase is Phase.MANUAL

    # Anything else passes straight through and leaves the cycle alone.
    scroller._phase = Phase.DOWN
    scroller.eventFilter(pane, QEvent(QEvent.Type.Show))
    assert scroller._phase is Phase.DOWN


def test_a_surface_that_fits_costs_nothing(app) -> None:
    """Attaching to a pane with nothing to scroll is free rather than wrong."""

    short = QPlainTextEdit()
    short.setPlainText("one line")
    short.resize(400, 400)
    short.show()
    app.processEvents()

    scroller = attach(short)
    assert short.verticalScrollBar().maximum() == 0

    _run_ticks(scroller, _ticks_for(auto_scroller.START_HOLD_MS) * 2)
    assert scroller._phase is Phase.PAUSE_TOP, "the hold was never even consumed"
    assert short.verticalScrollBar().value() == 0

    short.close()


def test_a_modal_above_the_surface_freezes_it_rather_than_suspending_it(
    pane, app
) -> None:
    """Frozen, not suspended: the hold that was running must still be running.

    Two surfaces reading at once compete for the eye, so whatever sits beneath a
    modal stops dead and resumes exactly where it was, with the same phase, the
    same position and the same remaining wait.
    """

    scroller = attach(pane)
    scroller._phase = Phase.DOWN
    scroller._wait_ms = 0
    pane.verticalScrollBar().setValue(30)

    modal = QDialog()
    modal.setModal(True)
    modal.show()
    app.processEvents()

    if QApplication.activeModalWidget() is not modal:
        modal.close()
        pytest.skip("the offscreen platform did not make the dialog modal")

    assert scroller._is_frozen() is True

    position = pane.verticalScrollBar().value()
    _run_ticks(scroller, 50)
    assert pane.verticalScrollBar().value() == position
    assert scroller._phase is Phase.DOWN

    modal.close()
    app.processEvents()
    assert scroller._is_frozen() is False


def test_a_modal_that_owns_the_surface_does_not_freeze_it(pane, app) -> None:
    """The modal's OWN surfaces are exactly the ones that should still read."""

    dialog = QDialog()
    inner = QPlainTextEdit(dialog)
    inner.setPlainText(LONG_TEXT)
    dialog.setModal(True)
    dialog.show()
    app.processEvents()

    scroller = attach(inner)
    if QApplication.activeModalWidget() is dialog:
        assert scroller._is_frozen() is False

    dialog.close()
    app.processEvents()

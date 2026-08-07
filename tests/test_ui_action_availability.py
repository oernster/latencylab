from __future__ import annotations

import itertools

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from latencylab_ui import main_window_actions as actions
from latencylab_ui.main_window import MainWindow
from latencylab_ui.theme import Theme, apply_theme, tokens_for

BOOLS = (False, True)


class _IdleController(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
    finished = Signal(int, float)

    def is_running(self) -> bool:
        return False

    def is_cancelled(self, run_token: int) -> bool:
        return False

    def shutdown(self) -> None:
        return None


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication) -> MainWindow:
    win = MainWindow(run_controller=_IdleController())
    win.show()
    app.processEvents()
    yield win
    win.close()


# --------------------------------------------------------------- the rules


def test_run_needs_a_model_and_no_run_in_progress() -> None:
    assert actions.availability(
        running=False, model_loaded=True, have_outputs=False
    ).run
    assert not actions.availability(
        running=False, model_loaded=False, have_outputs=True
    ).run
    assert not actions.availability(
        running=True, model_loaded=True, have_outputs=True
    ).run


def test_cancel_is_available_exactly_while_running() -> None:
    for model_loaded, have_outputs in itertools.product(BOOLS, BOOLS):
        for running in BOOLS:
            state = actions.availability(
                running=running, model_loaded=model_loaded, have_outputs=have_outputs
            )
            assert state.cancel is running
            assert state.inputs is (not running)


def test_run_and_cancel_are_never_both_available() -> None:
    """They are opposite halves of one state, so both live means neither means much."""

    for running, model_loaded, have_outputs in itertools.product(BOOLS, BOOLS, BOOLS):
        state = actions.availability(
            running=running, model_loaded=model_loaded, have_outputs=have_outputs
        )
        assert not (state.run and state.cancel)


def test_inspection_actions_need_outputs_and_no_active_run() -> None:
    for running, model_loaded in itertools.product(BOOLS, BOOLS):
        without = actions.availability(
            running=running, model_loaded=model_loaded, have_outputs=False
        )
        assert not without.save_log
        assert not without.distributions

    ready = actions.availability(running=False, model_loaded=True, have_outputs=True)
    assert ready.save_log
    assert ready.distributions


def test_every_unavailable_action_explains_itself() -> None:
    """A red ring says "inert", never why. The tooltip is the why."""

    assert actions.run_tooltip(running=False, model_loaded=False) == (
        actions.RUN_NEEDS_MODEL
    )
    assert actions.run_tooltip(running=True, model_loaded=True) == (
        actions.RUN_IN_PROGRESS
    )
    assert actions.run_tooltip(running=False, model_loaded=True) == actions.RUN_READY

    assert actions.cancel_tooltip(running=False) == actions.CANCEL_IDLE
    assert actions.cancel_tooltip(running=True) == actions.CANCEL_READY

    assert actions.save_tooltip(available=False) == actions.SAVE_NEEDS_OUTPUTS
    assert actions.save_tooltip(available=True) == actions.SAVE_READY

    assert actions.distributions_tooltip(available=False) == (
        actions.DISTRIBUTIONS_NEEDS_OUTPUTS
    )
    assert actions.distributions_tooltip(available=True) == (
        actions.DISTRIBUTIONS_READY
    )


# ------------------------------------------------------------- and the paint


def test_a_cold_window_opens_with_every_action_inert(window: MainWindow) -> None:
    assert window._run_btn.isEnabled() is False
    assert window._cancel_btn.isEnabled() is False
    assert window._save_log_btn.isEnabled() is False
    assert window._distributions_btn.isEnabled() is False
    assert window._run_select.isEnabled() is False

    assert window._run_btn.toolTip() == actions.RUN_NEEDS_MODEL
    assert window._save_log_btn.toolTip() == actions.SAVE_NEEDS_OUTPUTS


@pytest.mark.parametrize("theme", (Theme.DARK, Theme.LIGHT))
def test_run_wears_the_red_ring_until_a_model_is_loaded(
    app: QApplication, window: MainWindow, theme: Theme
) -> None:
    """The reported ask, measured off the rendered pixels.

    Disabled is not a colour that was applied to Run specially: it falls out of
    the one `:disabled` rule in the stylesheet. Asserting the pixels is what
    proves the rule reached this particular button, since an object-name rule
    elsewhere could silently have overridden it.
    """

    from pathlib import Path

    from latencylab.model import Model

    apply_theme(app, theme)
    app.processEvents()

    danger = QColor(tokens_for(theme).danger).rgb()

    def danger_pixels() -> int:
        image = window._run_btn.grab().toImage()
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixel(x, y) == danger
        )

    assert window._run_btn.isEnabled() is False
    assert danger_pixels() > 0

    window._set_model_load_ok(
        Path("model.json"),
        Model.from_json(
            {
                "schema_version": 1,
                "entry_event": "e0",
                "contexts": {"ui": {"concurrency": 1}},
                "events": {"e0": {"tags": ["ui"]}},
                "tasks": {},
            }
        ),
    )
    app.processEvents()

    assert window._run_btn.isEnabled() is True
    assert window._run_btn.toolTip() == actions.RUN_READY
    assert danger_pixels() == 0

from __future__ import annotations

import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton

from latencylab_ui import attention_flash
from latencylab_ui.attention_flash import (
    FLASH_COUNT,
    FLASH_INTERVAL_MS,
    FLASH_OFF_MS,
    FLASH_ON_MS,
    FLASH_PROPERTY,
    AttentionFlash,
)
from latencylab_ui.theme import Theme, apply_theme, tokens_for


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _drive(flash: AttentionFlash) -> list[bool]:
    """Run the sequence to its end, recording the lit state after each step.

    The timer is driven by hand rather than waited on: the schedule is what is
    under test, and a test that sleeps for the real interval buys nothing but
    seconds.
    """

    seen = [flash.is_lit()]
    # Twice the number of flashes is the whole sequence (on, off, on, off), and
    # one extra step proves it has genuinely stopped rather than paused.
    for _ in range(FLASH_COUNT * 2 + 1):
        flash._advance()
        seen.append(flash.is_lit())
    return seen


def test_the_sequence_is_finite_and_ends_dark(app: QApplication) -> None:
    """The whole point: it draws the eye once and then stops.

    A pulse that runs until it is obeyed is a nag, and the user who has already
    read it has no way to say so.
    """

    button = QPushButton("Run")
    flash = AttentionFlash(button)

    flash.start()
    seen = _drive(flash)

    assert seen[0] is True
    assert seen.count(True) == FLASH_COUNT
    assert seen[-1] is False
    assert flash.is_lit() is False

    button.deleteLater()


def test_the_gap_between_flashes_is_measured_start_to_start() -> None:
    """Lengthening the lit half must not silently shorten the gap."""

    assert FLASH_ON_MS + FLASH_OFF_MS == FLASH_INTERVAL_MS
    assert FLASH_OFF_MS > 0


def test_starting_again_restarts_rather_than_stacking(app: QApplication) -> None:
    button = QPushButton("Run")
    flash = AttentionFlash(button)

    flash.start()
    flash._advance()  # part-way through
    flash.start()

    seen = _drive(flash)

    assert seen.count(True) == FLASH_COUNT
    assert flash.is_lit() is False

    button.deleteLater()


def test_a_disabled_control_is_left_alone(app: QApplication) -> None:
    """Pointing at a control that cannot be used says the opposite.

    It would also collide with the red ring that is already explaining why it
    cannot be used.
    """

    button = QPushButton("Run")
    button.setEnabled(False)
    flash = AttentionFlash(button)

    flash.start()

    assert flash.is_lit() is False
    assert button.property(FLASH_PROPERTY) is False

    button.deleteLater()


def test_stop_clears_a_sequence_in_progress(app: QApplication) -> None:
    button = QPushButton("Run")
    flash = AttentionFlash(button)

    flash.start()
    assert flash.is_lit() is True

    flash.stop()

    assert flash.is_lit() is False
    assert button.property(FLASH_PROPERTY) is False

    button.deleteLater()


@pytest.mark.parametrize("theme", (Theme.DARK, Theme.LIGHT))
def test_the_flash_paints_the_same_green_as_the_ring(
    app: QApplication, theme: Theme
) -> None:
    """Measured off rendered pixels, and off the ring token rather than a copy.

    Hover, focus and this all mean "you can use this", so a fourth colour would
    be a fourth thing to learn.
    """

    apply_theme(app, theme)
    ring = QColor(tokens_for(theme).ring).rgb()

    button = QPushButton("Run")
    # A lone shown widget takes focus, and focus paints the same green, which
    # would make the "before" image indistinguishable from the "after".
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.resize(120, 40)
    button.show()
    app.processEvents()

    flash = AttentionFlash(button)
    before = button.grab().toImage()
    flash.start()
    app.processEvents()
    lit = button.grab().toImage()

    def _ring_pixels(image) -> int:
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixel(x, y) == ring
        )

    assert _ring_pixels(before) == 0
    assert _ring_pixels(lit) > 0

    flash.stop()
    button.hide()
    button.deleteLater()


def test_the_stylesheet_selects_on_the_property_the_flash_sets() -> None:
    """The two halves are written in different files, so they are pinned here."""

    from latencylab_ui.theme_stylesheet import build_stylesheet
    from latencylab_ui.theme_tokens import DARK_TOKENS

    sheet = build_stylesheet(DARK_TOKENS)

    assert f'QPushButton[{attention_flash.FLASH_PROPERTY}="true"]' in sheet

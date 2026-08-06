from __future__ import annotations

import pytest

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from latencylab_ui.theme import Theme, apply_theme, tokens_for
from latencylab_ui.theme_stylesheet import build_stylesheet
from latencylab_ui.theme_tokens import DARK_TOKENS, LIGHT_TOKENS

THEMES = (Theme.DARK, Theme.LIGHT)


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _count_pixels(image, colour: str) -> int:
    """How many pixels of the rendered widget are exactly `colour`.

    Exact rather than near: every token is a solid hex with no alpha, chosen so
    that a rendered ring can be asserted against the token it came from rather
    than eyeballed.
    """

    wanted = QColor(colour).rgb()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) == wanted
    )


def test_light_and_dark_do_not_share_a_ring_or_danger_colour() -> None:
    """A pastel green that reads on near-black is weak on white.

    Sharing one green across both themes is the mistake this guards; the
    saturated light-theme values exist precisely because the surfaces differ.
    """

    assert DARK_TOKENS.ring != LIGHT_TOKENS.ring
    assert DARK_TOKENS.danger != LIGHT_TOKENS.danger


def test_no_token_is_reused_across_meanings() -> None:
    """The accent is never the ring, and the ring is never the danger colour."""

    for tokens in (DARK_TOKENS, LIGHT_TOKENS):
        assert tokens.ring != tokens.accent
        assert tokens.ring != tokens.danger
        assert tokens.danger != tokens.accent
        # A control's fill must contrast the surface it sits on.
        assert tokens.panel != tokens.surface


@pytest.mark.parametrize("theme", THEMES)
def test_every_hover_and_focus_rule_is_gated_on_enabled(theme: Theme) -> None:
    """An ungated rule lights a dead control up under the mouse."""

    for line in build_stylesheet(tokens_for(theme)).splitlines():
        stripped = line.strip()
        if ":hover" in stripped or ":focus" in stripped:
            assert ":enabled:hover" in stripped or ":enabled:focus" in stripped, line


@pytest.mark.parametrize("theme", THEMES)
def test_button_ring_is_absent_at_rest_green_on_focus_and_red_when_disabled(
    app: QApplication, theme: Theme
) -> None:
    """The whole three-state model, measured off the rendered pixels."""

    apply_theme(app, theme)
    tokens = tokens_for(theme)

    host = QWidget()
    layout = QVBoxLayout(host)
    button = QPushButton("Run")
    layout.addWidget(button)
    host.show()
    app.processEvents()

    # Qt hands focus to the only focusable child the moment the window is shown,
    # so "at rest" has to be established rather than assumed. This is the same
    # reason the main window needs a neutral-start focus sink.
    button.clearFocus()
    app.processEvents()

    at_rest = host.grab().toImage()
    assert _count_pixels(at_rest, tokens.ring) == 0
    assert _count_pixels(at_rest, tokens.danger) == 0

    button.setFocus()
    app.processEvents()
    focused = host.grab().toImage()
    assert _count_pixels(focused, tokens.ring) > 0
    assert _count_pixels(focused, tokens.danger) == 0

    button.clearFocus()
    button.setEnabled(False)
    app.processEvents()
    disabled = host.grab().toImage()
    assert _count_pixels(disabled, tokens.danger) > 0
    assert _count_pixels(disabled, tokens.ring) == 0

    host.close()

from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from latencylab_ui.main_window import MainWindow
from latencylab_ui.theme import Theme, apply_theme, tokens_for

# Widths chosen either side of the default so centring is shown to be a property
# of the layout rather than of one lucky size.
WINDOW_WIDTHS = (900, 1400, 1920)
WINDOW_HEIGHT = 720

# A badge one pixel off centre is not a defect; a badge 134 pixels off centre
# was the reported one. Half a pixel of rounding is all the slack there is.
CENTRING_TOLERANCE_PX = 1.0


class _IdleController(QObject):
    """A controller that never runs anything, so the window builds and stops."""

    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
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


@pytest.mark.parametrize("width", WINDOW_WIDTHS)
def test_badge_is_centred_on_the_bar_not_on_the_leftover_space(
    app: QApplication, window: MainWindow, width: int
) -> None:
    """The reported defect, measured.

    The badge used to sit between two stretches, which centres it in the gap
    between the flanking control groups. Those groups are nowhere near the same
    width, so it landed 134px right of centre in a 1400px window.
    """

    window.resize(width, WINDOW_HEIGHT)
    app.processEvents()

    badge = window._top_badge
    bar = badge.parentWidget()
    badge_centre = badge.geometry().x() + badge.geometry().width() / 2

    assert abs(badge_centre - bar.width() / 2) <= CENTRING_TOLERANCE_PX


def test_badge_is_the_generated_icon_and_not_a_font_glyph(window: MainWindow) -> None:
    """A glyph is whatever font happens to be installed; a file is the mark."""

    badge = window._top_badge
    assert badge.text() == ""
    pixmap = badge.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()


def test_compose_button_is_reachable_and_tracks_the_dock(window: MainWindow) -> None:
    compose = window._compose_btn

    assert compose.isCheckable()
    assert compose.focusPolicy() != compose.focusPolicy().NoFocus
    assert not compose.isChecked()

    window._model_composer_dock.setVisible(True)
    assert compose.isChecked()

    window._model_composer_dock.setVisible(False)
    assert not compose.isChecked()


@pytest.mark.parametrize("theme", (Theme.DARK, Theme.LIGHT))
def test_compose_button_looks_different_when_the_composer_is_open(
    app: QApplication, window: MainWindow, theme: Theme
) -> None:
    """Checked was already being SET. What was missing was any way to see it.

    Neither stylesheet had a rule for the checked state of this button, so open
    and closed rendered identically. Asserting the rendered pixels is the only
    way to tell a state that is set from a state that is shown.
    """

    apply_theme(app, theme)
    app.processEvents()

    compose = window._compose_btn
    accent = QColor(tokens_for(theme).accent).rgb()

    def accent_pixels() -> int:
        image = compose.grab().toImage()
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixel(x, y) == accent
        )

    window._model_composer_dock.setVisible(False)
    app.processEvents()
    assert accent_pixels() == 0

    window._model_composer_dock.setVisible(True)
    app.processEvents()
    assert accent_pixels() > 0

    window._model_composer_dock.setVisible(False)

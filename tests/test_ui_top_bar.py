from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication

from latencylab_ui.main_window import MainWindow
from latencylab_ui.theme import Theme, apply_theme, tokens_for

# Widths chosen either side of the default so centring is shown to be a property
# of the layout rather than of one lucky size.
WINDOW_WIDTHS = (900, 1400, 1920)

# Large enough that scaling leaves solid interior pixels rather than only the
# blended edges an icon this size is mostly made of.
ICON_PROBE_PX = 64

# Rasterising blends the ink against transparency at every edge, so an exact
# match would only ever hold in the middle of a stroke.
INK_TOLERANCE = 60
WINDOW_HEIGHT = 720

# A badge one pixel off centre is not a defect; a badge 134 pixels off centre
# was the reported one. Half a pixel of rounding is all the slack there is.
CENTRING_TOLERANCE_PX = 1.0


class _IdleController(QObject):
    """A controller that never runs anything, so the window builds and stops."""

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


@pytest.mark.parametrize("width", WINDOW_WIDTHS)
def test_the_mark_is_centred_on_the_bar_not_on_the_leftover_space(
    app: QApplication, window: MainWindow, width: int
) -> None:
    """The reported defect, measured.

    The mark used to sit between two stretches, which centres it in the gap
    between the flanking control groups. Those groups are nowhere near the same
    width, so it landed 134px right of centre in a 1400px window.
    """

    window.resize(width, WINDOW_HEIGHT)
    app.processEvents()

    mark = window._distributions_btn
    bar = mark.parentWidget()
    mark_centre = mark.geometry().x() + mark.geometry().width() / 2

    assert abs(mark_centre - bar.width() / 2) <= CENTRING_TOLERANCE_PX


def test_the_mark_is_the_generated_icon_and_not_a_font_glyph(
    window: MainWindow,
) -> None:
    """A glyph is whatever font happens to be installed; a file is the mark."""

    mark = window._distributions_btn
    assert mark.text() == ""
    assert mark.icon().isNull() is False


def test_the_mark_is_re_inked_for_the_checked_state(window: MainWindow) -> None:
    """The mark's hands and hub are banana and the checked fill is banana, so
    on its own the mark loses them at exactly the moment the button is saying
    something. A stylesheet cannot reach inside an icon, so the checked state
    gets a second rendering, the same answer the drawn glyphs already use."""

    icon = window._distributions_btn.icon()
    size = QSize(ICON_PROBE_PX, ICON_PROBE_PX)

    unchecked = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.Off).toImage()
    checked = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.On).toImage()

    assert unchecked != checked

    ink = QColor(tokens_for(Theme.DARK).accent_text)
    opaque = 0
    inked = 0
    for y in range(checked.height()):
        for x in range(checked.width()):
            pixel = QColor(checked.pixel(x, y))
            if checked.pixelColor(x, y).alpha() == 0:
                continue
            opaque += 1
            if (
                abs(pixel.red() - ink.red()) <= INK_TOLERANCE
                and abs(pixel.green() - ink.green()) <= INK_TOLERANCE
                and abs(pixel.blue() - ink.blue()) <= INK_TOLERANCE
            ):
                inked += 1

    assert opaque > 0
    # Every visible part of it, not most of it: the whole mark is re-inked.
    assert inked == opaque


def test_the_centre_mark_is_the_distributions_toggle(window: MainWindow) -> None:
    """It was decoration; it is now the control. The mark is the most prominent
    thing on the bar and the panel it opens is the point of running anything, so
    the two belong together rather than competing from opposite ends."""

    mark = window._distributions_btn

    assert mark.isCheckable() is True
    assert mark.toolTip()
    # Not transparent to the mouse any more, and on the keyboard ring, because
    # there is now something to do to it.
    assert mark.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False
    assert mark.focusPolicy() != Qt.FocusPolicy.NoFocus

    window._distributions_dock.setVisible(True)
    assert mark.isChecked() is True
    window._distributions_dock.setVisible(False)
    assert mark.isChecked() is False


def test_compose_button_is_reachable_and_is_not_a_toggle(window: MainWindow) -> None:
    """It was checkable while the composer was a dock sharing the window with
    the results, because the button was the only thing saying which of the two
    was up. A modal dialog IS the window while it is open, so a button
    reporting that from underneath it says nothing."""

    compose = window._compose_btn

    assert compose.isCheckable() is False
    assert compose.focusPolicy() != compose.focusPolicy().NoFocus

    window._model_composer.show()
    assert compose.isChecked() is False

    window._model_composer.reject()


def _accent_pixels(widget, accent: QColor) -> int:
    """How much of a rendered button is drawn in the accent."""

    image = widget.grab().toImage()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if _near(QColor(image.pixel(x, y)), accent)
    )


def _near(pixel: QColor, want: QColor) -> bool:
    return (
        abs(pixel.red() - want.red()) <= INK_TOLERANCE
        and abs(pixel.green() - want.green()) <= INK_TOLERANCE
        and abs(pixel.blue() - want.blue()) <= INK_TOLERANCE
    )


@pytest.mark.parametrize("name", ("_compose_btn", "_edit_btn"))
def test_the_drawn_glyphs_are_two_tone(
    app: QApplication, window: MainWindow, name: str
) -> None:
    """A single-tone glyph on a filled button reads as a watermark.

    Compose and Edit both split the same way the Guide's book does: the part
    that merely sits there takes the button's ink, and the part that says what
    the button DOES takes the accent.
    """

    apply_theme(app, Theme.DARK)
    app.processEvents()

    button = getattr(window, name)
    button.setEnabled(True)
    app.processEvents()

    assert _accent_pixels(button, QColor(tokens_for(Theme.DARK).accent)) > 0


@pytest.mark.parametrize("name", ("_compose_btn", "_edit_btn"))
def test_a_disabled_drawn_glyph_mutes_both_of_its_tones(
    app: QApplication, window: MainWindow, name: str
) -> None:
    """A glyph that keeps its accent while the rest of it greys out reads as
    half-available, which is not a state this application has."""

    apply_theme(app, Theme.DARK)
    accent = QColor(tokens_for(Theme.DARK).accent)

    button = getattr(window, name)
    button.setEnabled(False)
    app.processEvents()

    assert _accent_pixels(button, accent) == 0

    button.setEnabled(True)
    app.processEvents()


@pytest.mark.parametrize("theme", (Theme.DARK, Theme.LIGHT))
def test_distributions_button_looks_different_when_the_panel_is_open(
    app: QApplication, window: MainWindow, theme: Theme
) -> None:
    """Checked being SET is not the same as checked being SHOWN.

    A stylesheet with no rule for a button's checked state renders open and
    closed identically, which is a state nobody can see. Asserting the rendered
    pixels is the only way to tell the two apart.
    """

    apply_theme(app, theme)
    app.processEvents()

    button = window._distributions_btn
    accent = QColor(tokens_for(theme).accent).rgb()

    def accent_pixels() -> int:
        image = button.grab().toImage()
        return sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if image.pixel(x, y) == accent
        )

    window._distributions_dock.setVisible(False)
    app.processEvents()
    assert accent_pixels() == 0

    window._distributions_dock.setVisible(True)
    app.processEvents()
    assert accent_pixels() > 0

    window._distributions_dock.setVisible(False)

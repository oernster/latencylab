from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMenu, QPushButton, QTextBrowser

from latencylab_ui.auto_scroller import AutoScroller
from latencylab_ui.guide_dialog import GuideDialog
from latencylab_ui.guide_text import GUIDE_HTML, GUIDE_TITLE
from latencylab_ui.main_window import MainWindow
from latencylab_ui.main_window_menus import show_guide_dialog
from latencylab_ui.theme import Theme, apply_theme, tokens_for

# Rasterising blends the ink against transparency at every edge, so an exact
# match would only hold in the middle of a stroke.
ACCENT_TOLERANCE = 55

# The steps somebody has to be able to follow without knowing anything first.
# Named rather than counted, so a rewrite that quietly drops one fails here.
FIRST_RUN_STEPS = ("Examples", "Runs", "Seed", "Run", "Summary", "Critical path")

# The settings the guide promises to explain the reasoning for.
SETTINGS_EXPLAINED = (
    "Runs",
    "Seed",
    "Concurrency",
    "Lognormal",
    "Delays on wiring",
    "Stress multiplier",
)


class _IdleController(QObject):
    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
    finished = Signal(int, float)

    def is_running(self) -> bool:
        return False

    def is_cancelled(self, _token: int) -> bool:
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
    app.processEvents()


def test_the_guide_starts_with_something_to_do(app: QApplication) -> None:
    """Somebody opening this has the application in front of them and wants to
    make it do something in the next minute, so the instructions come before
    any of the reasons."""

    for step in FIRST_RUN_STEPS:
        assert step in GUIDE_HTML

    first_run = GUIDE_HTML.index("Run something, in six steps")
    reasons = GUIDE_HTML.index("Why you would choose each setting")
    assert first_run < reasons


def test_the_guide_says_why_for_every_setting_it_offers(app: QApplication) -> None:
    """A guide that lists controls without saying when to reach for them leaves
    the reader exactly where they started."""

    for setting in SETTINGS_EXPLAINED:
        assert setting in GUIDE_HTML


def test_the_guide_reads_itself(app: QApplication, window: MainWindow) -> None:
    """Long guidance descends slowly, holds, rewinds and repeats, so a reader
    who opens it and does nothing is carried through it."""

    dialog = GuideDialog(window)
    dialog.show()
    app.processEvents()

    body = dialog.findChild(QTextBrowser)
    assert body is not None
    assert body.findChild(AutoScroller) is not None

    dialog.close()
    dialog.deleteLater()


def test_the_guide_is_html_on_a_pixel_scrolling_surface(
    app: QApplication, window: MainWindow
) -> None:
    """The reading cycle moves in PIXELS. A plain-text widget scrolls in lines,
    where the same gentle drift becomes a whole line jumping at a time."""

    dialog = GuideDialog(window)
    dialog.show()
    app.processEvents()

    body = dialog.findChild(QTextBrowser)
    assert body is not None
    assert isinstance(body, QTextBrowser)
    # Rendered as a document rather than shown as markup.
    assert "<h3>" not in body.toPlainText()
    assert "Guide to LatencyLab" in body.toPlainText()

    dialog.close()
    dialog.deleteLater()


def test_the_guide_does_not_block_the_thing_it_describes(
    app: QApplication, window: MainWindow
) -> None:
    """Guidance you cannot keep open beside the application is guidance you
    have to memorise first."""

    dialog = GuideDialog(window)

    assert dialog.isModal() is False

    dialog.deleteLater()


def test_the_button_sits_immediately_left_of_the_info_button(
    app: QApplication, window: MainWindow
) -> None:
    """The pair is one idea in two halves: which button to press, then what the
    output means."""

    guide = window._guide_btn
    info = window._how_to_read_btn

    assert guide.objectName() == "guide_btn"
    assert guide.toolTip() == GUIDE_TITLE
    # A drawn glyph rather than a caption, like the rest of the tray.
    assert guide.text() == ""
    assert guide.icon().isNull() is False
    assert guide.x() < info.x()


def test_the_button_opens_the_guide(app: QApplication, window: MainWindow) -> None:
    window._guide_btn.click()
    app.processEvents()

    dialog = window._guide_dialog
    assert isinstance(dialog, GuideDialog)
    assert dialog.isVisible() is True

    dialog.close()
    app.processEvents()


def test_the_guide_is_on_the_help_menu_above_how_to_read(
    app: QApplication, window: MainWindow
) -> None:
    """Which button to press comes before what the output means."""

    # The menus are children of the WINDOW, not of the bar: `add_menu` gives
    # each one an explicit parent so its lifetime belongs to C++.
    help_menu = next(
        menu for menu in window.findChildren(QMenu) if menu.title() == "Help"
    )
    labels = [action.text() for action in help_menu.actions()]

    assert GUIDE_TITLE in labels
    assert labels.index(GUIDE_TITLE) < labels.index("How to Read LatencyLab Output")


def test_showing_the_guide_keeps_it_alive(
    app: QApplication, window: MainWindow
) -> None:
    """A dialog nobody holds is collected the moment the function returns."""

    show_guide_dialog(window)
    app.processEvents()

    assert isinstance(window._guide_dialog, GuideDialog)

    window._guide_dialog.close()
    app.processEvents()


def test_the_guide_button_is_a_tray_button_like_the_others(
    app: QApplication, window: MainWindow
) -> None:
    assert isinstance(window._guide_btn, QPushButton)
    assert window._guide_btn.property("role") == "icon-action"
    assert window._guide_btn.isCheckable() is False


def _accent_pixels(widget, accent: QColor) -> int:
    image = widget.grab().toImage()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if _near(QColor(image.pixel(x, y)), accent)
    )


def _near(pixel: QColor, want: QColor) -> bool:
    return (
        abs(pixel.red() - want.red()) < ACCENT_TOLERANCE
        and abs(pixel.green() - want.green()) < ACCENT_TOLERANCE
        and abs(pixel.blue() - want.blue()) < ACCENT_TOLERANCE
    )


def test_the_book_is_drawn_in_two_colours(
    app: QApplication, window: MainWindow
) -> None:
    """A single-tone version came out as two blank curves: it said "a document"
    where it needed to say "a manual with something in it"."""

    apply_theme(app, Theme.DARK)
    app.processEvents()
    accent = QColor(tokens_for(Theme.DARK).accent)

    assert _accent_pixels(window._guide_btn, accent) > 0


def test_a_disabled_book_mutes_both_of_its_colours(
    app: QApplication, window: MainWindow
) -> None:
    """A glyph that keeps its accent while the rest of it greys out reads as
    half-available, which is not a state this application has."""

    apply_theme(app, Theme.DARK)
    accent = QColor(tokens_for(Theme.DARK).accent)

    window._guide_btn.setEnabled(False)
    app.processEvents()

    assert _accent_pixels(window._guide_btn, accent) == 0

    window._guide_btn.setEnabled(True)
    app.processEvents()

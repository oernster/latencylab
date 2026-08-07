from __future__ import annotations

import pytest

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.main_window_menus import add_menu
from latencylab_ui.qt_style_helpers import harden_combobox_popup
from latencylab_ui.theme import Theme, apply_theme, tokens_for
from latencylab_ui.theme_tokens import DARK_TOKENS, LIGHT_TOKENS

THEMES = (Theme.DARK, Theme.LIGHT)

# How far apart two greys have to be before a person can see the join. The
# menu shipped at a difference of ZERO: the popup was painted in the window
# colour with no border, so it had no visible edge at all.
MIN_SEPARATION = 20.0


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _luminance(colour: QColor) -> float:
    return 0.2126 * colour.red() + 0.7152 * colour.green() + 0.0722 * colour.blue()


def _separation(left: str, right: str) -> float:
    return abs(_luminance(QColor(left)) - _luminance(QColor(right)))


def _dropped_menu_image(window: QMainWindow, app: QApplication):
    menu = add_menu(window, "Examples")
    for label in ("Checkout", "Contention", "Interactive"):
        menu.addAction(label)
    window.resize(400, 200)
    window.show()
    app.processEvents()

    menu.popup(window.mapToGlobal(window.rect().topLeft()))
    app.processEvents()
    image = menu.grab().toImage()

    menu.hide()
    window.hide()
    return image


@pytest.mark.parametrize("tokens", (DARK_TOKENS, LIGHT_TOKENS))
def test_a_floating_surface_is_never_the_window_colour(tokens) -> None:
    """The reported bug, stated as a rule.

    A menu painted in the window colour is not merely low contrast, it is
    invisible: its items read as text written onto the window behind it.
    """

    assert tokens.elevated != tokens.surface
    assert tokens.elevated_hover != tokens.elevated
    assert tokens.elevated_border != tokens.elevated


@pytest.mark.parametrize("tokens", (DARK_TOKENS, LIGHT_TOKENS))
def test_a_popup_is_separated_by_its_fill_or_its_border(tokens) -> None:
    """One of the two has to do the work, and in light it is the border.

    White on off-white is a small fill difference on purpose, which is why the
    border is allowed to carry it rather than both being required to.
    """

    by_fill = _separation(tokens.elevated, tokens.surface)
    by_edge = _separation(tokens.elevated_border, tokens.surface)

    assert max(by_fill, by_edge) >= MIN_SEPARATION


@pytest.mark.parametrize("theme", THEMES)
def test_the_rendered_menu_paints_the_elevated_surface(
    app: QApplication, theme: Theme
) -> None:
    """Measured off the rendered pixels, not read off the stylesheet."""

    apply_theme(app, theme)
    tokens = tokens_for(theme)

    window = QMainWindow()
    image = _dropped_menu_image(window, app)

    body = image.pixelColor(image.width() // 2, image.height() // 2)
    edge = image.pixelColor(0, image.height() // 2)

    assert body.name() == QColor(tokens.elevated).name()
    assert edge.name() == QColor(tokens.elevated_border).name()

    window.deleteLater()


def test_a_checked_button_repaints_its_glyph_in_the_accent_ink(
    app: QApplication,
) -> None:
    """A stylesheet cannot reach inside an icon.

    The checked fill is the light accent and the checked TEXT is dark, but a
    glyph is a baked pixmap: without a second rendering it stays near-white and
    disappears at the moment the button is saying something.
    """

    from PySide6.QtGui import QIcon

    from latencylab_ui.glyphs import compose_body, two_tone_icon

    tokens = tokens_for(Theme.DARK)
    icon = two_tone_icon(
        compose_body,
        ink=tokens.primary_text,
        accent=tokens.accent,
        disabled=tokens.muted_text,
        checked_ink=tokens.accent_text,
        size=20,
    )

    off = icon.pixmap(20, QIcon.Mode.Normal, QIcon.State.Off).toImage()
    on = icon.pixmap(20, QIcon.Mode.Normal, QIcon.State.On).toImage()

    assert off != on

    def _has(image, colour: str) -> bool:
        wanted = QColor(colour).rgb()
        return any(
            image.pixel(x, y) == wanted
            for y in range(image.height())
            for x in range(image.width())
        )

    assert _has(off, tokens.primary_text)
    assert _has(on, tokens.accent_text)


@pytest.mark.parametrize("theme", THEMES)
def test_a_combo_popup_floats_on_the_same_surface_as_a_menu(
    app: QApplication, theme: Theme
) -> None:
    """The open list is a popup too, and had the same defect.

    Copying the closed combo's Base across to its popup put the open list
    within six levels of luminance of the window in the dark theme. It is
    painted on `elevated` now, like every other floating surface.
    """

    apply_theme(app, theme)
    tokens = tokens_for(theme)

    window = QMainWindow()
    root = QWidget()
    layout = QVBoxLayout(root)
    combo = QComboBox()
    combo.addItems(["Run 1", "Run 2", "Run 3"])
    harden_combobox_popup(combo)
    layout.addWidget(combo)
    window.setCentralWidget(root)
    window.resize(400, 200)
    window.show()
    app.processEvents()

    combo.showPopup()
    app.processEvents()
    image = combo.view().window().grab().toImage()

    body = image.pixelColor(image.width() // 2, image.height() // 2)
    assert body.name() == QColor(tokens.elevated).name()

    combo.hidePopup()
    window.hide()
    window.deleteLater()


@pytest.mark.parametrize("theme", THEMES)
def test_the_rendered_menu_stands_off_the_window_behind_it(
    app: QApplication, theme: Theme
) -> None:
    apply_theme(app, theme)
    tokens = tokens_for(theme)

    window = QMainWindow()
    image = _dropped_menu_image(window, app)

    body = image.pixelColor(image.width() // 2, image.height() // 2)
    edge = image.pixelColor(0, image.height() // 2)
    behind = QColor(tokens.surface)

    separation = max(
        abs(_luminance(body) - _luminance(behind)),
        abs(_luminance(edge) - _luminance(behind)),
    )
    assert separation >= MIN_SEPARATION

    window.deleteLater()

from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_apply_theme_dark_and_light() -> None:
    app = _ensure_qapp()

    from latencylab_ui.theme import Theme, apply_theme

    apply_theme(app, Theme.DARK)
    dark_hl = app.palette().color(app.palette().ColorRole.Highlight).name()

    apply_theme(app, Theme.LIGHT)
    light_window = app.palette().color(app.palette().ColorRole.Window).name()
    light_hl = app.palette().color(app.palette().ColorRole.Highlight).name()

    assert dark_hl == light_hl  # teal accent consistent
    assert light_window == "#f8f8f8"


def test_theme_toggle_emits() -> None:
    _ensure_qapp()

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import ThemeToggle

    t = ThemeToggle(default=Theme.DARK)
    seen: list[Theme] = []
    t.theme_changed.connect(lambda theme: seen.append(theme))

    t.set_theme(Theme.LIGHT)
    assert seen[-1] == Theme.LIGHT

    t.set_theme(Theme.DARK)
    assert seen[-1] == Theme.DARK


def test_theme_toggle_is_one_button_that_is_never_disabled() -> None:
    """The pair it replaced disabled whichever theme was in force.

    Under the three-state ring model that painted the ACTIVE theme with the
    permanent red danger ring, and it put a control on the keyboard ring that
    could never be reached. A single button that is never disabled has neither
    problem.
    """

    _ensure_qapp()

    from PySide6.QtWidgets import QPushButton

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import ThemeToggle

    t = ThemeToggle(default=Theme.DARK)

    assert isinstance(t, QPushButton)
    assert t.findChildren(QPushButton) == []
    assert t.isEnabled()

    t.set_theme(Theme.LIGHT)
    assert t.isEnabled()


def test_sun_asks_for_emoji_presentation_and_moon_does_not_need_to() -> None:
    """The sun rendered monochrome white until it carried U+FE0F.

    U+2600 defaults to TEXT presentation, so it is painted in the label's own
    text colour rather than by the emoji font. U+1F319 is emoji-presentation by
    default, which is why exactly one of the pair looked wrong. The selector is
    invisible in source, so it is asserted by codepoint: nothing about the
    rendered glyph can be checked headlessly, because the offscreen platform has
    no font families at all.
    """

    from latencylab_ui import theme_toggle

    assert [hex(ord(c)) for c in theme_toggle.SUN] == ["0x2600", "0xfe0f"]
    assert [hex(ord(c)) for c in theme_toggle.MOON] == ["0x1f319"]
    assert theme_toggle.VARIATION_SELECTOR_16 == "️"


def test_theme_toggle_names_the_theme_it_will_switch_to() -> None:
    """A toggle captioned with its own current state reads as an indicator."""

    _ensure_qapp()

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import MOON, SUN, ThemeToggle

    t = ThemeToggle(default=Theme.DARK)
    assert t.theme() == Theme.DARK
    assert t.next_theme() == Theme.LIGHT
    assert t.text() == SUN
    assert "light" in t.toolTip().lower()

    t.set_theme(Theme.LIGHT)
    assert t.next_theme() == Theme.DARK
    assert t.text() == MOON
    assert "dark" in t.toolTip().lower()


def test_theme_toggle_space_switches_and_switches_back() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import ThemeToggle

    t = ThemeToggle(default=Theme.DARK)
    t.show()
    app.processEvents()

    seen: list[Theme] = []
    t.theme_changed.connect(lambda theme: seen.append(theme))

    t.setFocus()
    QTest.keyClick(t, Qt.Key_Space)
    app.processEvents()
    assert t.theme() == Theme.LIGHT
    assert seen[-1] == Theme.LIGHT

    # The same key on the same control comes back: that is what makes it a
    # toggle rather than a pair of one-way switches.
    QTest.keyClick(t, Qt.Key_Space)
    app.processEvents()
    assert t.theme() == Theme.DARK
    assert seen[-1] == Theme.DARK

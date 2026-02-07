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


def test_theme_toggle_disables_current_theme_button() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QPushButton

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import ThemeToggle

    t = ThemeToggle(default=Theme.DARK)
    btns = t.findChildren(QPushButton)
    assert len(btns) == 2

    # Dark is current -> dark button disabled; light enabled.
    t.set_theme(Theme.DARK)
    dark = [b for b in btns if b.text() == "🌙"][0]
    light = [b for b in btns if b.text() == "☀"][0]
    assert not dark.isEnabled()
    assert light.isEnabled()

    # Light is current -> light button disabled; dark enabled.
    t.set_theme(Theme.LIGHT)
    assert not light.isEnabled()
    assert dark.isEnabled()


def test_theme_toggle_space_switch_updates_enabled_state() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from latencylab_ui.theme import Theme
    from latencylab_ui.theme_toggle import ThemeToggle

    t = ThemeToggle(default=Theme.DARK)
    t.show()
    app.processEvents()

    btns = t.findChildren(QPushButton)
    dark = [b for b in btns if b.text() == "🌙"][0]
    light = [b for b in btns if b.text() == "☀"][0]

    # Initial: dark is selected/disabled.
    assert not dark.isEnabled()
    assert light.isEnabled()

    # Focus and space-toggle light.
    light.setFocus()
    QTest.keyClick(light, Qt.Key_Space)
    app.processEvents()

    assert not light.isEnabled()
    assert dark.isEnabled()


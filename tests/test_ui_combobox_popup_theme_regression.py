from __future__ import annotations


def test_theme_stylesheet_mentions_combobox_popup_view() -> None:
    """Regression test: combo popup items must remain readable.

    Contract (directive): we do NOT style popup views via CSS because combo
    popups are separate widgets and stylesheet scoping is unreliable across
    platforms/styles.

    Instead:
    - Fusion + palette provide colors deterministically.
    - We allow only *item sizing* rules via CSS.
    - We harden each QComboBox programmatically to bind its popup view palette.
    """

    from latencylab_ui import theme

    # No popup view color rules via CSS.
    assert "QComboBox QAbstractItemView{" not in theme._DARK_STYLESHEET.replace(" ", "")
    assert "QComboBox QAbstractItemView{" not in theme._LIGHT_STYLESHEET.replace(" ", "")
    assert "QAbstractItemView{" not in theme._DARK_STYLESHEET.replace(" ", "")
    assert "QAbstractItemView{" not in theme._LIGHT_STYLESHEET.replace(" ", "")

    # Keep compact item height/padding rules.
    assert "QComboBox QAbstractItemView::item" in theme._DARK_STYLESHEET
    assert "QComboBox QAbstractItemView::item" in theme._LIGHT_STYLESHEET


def test_model_composer_combobox_popup_view_uses_combo_palette() -> None:
    """Regression test: Model Composer combos must explicitly harden popup view palette."""

    from PySide6.QtWidgets import QApplication

    from latencylab_ui.model_composer_wiring_editor import WiringEditor

    app = QApplication.instance() or QApplication([])
    _ = app  # keep reference in local scope

    w = WiringEditor()
    combo = w.event_combo
    view = combo.view()

    assert view.autoFillBackground() is True

    vp = view.viewport()
    assert vp is not None
    assert vp.autoFillBackground() is True

    view_pal = view.palette()
    combo_pal = combo.palette()
    assert view_pal.color(view_pal.ColorRole.Text) == combo_pal.color(combo_pal.ColorRole.Text)
    assert view_pal.color(view_pal.ColorRole.Base) == combo_pal.color(combo_pal.ColorRole.Base)

    vp_pal = vp.palette()
    assert vp_pal.color(vp_pal.ColorRole.Text) == combo_pal.color(combo_pal.ColorRole.Text)
    assert vp_pal.color(vp_pal.ColorRole.Base) == combo_pal.color(combo_pal.ColorRole.Base)


def test_combobox_popup_hardener_filter_installed_without_debug_env() -> None:
    """Regression: show-time hardening must be always-on (not debug-only)."""
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.model_composer_wiring_editor import WiringEditor

    app = QApplication.instance() or QApplication([])
    _ = app

    w = WiringEditor()
    combo = w.event_combo
    view = combo.view()

    # The always-on hardener must be installed on the popup view.
    assert hasattr(view, "_ll_combo_popup_hardener_filter")


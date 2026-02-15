from __future__ import annotations


def test_apply_theme_disable_stylesheet_branch() -> None:
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.theme import Theme, apply_theme

    app = QApplication.instance() or QApplication([])

    import os

    os.environ["LATENCYLAB_UI_THEME_DISABLE_STYLESHEET"] = "1"
    prev = app.styleSheet()
    try:
        apply_theme(app, Theme.DARK)
        # When stylesheet is disabled, we should not apply a new stylesheet.
        assert app.styleSheet() == prev
    finally:
        os.environ.pop("LATENCYLAB_UI_THEME_DISABLE_STYLESHEET", None)


def test_apply_theme_disable_fusion_branch() -> None:
    from PySide6.QtWidgets import QApplication

    from latencylab_ui.theme import Theme, apply_theme

    app = QApplication.instance() or QApplication([])

    import os

    os.environ["LATENCYLAB_UI_THEME_DISABLE_FUSION"] = "1"
    try:
        apply_theme(app, Theme.DARK)
        # Just an execution hit of the branch; styling assertions are handled
        # elsewhere.
        assert app.style() is not None
    finally:
        os.environ.pop("LATENCYLAB_UI_THEME_DISABLE_FUSION", None)


def test_apply_theme_fusion_none_fallback(monkeypatch) -> None:
    """Cover the `fusion is None` fallback branch."""

    from PySide6.QtWidgets import QApplication, QStyleFactory

    from latencylab_ui.theme import Theme, apply_theme

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(QStyleFactory, "create", lambda *_a, **_k: None)

    apply_theme(app, Theme.DARK)
    assert app.style() is not None


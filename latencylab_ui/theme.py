from __future__ import annotations

import os
import sys
from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from latencylab_ui.theme_stylesheet import _DARK_STYLESHEET, _LIGHT_STYLESHEET


# Palette accents used by both themes.
_ACCENT_TEAL = QColor(38, 166, 154)  # hover/focus accent


class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"





def _dark_palette() -> QPalette:
    """A conservative Fusion-friendly dark palette.

    This avoids per-widget overrides while still producing a true dark theme.
    """

    pal = QPalette()

    # Backgrounds (avoid pure black).
    window = QColor(30, 30, 30)
    base = QColor(24, 24, 24)
    alternate_base = QColor(36, 36, 36)
    button = QColor(40, 40, 40)

    # Text (avoid pure white).
    text = QColor(228, 228, 228)
    disabled_text = QColor(150, 150, 150)

    # Accents.
    highlight = _ACCENT_TEAL

    pal.setColor(QPalette.ColorRole.Window, window)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, alternate_base)
    pal.setColor(QPalette.ColorRole.ToolTipBase, window)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, button)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    pal.setColor(QPalette.ColorRole.Highlight, highlight)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(15, 15, 15))

    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    pal.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text
    )
    return pal


def _light_palette(app: QApplication) -> QPalette:
    """A bright, neutral light palette with minimal accent tweaks.

    We keep this explicitly light (white/near-white surfaces) to avoid the
    "slightly-less-dark" look when switching from the dark palette.
    """

    pal = app.style().standardPalette()

    window = QColor(248, 248, 248)
    base = QColor(255, 255, 255)
    alternate_base = QColor(242, 242, 242)
    button = QColor(245, 245, 245)
    text = QColor(32, 32, 32)
    disabled_text = QColor(130, 130, 130)

    pal.setColor(QPalette.ColorRole.Window, window)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, alternate_base)
    pal.setColor(QPalette.ColorRole.Button, button)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.ToolTipBase, base)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)

    pal.setColor(QPalette.ColorRole.Highlight, _ACCENT_TEAL)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(15, 15, 15))

    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    return pal


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply an application-global theme.

    v1 intentionally uses an application stylesheet only, not per-widget overrides.
    """

    disable_fusion = os.environ.get("LATENCYLAB_UI_THEME_DISABLE_FUSION", "").strip() not in (
        "",
        "0",
        "false",
    )
    disable_palette = os.environ.get("LATENCYLAB_UI_THEME_DISABLE_PALETTE", "").strip() not in (
        "",
        "0",
        "false",
    )
    disable_stylesheet = os.environ.get(
        "LATENCYLAB_UI_THEME_DISABLE_STYLESHEET", ""
    ).strip() not in ("", "0", "false")

    if not disable_fusion:
        # Use QStyleFactory for determinism; string-based style selection can be
        # platform-dependent if the style isn't available/registered.
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            app.setStyle(fusion)
        else:
            app.setStyle("Fusion")

    if theme == Theme.DARK:
        palette = _dark_palette()
        stylesheet = _DARK_STYLESHEET
    else:
        palette = _light_palette(app)
        stylesheet = _LIGHT_STYLESHEET

    if not disable_palette:
        app.setPalette(palette)
    if not disable_stylesheet:
        app.setStyleSheet(stylesheet)

    # Debug logging removed.


from __future__ import annotations

import os
from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from latencylab_ui.theme_stylesheet import build_stylesheet
from latencylab_ui.theme_tokens import DARK_TOKENS, LIGHT_TOKENS, ThemeTokens


class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


def tokens_for(theme: Theme) -> ThemeTokens:
    """The colour set behind a theme.

    Public because the ring and danger colours are not only a stylesheet
    concern: anything that paints or asserts a focus state needs the same two
    values the sheet was built from, and reading them from here is what stops a
    second, drifting copy appearing.
    """

    return DARK_TOKENS if theme == Theme.DARK else LIGHT_TOKENS


def _apply_common_palette(pal: QPalette, tokens: ThemeTokens) -> QPalette:
    """Colour a palette from the same tokens the stylesheet was built from."""

    pal.setColor(QPalette.ColorRole.Window, QColor(tokens.surface))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(tokens.text))
    pal.setColor(QPalette.ColorRole.Base, QColor(tokens.base))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens.alternate_base))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens.panel))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens.text))
    pal.setColor(QPalette.ColorRole.Text, QColor(tokens.text))
    pal.setColor(QPalette.ColorRole.Button, QColor(tokens.panel))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(tokens.text))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(tokens.accent))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(15, 15, 15))

    muted = QColor(tokens.muted_text)
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, muted)
    return pal


def _dark_palette() -> QPalette:
    """A Fusion-friendly dark palette, avoiding pure black."""

    pal = _apply_common_palette(QPalette(), DARK_TOKENS)
    pal.setColor(QPalette.ColorRole.BrightText, QColor(DARK_TOKENS.danger))
    return pal


def _light_palette(app: QApplication) -> QPalette:
    """A bright, neutral light palette.

    Explicitly light surfaces, so switching away from dark does not land on a
    slightly-less-dark grey.
    """

    return _apply_common_palette(app.style().standardPalette(), LIGHT_TOKENS)


def _disabled_by_env(name: str) -> bool:
    """Whether an escape-hatch environment variable is switched on."""

    return os.environ.get(name, "").strip() not in ("", "0", "false")


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply an application-global theme: style, palette and stylesheet."""

    if not _disabled_by_env("LATENCYLAB_UI_THEME_DISABLE_FUSION"):
        # Via QStyleFactory for determinism: string-based selection is
        # platform-dependent when the style is not registered.
        fusion = QStyleFactory.create("Fusion")
        app.setStyle(fusion if fusion is not None else "Fusion")

    palette = _dark_palette() if theme == Theme.DARK else _light_palette(app)

    if not _disabled_by_env("LATENCYLAB_UI_THEME_DISABLE_PALETTE"):
        app.setPalette(palette)
    if not _disabled_by_env("LATENCYLAB_UI_THEME_DISABLE_STYLESHEET"):
        app.setStyleSheet(build_stylesheet(tokens_for(theme)))

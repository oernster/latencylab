from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


_LIGHT_STYLESHEET = """
QWidget { font-size: 12px; }
QGroupBox { font-weight: 600; }
QStatusBar QLabel { padding-left: 6px; padding-right: 6px; }
""".strip()


_DARK_STYLESHEET = """
/* Keep it intentionally minimal: use a dark palette + light spacing tweaks only. */
QWidget { font-size: 12px; }
QGroupBox { font-weight: 600; }
QStatusBar QLabel { padding-left: 6px; padding-right: 6px; }
""".strip()


def _dark_palette() -> QPalette:
    """A conservative Fusion-friendly dark palette.

    This avoids per-widget overrides while still producing a true dark theme.
    """

    pal = QPalette()
    base = QColor(30, 30, 30)
    alt_base = QColor(40, 40, 40)
    text = QColor(220, 220, 220)
    disabled_text = QColor(140, 140, 140)
    button = QColor(45, 45, 45)
    highlight = QColor(42, 130, 218)

    pal.setColor(QPalette.ColorRole.Window, base)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    pal.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    pal.setColor(QPalette.ColorRole.ToolTipBase, text)
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(10, 10, 10))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, button)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    pal.setColor(QPalette.ColorRole.Highlight, highlight)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(10, 10, 10))

    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    pal.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text
    )
    return pal


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply an application-global theme.

    v1 intentionally uses an application stylesheet only, not per-widget overrides.
    """

    app.setStyle("Fusion")
    if theme == Theme.DARK:
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_STYLESHEET)
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet(_LIGHT_STYLESHEET)


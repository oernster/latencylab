from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


_PRIMARY_PURPLE = QColor(126, 87, 194)  # muted purple (Fusion-friendly)
_ACCENT_TEAL = QColor(38, 166, 154)  # hover/focus accent


_LIGHT_STYLESHEET = f"""
/* Global, restrained rules only. Theme colors come from palette + a small set of controls. */

QWidget {{
  font-size: 13px;
}}

QStatusBar QLabel {{
  padding-left: 6px;
  padding-right: 6px;
}}

QGroupBox {{
  font-weight: 600;
  border: 1px solid palette(mid);
  border-radius: 6px;
  margin-top: 10px;
  padding: 6px;
}}

QGroupBox::title {{
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 4px;
}}

QPushButton {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(250, 250, 250, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.10);
  border-radius: 6px;
  padding: 6px 10px;
}}

QPushButton:hover {{
  background-color: {_ACCENT_TEAL.name()};
}}

QPushButton:disabled {{
  background-color: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(0, 0, 0, 0.06);
}}

QPushButton[role="theme-toggle"] {{
  background-color: palette(button);
  color: palette(buttonText);
  border: 1px solid palette(mid);
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
}}

QPushButton[role="theme-toggle"]:checked {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(250, 250, 250, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.10);
}}

QPushButton[role="theme-toggle"]:hover {{
  background-color: {_ACCENT_TEAL.name()};
  color: rgba(250, 250, 250, 0.98);
}}

QPushButton[role="icon-action"] {{
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
  border-radius: 6px;
}}

QSpinBox,
QComboBox,
QPlainTextEdit {{
  border: 1px solid palette(mid);
  border-radius: 6px;
  min-height: 32px;
  padding: 6px 8px;
}}

QSpinBox {{
  /* Reserve space for the up/down buttons so they stay visible. */
  padding-right: 26px;
}}

QSpinBox::up-button,
QSpinBox::down-button {{
  width: 22px;
}}

QSpinBox:focus,
QComboBox:focus,
QPlainTextEdit:focus {{
  border: 1px solid {_ACCENT_TEAL.name()};
}}
""".strip()


_DARK_STYLESHEET = f"""
/* Keep it intentionally minimal: rely on a dark palette + restrained control rules only. */

QWidget {{
  font-size: 13px;
}}

QStatusBar QLabel {{
  padding-left: 6px;
  padding-right: 6px;
}}

QGroupBox {{
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  margin-top: 10px;
  padding: 6px;
}}

QGroupBox::title {{
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 4px;
}}

QPushButton {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(245, 245, 245, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  padding: 6px 10px;
}}

QPushButton:hover {{
  background-color: {_ACCENT_TEAL.name()};
}}

QPushButton:disabled {{
  background-color: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 245, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.06);
}}

QPushButton[role="theme-toggle"] {{
  background-color: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 245, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.10);
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
}}

QPushButton[role="theme-toggle"]:checked {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(245, 245, 245, 0.98);
  border: 1px solid rgba(0, 0, 0, 0.35);
}}

QPushButton[role="theme-toggle"]:hover {{
  background-color: {_ACCENT_TEAL.name()};
  color: rgba(245, 245, 245, 0.98);
}}

QPushButton[role="icon-action"] {{
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
  border-radius: 6px;
}}

QSpinBox,
QComboBox,
QPlainTextEdit {{
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 6px;
  min-height: 32px;
  padding: 6px 8px;
  background: palette(base);
}}

QSpinBox {{
  /* Reserve space for the up/down buttons so they stay visible. */
  padding-right: 26px;
}}

QSpinBox::up-button,
QSpinBox::down-button {{
  width: 22px;
}}

QSpinBox:focus,
QComboBox:focus,
QPlainTextEdit:focus {{
  border: 1px solid {_ACCENT_TEAL.name()};
}}
""".strip()


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

    app.setStyle("Fusion")
    if theme == Theme.DARK:
        app.setPalette(_dark_palette())
        app.setStyleSheet(_DARK_STYLESHEET)
    else:
        app.setPalette(_light_palette(app))
        app.setStyleSheet(_LIGHT_STYLESHEET)


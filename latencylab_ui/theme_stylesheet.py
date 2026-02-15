from __future__ import annotations

"""Application stylesheet definitions.

Separated from `theme.py` to keep modules small (repo guardrail: <= 400 lines).
"""

from PySide6.QtGui import QColor

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
  border: 2px solid rgba(0, 0, 0, 0.10);
  border-radius: 10px;
  padding: 6px 10px;
}}

QPushButton:focus {{
  border: 2px solid white;
}}

QPushButton:hover {{
  background-color: {_ACCENT_TEAL.name()};
}}

QPushButton:disabled {{
  background-color: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.45);
  border: 2px solid rgba(0, 0, 0, 0.06);
}}

QPushButton[role="theme-toggle"] {{
  background-color: palette(button);
  color: palette(buttonText);
  border: 2px solid palette(mid);
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
}}

QPushButton[role="theme-toggle"]:focus {{
  border: 2px solid white;
}}

QPushButton[role="theme-toggle"]:checked {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(250, 250, 250, 0.98);
  border: 2px solid rgba(0, 0, 0, 0.10);
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
  border-radius: 10px;
}}

/* Keep the Compose pill the same height as the adjacent icon-action buttons. */
QPushButton#compose_model_btn {{
  min-height: 34px;
  max-height: 34px;
  padding: 2px 10px;
}}

QSpinBox,
QComboBox,
QPlainTextEdit {{
  border: 1px solid palette(mid);
  border-radius: 6px;
  min-height: 32px;
  padding: 6px 8px;
}}

/* Popup item height/padding only (popup colors are palette-driven and enforced
   programmatically for deterministic rendering across platforms/styles). */
QComboBox QAbstractItemView::item {{
  min-height: 24px;
  padding: 4px 8px;
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
  border: 2px solid rgba(0, 0, 0, 0.35);
  border-radius: 10px;
  padding: 6px 10px;
}}

QPushButton:focus {{
  border: 2px solid white;
}}

QPushButton:hover {{
  background-color: {_ACCENT_TEAL.name()};
}}

QPushButton:disabled {{
  background-color: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 245, 0.45);
  border: 2px solid rgba(255, 255, 255, 0.06);
}}

QPushButton[role="theme-toggle"] {{
  background-color: rgba(255, 255, 255, 0.06);
  color: rgba(245, 245, 245, 0.85);
  border: 2px solid rgba(255, 255, 255, 0.10);
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
}}

QPushButton[role="theme-toggle"]:focus {{
  border: 2px solid white;
}}

QPushButton[role="theme-toggle"]:checked {{
  background-color: {_PRIMARY_PURPLE.name()};
  color: rgba(245, 245, 245, 0.98);
  border: 2px solid rgba(0, 0, 0, 0.35);
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
  border-radius: 10px;
}}

/* Keep the Compose pill the same height as the adjacent icon-action buttons. */
QPushButton#compose_model_btn {{
  min-height: 34px;
  max-height: 34px;
  padding: 2px 10px;
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

/* Popup item height/padding only (popup colors are palette-driven and enforced
   programmatically for deterministic rendering across platforms/styles). */
QComboBox QAbstractItemView::item {{
  min-height: 24px;
  padding: 4px 8px;
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


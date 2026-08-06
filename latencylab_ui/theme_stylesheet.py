from __future__ import annotations

"""The application stylesheet: ONE template, built per theme from its tokens.

There used to be two near-identical sheets kept in step by hand, which is how
the light theme ended up with rules the dark theme did not have. There is now a
single template and the only thing that varies is the token set, so a rule
written once is a rule both themes have.

Every focusable control follows the three-state ring model:

- 2px transparent border at rest, so gaining a ring never reflows the layout,
- `:enabled:hover` and `:enabled:focus` both paint the GREEN ring, deliberately
  identical, because both mean "you can use this",
- `:disabled` paints a permanent RED ring and mutes the fill to `panel` so the
  red reads against it.

Every hover and focus rule is gated on `:enabled`. An ungated `:hover` lights up
a dead control under the mouse, which says the opposite of what the red ring is
there to say. Note that `:disabled:hover` is unmatchable in Qt (the engine nests
hover under enabled), so the permanent form is both what is wanted and the only
form that can be expressed.

An object-name rule that sets `border` beats the generic `:enabled:focus` by id
specificity, so every object-name-styled control below carries its own ring
rules. Leaving them out is how a button ends up with no ring at all.
"""

from latencylab_ui.theme_tokens import DARK_TOKENS, LIGHT_TOKENS, ThemeTokens

_TEMPLATE = """
/* `outline: none` removes Qt's own dotted focus rectangle around a control's
   text. The ring IS the focus indicator, and two indicators read as a bug. */
QWidget {{
  font-size: 13px;
  outline: none;
}}

QToolTip {{
  background-color: {panel};
  color: {text};
  border: 1px solid {border};
  padding: 4px 6px;
  font-size: 13px;
}}

QStatusBar QLabel {{
  padding-left: 6px;
  padding-right: 6px;
}}

QGroupBox {{
  font-weight: 600;
  border: 1px solid {border};
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
  background-color: {primary};
  color: {primary_text};
  border: 2px solid transparent;
  border-radius: 10px;
  padding: 6px 10px;
}}

QPushButton:enabled:hover,
QPushButton:enabled:focus {{
  border-color: {ring};
}}

QPushButton:disabled {{
  background-color: {panel};
  color: {muted_text};
  border: 2px solid {danger};
}}

QPushButton[role="icon-action"] {{
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
  border-radius: 10px;
}}

/* The theme toggle is a single button that names the theme it will switch TO.
   It is never disabled, so it needs no danger rule of its own beyond the
   generic one. */
QPushButton[role="theme-toggle"] {{
  background-color: {panel};
  color: {text};
  font-size: 18px;
  min-width: 34px;
  min-height: 34px;
  padding: 2px 8px;
}}

/* Compose keeps the icon buttons' height, and its CHECKED state is the visible
   answer to "is the composer open". Object-name specificity means these ring
   rules have to be repeated here or the button shows none. */
QPushButton#compose_model_btn {{
  min-height: 34px;
  max-height: 34px;
  padding: 2px 10px;
}}

QPushButton#compose_model_btn:checked {{
  background-color: {accent};
  color: {primary_text};
}}

QPushButton#compose_model_btn:enabled:hover,
QPushButton#compose_model_btn:enabled:focus {{
  border-color: {ring};
}}

QPushButton#compose_model_btn:disabled {{
  background-color: {panel};
  color: {muted_text};
  border: 2px solid {danger};
}}

/* Inputs carry the same 2px transparent border as the buttons so that gaining
   a ring never moves them either. */
QSpinBox,
QComboBox,
QPlainTextEdit,
QTextBrowser {{
  background-color: {base};
  border: 2px solid {border};
  border-radius: 6px;
  min-height: 32px;
  padding: 6px 8px;
}}

QSpinBox:enabled:focus,
QComboBox:enabled:focus,
QPlainTextEdit:enabled:focus,
QTextBrowser:enabled:focus {{
  border-color: {ring};
}}

QSpinBox:disabled,
QComboBox:disabled,
QPlainTextEdit:disabled,
QTextBrowser:disabled {{
  background-color: {panel};
  color: {muted_text};
  border: 2px solid {danger};
}}

/* Popup item metrics only. The popup's colours are palette-driven and set
   programmatically, so that they render identically across platforms. */
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

/* A highlighted menu title or item is the keyboard ring passing through the
   menu bar, so it wears the same green. */
QMenuBar::item:selected,
QMenu::item:selected {{
  background-color: {panel};
  border: 1px solid {ring};
}}
"""


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Render the one template against one theme's tokens."""

    return _TEMPLATE.format(
        surface=tokens.surface,
        panel=tokens.panel,
        base=tokens.base,
        primary=tokens.primary,
        primary_text=tokens.primary_text,
        text=tokens.text,
        muted_text=tokens.muted_text,
        border=tokens.border,
        ring=tokens.ring,
        danger=tokens.danger,
        accent=tokens.accent,
    ).strip()


_DARK_STYLESHEET = build_stylesheet(DARK_TOKENS)
_LIGHT_STYLESHEET = build_stylesheet(LIGHT_TOKENS)

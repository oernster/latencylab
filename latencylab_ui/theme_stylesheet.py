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
  background-color: {elevated};
  color: {text};
  border: 1px solid {elevated_border};
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

/* A control that has just become usable, saying so. The same green as hover
   and focus on purpose: all three mean "you can use this", and a fourth colour
   would be a fourth thing to learn. Driven by `attention_flash`, which only
   ever sets this on an enabled control, so it cannot argue with the red. */
QPushButton[flash="true"] {{
  border-color: {ring};
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

/* Switched ON. The ink goes dark here and only here, because the accent is far
   too light to carry the near-white every other filled button uses. */
QPushButton#compose_model_btn:checked {{
  background-color: {accent};
  color: {accent_text};
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

/* The distributions toggle answers the same question from the other side: the
   two docks share the right-hand area, so at most one of this pair is checked.
   It carries the application's own mark rather than a drawn glyph, and a
   picture cannot be recoloured on check the way a stroke can, so the fill and
   the ink do all of the saying here. Declaring only those two leaves the
   generic ring rules in force rather than overriding them by id. */
QPushButton#distributions_btn:checked {{
  background-color: {accent};
  color: {accent_text};
}}

/* Inputs carry the same 2px transparent border as the buttons so that gaining
   a ring never moves them either.

   `QAbstractSpinBox` rather than `QSpinBox`, and `QLineEdit` named explicitly.
   A Qt type selector matches a class and its SUBCLASSES, and QDoubleSpinBox is
   a sibling of QSpinBox rather than a subclass, so a rule written for the one
   never reached the other: measured in the composer, a QSpinBox stood 51px tall
   beside a QDoubleSpinBox at 19px and a QLineEdit at 22px, three controls doing
   the same job at three heights. Anything a user types into belongs on this
   list. */
QAbstractSpinBox,
QComboBox,
QLineEdit,
QPlainTextEdit,
QTextBrowser {{
  background-color: {base};
  border: 2px solid {border};
  border-radius: 6px;
  min-height: 32px;
  padding: 6px 8px;
}}

/* A spin box and an editable combo CONTAIN a QLineEdit, so the rule above
   reaches inside them and would give the inner field its own border, padding
   and minimum height on top of the outer control's. The nested one is not a
   field in its own right, so it is reset to nothing and the container keeps
   the metrics. */
QAbstractSpinBox QLineEdit,
QComboBox QLineEdit {{
  background: transparent;
  border: none;
  border-radius: 0;
  min-height: 0;
  padding: 0;
}}

QAbstractSpinBox:enabled:focus,
QComboBox:enabled:focus,
QLineEdit:enabled:focus,
QPlainTextEdit:enabled:focus,
QTextBrowser:enabled:focus {{
  border-color: {ring};
}}

QAbstractSpinBox:disabled,
QComboBox:disabled,
QLineEdit:disabled,
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

QAbstractSpinBox {{
  /* Reserve space for the up/down buttons so they stay visible. */
  padding-right: 26px;
}}

QAbstractSpinBox::up-button,
QAbstractSpinBox::down-button {{
  width: 22px;
}}

/* The icon tray is a band, not controls floating on the window. Given the
   window's own colour and no edge, the row of buttons appeared to hover in the
   content area with nothing saying where the chrome stopped. Its own surface
   and a bottom border say it. */
QWidget#top_tray {{
  background-color: {panel};
  border-bottom: 1px solid {border};
}}

/* The menu bar is part of the window, so it shares its colour, and a rule of
   its own is still needed: without the bottom border the bar and the content
   below it are one undivided field. */
QMenuBar {{
  background-color: {surface};
  color: {text};
  border-bottom: 1px solid {border};
}}

QMenuBar::item {{
  background: transparent;
  padding: 4px 10px;
  border: 1px solid transparent;
  border-radius: 4px;
}}

/* A dropped menu FLOATS, so it gets the elevated surface and the strongest
   border in the set. Painted in the window colour with no border, which is
   what Qt does when nothing here says otherwise, a menu is indistinguishable
   from the window behind it and its items read as text lying on the page. */
QMenu {{
  background-color: {elevated};
  color: {text};
  border: 1px solid {elevated_border};
  border-radius: 6px;
  padding: 4px;
}}

QMenu::item {{
  background: transparent;
  padding: 5px 22px 5px 12px;
  border: 1px solid transparent;
  border-radius: 4px;
}}

QMenu::separator {{
  height: 1px;
  background-color: {elevated_border};
  margin: 4px 6px;
}}

/* A menu item that cannot be chosen is muted rather than ringed: the red ring
   belongs to controls the user aimed at, and every entry under an open menu is
   passed over on the way to another. */
QMenu::item:disabled {{
  color: {muted_text};
}}

/* A highlighted menu title or item is the keyboard ring passing through the
   menu bar, so it wears the same green. The fill lifts to the elevated surface
   as well, so the highlight survives a display where the ring is hard to see,
   and so a highlighted title matches the menu that drops from it. */
QMenuBar::item:selected,
QMenu::item:selected {{
  background-color: {elevated_hover};
  border: 1px solid {ring};
}}
"""


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Render the one template against one theme's tokens."""

    return _TEMPLATE.format(
        surface=tokens.surface,
        panel=tokens.panel,
        base=tokens.base,
        elevated=tokens.elevated,
        elevated_hover=tokens.elevated_hover,
        elevated_border=tokens.elevated_border,
        primary=tokens.primary,
        primary_text=tokens.primary_text,
        text=tokens.text,
        muted_text=tokens.muted_text,
        border=tokens.border,
        ring=tokens.ring,
        danger=tokens.danger,
        accent=tokens.accent,
        accent_text=tokens.accent_text,
    ).strip()


_DARK_STYLESHEET = build_stylesheet(DARK_TOKENS)
_LIGHT_STYLESHEET = build_stylesheet(LIGHT_TOKENS)

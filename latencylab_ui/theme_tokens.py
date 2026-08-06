from __future__ import annotations

"""Semantic colour tokens, one set per theme.

The stylesheet is built once from these, so the three-state ring model holds in
every theme by construction rather than by being re-checked per skin:

- at rest, an enabled control shows NO ring,
- while enabled and hovered OR keyboard-focused it shows the GREEN `ring`,
- while disabled it shows a permanent RED `danger` ring.

`accent` carries data meaning and the checked state of a toggle. It is never a
ring colour, because a ring drawn in the brand colour stops saying "you can use
this" and starts competing with everything else painted in it.

Light and dark need DIFFERENT greens and reds. A pastel green that reads well on
near-black is weak on white, so each theme names its own rather than sharing one
and hoping. Every value is a solid hex string with no alpha, so a rendered pixel
can be asserted against the token exactly.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Every colour the stylesheet is allowed to use."""

    # Surfaces. `panel` is what a control's own fill falls back to, and it must
    # differ from `surface`: a control filled with the window colour disappears
    # into the window.
    surface: str
    panel: str
    base: str
    alternate_base: str

    # Controls.
    primary: str
    primary_text: str
    text: str
    muted_text: str
    border: str

    # The three-state ring model, plus the brand accent.
    ring: str
    danger: str
    accent: str


DARK_TOKENS = ThemeTokens(
    surface="#1e1e1e",
    panel="#2b2b2b",
    base="#181818",
    alternate_base="#242424",
    primary="#7e57c2",
    primary_text="#f5f5f5",
    text="#e4e4e4",
    muted_text="#969696",
    border="#3a3a3a",
    ring="#34d399",
    danger="#f87171",
    accent="#26a69a",
)

LIGHT_TOKENS = ThemeTokens(
    surface="#f8f8f8",
    panel="#ececec",
    base="#ffffff",
    alternate_base="#f2f2f2",
    primary="#7e57c2",
    primary_text="#fafafa",
    text="#202020",
    muted_text="#828282",
    border="#c8c8c8",
    # Saturated rather than pastel: these sit against white.
    ring="#059669",
    danger="#dc2626",
    accent="#26a69a",
)

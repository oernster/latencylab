from __future__ import annotations

"""Semantic colour tokens, one set per theme.

The stylesheet is built once from these, so the three-state ring model holds in
every theme by construction rather than by being re-checked per skin:

- at rest, an enabled control shows NO ring,
- while enabled and hovered OR keyboard-focused it shows the GREEN `ring`,
- while disabled it shows a permanent RED `danger` ring.

`accent` is the brand colour: it marks a control that is switched ON and it
carries data meaning. It is never a ring colour, because a ring drawn in the
brand colour stops saying "you can use this" and starts competing with
everything else painted in it. Anything painted on top of it uses
`accent_text`, never the near-white the other filled controls use.

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

    # Anything that FLOATS above the window: menus and tooltips. They need a
    # surface of their own for the same reason a control does, and more
    # urgently, because a popup has no layout position to explain its edges. A
    # menu painted in the window colour with no border is not a subtle problem:
    # it is invisible, and the text appears to have been written onto the
    # window. `elevated_border` is deliberately the strongest edge in the set,
    # since it is the only thing separating a popup from whatever is behind it.
    elevated: str
    elevated_hover: str
    elevated_border: str

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

    # The ink that goes ON the accent. Near-black, and it has to be: the accent
    # is far too light to carry the near-white every other filled control uses,
    # and a filled state nobody can read is worse than no filled state at all.
    accent_text: str


DARK_TOKENS = ThemeTokens(
    surface="#1e1e1e",
    panel="#2b2b2b",
    base="#181818",
    alternate_base="#242424",
    # Lighter than the window rather than darker: a popup reads as nearer.
    elevated="#383838",
    elevated_hover="#4a4a4a",
    elevated_border="#5c5c5c",
    primary="#7e57c2",
    primary_text="#f5f5f5",
    text="#e4e4e4",
    muted_text="#969696",
    border="#3a3a3a",
    ring="#34d399",
    danger="#f87171",
    accent="#ffe135",
    accent_text="#1a1a1a",
)

LIGHT_TOKENS = ThemeTokens(
    surface="#f8f8f8",
    panel="#ececec",
    base="#ffffff",
    alternate_base="#f2f2f2",
    # White against an off-white window is a small fill difference, so here the
    # border does most of the separating and is set well darker than `border`.
    elevated="#ffffff",
    elevated_hover="#e2e2e2",
    elevated_border="#9a9a9a",
    primary="#7e57c2",
    primary_text="#fafafa",
    text="#202020",
    muted_text="#828282",
    border="#c8c8c8",
    # Saturated rather than pastel: these sit against white.
    ring="#059669",
    danger="#dc2626",
    # The same yellow in both themes, like `primary`. A filled block does not
    # need the per-theme adjustment the ring and danger colours do, because
    # those are lines drawn ON a surface and this covers one.
    accent="#ffe135",
    accent_text="#1a1a1a",
)

from __future__ import annotations

"""The two drawn control glyphs, and how they become icons.

Compose and Edit are the only two toolbar actions with no obvious emoji, and
picking a near-miss from the emoji set would have said something slightly wrong
in every font that renders it. They are drawn instead: a three-node event graph
with a plus for "make one of these", and a document with a pencil for "change
the one that is open".

Held as SVG SOURCE rather than as files in `assets/`, for two reasons. The
delivery paths already stage three directories across three platforms and this
adds nothing to stage. More importantly the colour is not fixed: a glyph drawn
once in near-white is invisible on the pale fill a disabled button takes in the
light theme, so it is rendered per use in a colour the caller supplies from the
theme's own tokens.

The viewBox is 24 units and the strokes are round-capped, so the pair sit
together at any size without one looking heavier than the other.
"""

from collections.abc import Callable

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

VIEWBOX = 24
STROKE_WIDTH = 1.9

_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" '
    'fill="none" stroke="{stroke}" stroke-width="{width}" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

# Every glyph here is two-tone, and they all split the same way: the part that
# merely sits there takes the button's ink, and the part that says what the
# button DOES takes the accent. The graph's nodes and its plus, the pencil, the
# book's ruled lines. A single-tone glyph on a filled button reads as a
# watermark, which is what these were before.

# The edges between the nodes: structure, so they stay in the ink.
_GRAPH_EDGES = '<path d="M7.1 8.1 L12.9 11"/><path d="M7.1 15.9 L12.9 13"/>'

# Three nodes and a plus: the shape of the thing being made, and the making.
_GRAPH_NODES = (
    '<circle cx="5" cy="7" r="2.2" stroke="{accent}"/>'
    '<circle cx="5" cy="17" r="2.2" stroke="{accent}"/>'
    '<circle cx="15" cy="12" r="2.2" stroke="{accent}"/>'
)
_COMPOSE_PLUS = '<path d="M19 4.5v5M16.5 7h5" stroke="{accent}"/>'

# The document is the thing being changed and the pencil is the changing, so
# the pencil is the half that carries the accent.
_EDIT_DOCUMENT = (
    '<path d="M13 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11'
    'a1.5 1.5 0 0 0 1.5-1.5V11"/>'
)
_EDIT_PENCIL = (
    '<path d="M19.8 2.8 L21.9 4.9 L14.6 12.2 L11.8 12.9 L12.5 10.1 Z" '
    'stroke="{accent}"/>'
)


def compose_body(*, accent: str) -> str:
    """The event graph, with its nodes and its plus in `accent`."""

    return _GRAPH_EDGES + (_GRAPH_NODES + _COMPOSE_PLUS).format(accent=accent)


def edit_body(*, accent: str) -> str:
    """The document, with its pencil in `accent`."""

    return _EDIT_DOCUMENT + _EDIT_PENCIL.format(accent=accent)


# An open book: a manual. It sits immediately left of the info button, so it
# deliberately shares no shape with an "i" in a circle; and its spine plus two
# curved pages read differently at 20px from Edit's rectangular document.
#
# Covers in the button's own ink and everything else in the accent, because a
# single-tone version came out as two blank curves: it said "a document" where
# it needed to say "a manual with something in it".
_GUIDE_COVERS = (
    '<path d="M12 7.2v12.4"/>'
    '<path d="M12 7.2C9.9 5.6 7 5.1 3.6 5.5v12.4c3.4-.4 6.3.1 8.4 1.7"/>'
    '<path d="M12 7.2c2.1-1.6 5-2.1 8.4-1.7v12.4c-3.4-.4-6.3.1-8.4 1.7"/>'
)

# Where the ruled lines sit. TWO rather than three: measured at the 20px the
# tray actually draws, a third line blurs into the two beside it and the page
# turns to mush, so the sense of several pages comes from the edge below
# instead, which has room to be seen.
_GUIDE_RULES = (9.6, 12.6)
_RULE_WIDTH = 1.3

# The near page's edge, showing the book has thickness rather than being two
# flat leaves.
_EDGE_OFFSET = 1.5
_EDGE_WIDTH = 1.1


def _guide_marks(accent: str) -> str:
    """The ruled lines and the page edge, all in one colour."""

    marks = []
    for y in _GUIDE_RULES:
        marks.append(
            f'<path stroke="{accent}" stroke-width="{_RULE_WIDTH}" '
            f'd="M5.6 {y}c1.5-.1 2.9.1 4.1.6"/>'
        )
        marks.append(
            f'<path stroke="{accent}" stroke-width="{_RULE_WIDTH}" '
            f'd="M18.4 {y}c-1.5-.1-2.9.1-4.1.6"/>'
        )
    edge_y = 17.9 + _EDGE_OFFSET
    marks.append(
        f'<path stroke="{accent}" stroke-width="{_EDGE_WIDTH}" '
        f'd="M3.6 {edge_y}c3.4-.4 6.3.1 8.4 1.7"/>'
    )
    marks.append(
        f'<path stroke="{accent}" stroke-width="{_EDGE_WIDTH}" '
        f'd="M20.4 {edge_y}c-3.4-.4-6.3.1-8.4 1.7"/>'
    )
    return "".join(marks)


def guide_body(*, accent: str) -> str:
    """The book, with its marks in `accent` and its covers left to the head."""

    return _GUIDE_COVERS + _guide_marks(accent)


def glyph_svg(body: str, *, stroke: str) -> str:
    """One glyph's complete SVG, drawn in `stroke`."""

    head = _HEAD.format(box=VIEWBOX, stroke=stroke, width=STROKE_WIDTH)
    return f"{head}{body}</svg>"


def glyph_pixmap(body: str, *, stroke: str, size: int) -> QPixmap:
    """Render one glyph at `size` square, transparent behind it."""

    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(glyph_svg(body, stroke=stroke).encode("utf-8")).render(
        painter, QRectF(0, 0, size, size)
    )
    painter.end()
    return pixmap


def two_tone_icon(
    body_of: Callable[..., str],
    *,
    ink: str,
    accent: str,
    disabled: str,
    size: int,
    checked_ink: str | None = None,
) -> QIcon:
    """A two-tone glyph carrying every state, so Qt never invents one.

    Left to itself Qt greys the normal pixmap, which on a disabled button that
    has ALSO changed its fill can land the glyph and the fill at nearly the same
    lightness. Supplying the disabled pixmap keeps that decision with the theme,
    and disabled mutes BOTH tones rather than only the structure: a glyph that
    keeps its accent while the rest of it greys out reads as half-available,
    which is not a state this application has.

    `checked_ink` exists because a stylesheet cannot reach inside an icon. A
    checked button changes its fill to the light accent and its TEXT to that
    accent's dark ink; a glyph baked in near-white simply stays near-white on
    top of it, and its accent half stops being an accent at all, because the
    fill it was standing out against is now that same colour. So both tones
    collapse to the one ink that reads there. Anything checkable whose checked
    fill is light has to supply this or the icon disappears at exactly the
    moment it means something.
    """

    checked_stroke = ink if checked_ink is None else checked_ink
    checked_accent = accent if checked_ink is None else checked_ink

    icon = QIcon()
    icon.addPixmap(
        glyph_pixmap(body_of(accent=accent), stroke=ink, size=size),
        QIcon.Mode.Normal,
        QIcon.State.Off,
    )
    icon.addPixmap(
        glyph_pixmap(body_of(accent=checked_accent), stroke=checked_stroke, size=size),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    icon.addPixmap(
        glyph_pixmap(body_of(accent=disabled), stroke=disabled, size=size),
        QIcon.Mode.Disabled,
    )
    return icon

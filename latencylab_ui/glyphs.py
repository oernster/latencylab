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

# Three nodes and the edges between them: the shape of the thing being made.
_GRAPH = (
    '<circle cx="5" cy="7" r="2.2"/>'
    '<circle cx="5" cy="17" r="2.2"/>'
    '<circle cx="15" cy="12" r="2.2"/>'
    '<path d="M7.1 8.1 L12.9 11"/>'
    '<path d="M7.1 15.9 L12.9 13"/>'
)

COMPOSE_BODY = _GRAPH + '<path d="M19 4.5v5M16.5 7h5"/>'

EDIT_BODY = (
    '<path d="M13 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11'
    'a1.5 1.5 0 0 0 1.5-1.5V11"/>'
    '<path d="M19.8 2.8 L21.9 4.9 L14.6 12.2 L11.8 12.9 L12.5 10.1 Z"/>'
)


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


def glyph_icon(
    body: str,
    *,
    stroke: str,
    disabled_stroke: str,
    size: int,
    checked_stroke: str | None = None,
) -> QIcon:
    """An icon carrying every state, so Qt never invents one.

    Left to itself Qt greys the normal pixmap, which on a disabled button that
    has ALSO changed its fill can land the glyph and the fill at nearly the same
    lightness. Supplying the disabled pixmap keeps that decision with the theme.

    `checked_stroke` exists because a stylesheet cannot reach inside an icon.
    A checked button changes its fill to the accent and its TEXT to the accent's
    dark ink, and a glyph baked in near-white simply stays near-white on top of
    it. Anything checkable whose checked fill is light has to supply this or the
    icon disappears at exactly the moment it means something.
    """

    icon = QIcon()
    normal = glyph_pixmap(body, stroke=stroke, size=size)
    icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(
        (
            normal
            if checked_stroke is None
            else glyph_pixmap(body, stroke=checked_stroke, size=size)
        ),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    icon.addPixmap(
        glyph_pixmap(body, stroke=disabled_stroke, size=size), QIcon.Mode.Disabled
    )
    return icon

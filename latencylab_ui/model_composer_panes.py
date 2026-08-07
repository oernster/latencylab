from __future__ import annotations

"""Assembling the composer's two panes, and sizing the window they sit in.

Split out of the dialog for the reason every other composer module was: the
dialog holds the model's state and the rules around it, and this holds where
things are put. Neither is improved by being read through the other.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.model_composer_tree import SECTIONS

# What a page's content is inset by, matching the old column so the editors are
# not suddenly tighter against an edge than they were.
PAGE_MARGIN = 10

# The panes' opening split. The list names things and the editor edits them, so
# the editor gets the room; the splitter is there for anyone who disagrees.
TREE_PANE_W = 260
DETAIL_PANE_W = 720

# Small enough to fit a modest laptop screen, large enough that the editor pane
# is not itself a scrolling column, which is the thing this replaced.
MIN_WIDTH = 900
MIN_HEIGHT = 600

# Modelling wants room. The dialog opens at nearly the whole application window,
# or nearly the whole screen when it has no parent to measure against.
PARENT_FILL = 0.95
SCREEN_FILL = 0.90


def initial_size(parent: QWidget | None) -> QSize:
    """How large to open, measured against whatever there is to measure."""

    if parent is not None:
        source = parent.size()
        fill = PARENT_FILL
    else:
        screen = QGuiApplication.primaryScreen()
        if screen is None:  # pragma: no cover - a screen always exists in Qt
            return QSize(MIN_WIDTH, MIN_HEIGHT)
        source = screen.availableGeometry().size()
        fill = SCREEN_FILL
    return QSize(
        max(MIN_WIDTH, int(source.width() * fill)),
        max(MIN_HEIGHT, int(source.height() * fill)),
    )


def scrolling_page(inner: QWidget) -> QScrollArea:
    """One editor, in a panel that scrolls if the window is small enough.

    The body is `MinimumExpanding` rather than `Maximum`. `Maximum` reads as
    "no taller than it needs" and means "may be made SHORTER than it needs", so
    a resizable scroll area hands the body the viewport's height instead of its
    own and the starvation reaches all the way down to individual controls
    drawn under their own minimum.
    """

    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    holder = QWidget(area)
    holder.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
    )
    layout = QVBoxLayout(holder)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.addWidget(inner)
    layout.addStretch(1)

    area.setWidget(holder)
    return area


def build_panes(
    tree: QWidget, pages: dict[str, QWidget]
) -> tuple[QSplitter, QStackedWidget]:
    """The list on the left, the editor for one thing on the right.

    The stack is built from `SECTIONS` rather than from the caller's dict order,
    so the page indices and the tree's rows come from the same one statement of
    what a model is made of.
    """

    stack = QStackedWidget()
    for key, _label in SECTIONS:
        stack.addWidget(scrolling_page(pages[key]))

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(tree)
    splitter.addWidget(stack)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([TREE_PANE_W, DETAIL_PANE_W])
    # The list is a fixed set of sections plus a task per row: collapsing it
    # would leave the editor with no way back to anything else.
    splitter.setChildrenCollapsible(False)
    return splitter, stack


def page_index(key: str) -> int:
    """Where a section's page sits in the stack, from the same one list."""

    return [section for section, _label in SECTIONS].index(key)

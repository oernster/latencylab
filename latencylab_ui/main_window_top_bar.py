from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from latencylab_ui import main_window_actions as actions
from latencylab_ui.glyphs import compose_body, edit_body, guide_body, two_tone_icon
from latencylab_ui.guide_text import GUIDE_TITLE
from latencylab_ui.icon_resolver import get_app_icon_png_path
from latencylab_ui.theme import Theme, tokens_for
from latencylab_ui.theme_toggle import ThemeToggle

TOOLBAR_BUTTON_PX = 34

# The glyph inside a toolbar button, leaving room for the 2px ring and the
# button's own padding without crowding either.
GLYPH_PX = 20

# The tray is a band of its own rather than controls floating on the window.
# The stylesheet gives it a surface and a bottom edge; it needs a name to be
# addressed by, plus vertical padding so the band reads as a band.
TRAY_OBJECT_NAME = "top_tray"
TRAY_PAD_Y = 6

# Named so the stylesheet can say what CHECKED looks like on it. The name is
# shared with the sheet rather than written out twice.
DISTRIBUTIONS_BUTTON_NAME = "distributions_btn"

# The application mark, in the middle of the bar. Painted from the generated
# icon set rather than an emoji glyph, so the mark in the bar, the mark in the
# taskbar, the mark on the shortcut and the mark in About are all one file.
TOP_BADGE_PX = 36

# The mark is the centrepiece, so it is drawn a little larger than the glyphs
# flanking it, while still fitting inside a button of the tray's own height.
CENTRE_MARK_PX = 24

# Ask for a larger source and scale it down: downscaling a slightly-too-big icon
# looks better than upscaling a slightly-too-small one.
_MARK_SOURCE_PX = 64

MARGIN_SIDE = 10
BUTTON_SPACING = 8


class NavBand(QWidget):
    """The tray, which knows the order its own controls are READ in.

    The mark is an overlay sharing one grid cell with the row of buttons,
    because centring on the BAR cannot be done with a row of stretches. Layout
    order therefore reaches every button first and the mark last, so the ring
    stepped from the leftmost button all the way to the theme toggle at the far
    right and only THEN back to the mark in the middle. The one control on the
    bar nobody can miss with their eye was the last one the keyboard offered,
    which is indistinguishable from the ring having skipped it.

    A container whose layout is deliberately not in reading order has to state
    the reading order itself rather than leave it to be inferred.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._ring_stops: tuple[QWidget, ...] = ()

    def set_ring_stops(self, stops: tuple[QWidget, ...]) -> None:
        self._ring_stops = stops

    def ring_stops(self) -> tuple[QWidget, ...]:
        """Left to right as drawn, which is not the order the layout holds."""

        return self._ring_stops


@dataclass(frozen=True, slots=True)
class TopBar:
    """The top bar and every control on it the window needs to reach later."""

    widget: NavBand
    save_log_btn: QPushButton
    distributions_btn: QPushButton
    guide_btn: QPushButton
    how_to_read_btn: QPushButton
    compose_btn: QPushButton
    edit_btn: QPushButton
    theme_toggle: ThemeToggle


def _build_centre_mark(
    parent: QWidget, *, tooltip: str, on_clicked: Callable[[], None]
) -> QPushButton:
    """The application mark, dead centre, doubling as the distributions toggle.

    It was decoration and is now the control, which is the same widget doing a
    job instead of sitting there: the mark is the most prominent thing on the
    bar and the panel it opens is the point of running anything, so the two
    belong together rather than competing for attention from opposite ends.

    The height is fixed and the WIDTH is left natural. Fixing both to a size
    smaller than the frame the stylesheet computes makes Qt lay the frame out at
    its natural size and clip it at the widget edge, which slices the bottom
    border off and leaves a ring that stops short. A minimum width holds the
    centre steady if the icon set is ever missing, since a mark that collapses
    would move the thing it is supposed to centre.
    """

    mark = QPushButton(parent)
    mark.setObjectName(DISTRIBUTIONS_BUTTON_NAME)
    mark.setProperty("role", "icon-action")
    mark.setFixedHeight(TOOLBAR_BUTTON_PX)
    mark.setMinimumWidth(TOP_BADGE_PX)
    mark.setToolTip(tooltip)
    mark.setCheckable(True)
    mark.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    mark.clicked.connect(on_clicked)

    mark_path = get_app_icon_png_path(_MARK_SOURCE_PX)
    if mark_path is not None:
        mark.setIcon(_mark_icon(QPixmap(str(mark_path))))
        mark.setIconSize(QSize(CENTRE_MARK_PX, CENTRE_MARK_PX))
    return mark


def _mark_icon(source: QPixmap) -> QIcon:
    """The mark, plus a second rendering of it for the checked state.

    The mark's hands and hub are banana and the checked fill is banana, so on
    its own the mark loses them at exactly the moment the button is saying
    something. Measured at the 24px the bar draws, the same 74% of the mark
    clears both fills by luminance; it is not the same 74%: on the blue fill the
    quarter that does not clear is the case, which is warm against a cool fill
    and so is separated by hue instead, while on the banana fill it is the
    hands, which are that same yellow and therefore genuinely gone. A
    stylesheet cannot reach inside an icon, so the second rendering is the same
    answer the drawn glyphs already use, in the same ink.
    """

    icon = QIcon()
    icon.addPixmap(source, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(
        _inked(source, tokens_for(Theme.DARK).accent_text),
        QIcon.Mode.Normal,
        QIcon.State.On,
    )
    return icon


def _inked(source: QPixmap, colour: str) -> QPixmap:
    """The same shape in one flat colour, keeping its alpha.

    The mark is strokes rather than a solid body, so flattening it reads as the
    same stopwatch drawn in a different ink rather than as a blob of its
    outline.
    """

    out = QPixmap(source.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), QColor(colour))
    painter.end()
    return out


def _icon_button(
    glyph: str, *, tooltip: str, on_clicked: Callable[[], None]
) -> QPushButton:
    button = QPushButton(glyph)
    button.setToolTip(tooltip)
    button.setProperty("role", "icon-action")
    button.setFixedHeight(TOOLBAR_BUTTON_PX)
    button.clicked.connect(on_clicked)
    return button


def _glyph_button(
    icon: QIcon, *, tooltip: str, on_clicked: Callable[[], None]
) -> QPushButton:
    """A toolbar button carrying an already-drawn icon."""

    button = QPushButton()
    button.setIcon(icon)
    button.setIconSize(QSize(GLYPH_PX, GLYPH_PX))
    button.setToolTip(tooltip)
    button.setProperty("role", "icon-action")
    button.setFixedHeight(TOOLBAR_BUTTON_PX)
    button.clicked.connect(on_clicked)
    return button


def _drawn_icon_button(
    body_of: Callable[..., str],
    *,
    tooltip: str,
    on_clicked: Callable[[], None],
    checkable: bool = False,
) -> QPushButton:
    """A toolbar button carrying a drawn two-tone glyph rather than an emoji.

    The colours come from the dark theme's tokens because the button fill is
    the same blue in both themes, so one rendering serves both and the glyph
    never has to be redrawn on a theme switch.
    """

    tokens = tokens_for(Theme.DARK)
    return _glyph_button(
        two_tone_icon(
            body_of,
            ink=tokens.primary_text,
            accent=tokens.accent,
            disabled=tokens.muted_text,
            # A checked button's fill is the light accent, so its glyph takes
            # the accent's dark ink. Without it the icon stays near-white and
            # vanishes at the moment the button is saying something.
            checked_ink=tokens.accent_text if checkable else None,
            size=GLYPH_PX,
        ),
        tooltip=tooltip,
        on_clicked=on_clicked,
    )


def build_top_bar(
    parent: QWidget,
    *,
    on_save_log_clicked: Callable[[], None],
    on_show_distributions_clicked: Callable[[], None],
    on_show_guide_clicked: Callable[[], None],
    on_show_how_to_read_clicked: Callable[[], None],
    on_toggle_model_composer_clicked: Callable[[], None],
    on_edit_model_clicked: Callable[[], None],
    on_theme_changed: Callable[[Theme], None],
) -> TopBar:
    """Build the top bar: actions at the edges, the app mark dead centre.

    The mark is centred on the BAR, which a row of stretches cannot do. Three
    stretches centre it in the space LEFT OVER between the flanking groups, and
    those groups are nowhere near the same width, so it lands well right of
    centre (134px out of 1400, measured). Equalising two grid columns by stretch
    does not work either, because a column never shrinks below its own content.

    What does work is an overlay: the controls and the mark occupy the SAME grid
    cell, that cell is the whole bar, then the mark centres itself in it. The
    mark is added second, so it is the one that takes a click where they meet.
    """

    top_bar = NavBand(parent)
    top_bar.setObjectName(TRAY_OBJECT_NAME)
    grid = QGridLayout(top_bar)
    grid.setContentsMargins(MARGIN_SIDE, TRAY_PAD_Y, MARGIN_SIDE, TRAY_PAD_Y)

    controls = QWidget(top_bar)
    layout = QHBoxLayout(controls)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(BUTTON_SPACING)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    save_log_btn = _icon_button(
        "💾", tooltip="Export runs as zip…", on_clicked=on_save_log_clicked
    )
    layout.addWidget(save_log_btn, 0, Qt.AlignmentFlag.AlignTop)

    # Immediately left of the info button, because the pair is one idea in two
    # halves: this one says which button to press, that one says what the
    # output means.
    guide_btn = _drawn_icon_button(
        guide_body, tooltip=GUIDE_TITLE, on_clicked=on_show_guide_clicked
    )
    guide_btn.setObjectName("guide_btn")
    guide_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout.addWidget(guide_btn, 0, Qt.AlignmentFlag.AlignTop)

    how_to_read_btn = _icon_button(
        "ℹ️",
        tooltip="How to Read LatencyLab Output",
        on_clicked=on_show_how_to_read_clicked,
    )
    how_to_read_btn.setObjectName("how_to_read_btn")
    layout.addWidget(how_to_read_btn, 0, Qt.AlignmentFlag.AlignTop)

    compose_btn = _drawn_icon_button(
        compose_body,
        tooltip=actions.COMPOSE_READY,
        on_clicked=on_toggle_model_composer_clicked,
    )
    compose_btn.setObjectName("compose_model_btn")
    # Not checkable. It was, back when it toggled a dock that shared the window
    # with the results, so the button was the only thing saying which of the two
    # was up. The composer is a modal dialog now: while it is open it IS the
    # window; a button reporting that from underneath it says nothing.
    compose_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout.addWidget(compose_btn, 0, Qt.AlignmentFlag.AlignTop)

    edit_btn = _drawn_icon_button(
        edit_body,
        tooltip=actions.EDIT_NEEDS_MODEL,
        on_clicked=on_edit_model_clicked,
    )
    edit_btn.setObjectName("edit_model_btn")
    edit_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignTop)

    layout.addStretch(1)

    theme_toggle = ThemeToggle(default=Theme.DARK, parent=parent)
    theme_toggle.theme_changed.connect(on_theme_changed)
    layout.addWidget(theme_toggle, 0, Qt.AlignmentFlag.AlignTop)

    distributions_btn = _build_centre_mark(
        top_bar,
        tooltip=actions.DISTRIBUTIONS_NEEDS_OUTPUTS,
        on_clicked=on_show_distributions_clicked,
    )

    grid.addWidget(controls, 0, 0)
    grid.addWidget(
        distributions_btn,
        0,
        0,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
    )

    # Left to right as the bar is drawn: the action group, then the mark in the
    # middle, then the theme toggle on the far right. Stated here because this
    # is the one place every control is in hand at once. It is asserted against
    # the band's real children by a test, so adding a button and forgetting this
    # line fails the suite rather than quietly dropping it off the ring.
    top_bar.set_ring_stops(
        (
            save_log_btn,
            guide_btn,
            how_to_read_btn,
            compose_btn,
            edit_btn,
            distributions_btn,
            theme_toggle,
        )
    )

    return TopBar(
        widget=top_bar,
        save_log_btn=save_log_btn,
        distributions_btn=distributions_btn,
        guide_btn=guide_btn,
        how_to_read_btn=how_to_read_btn,
        compose_btn=compose_btn,
        edit_btn=edit_btn,
        theme_toggle=theme_toggle,
    )

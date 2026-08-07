from __future__ import annotations

from PySide6.QtGui import QBrush, QPalette
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget

# How many rows a table shows before it starts scrolling on its own. Beyond
# this it would be taking the whole panel and pushing everything below it out
# of reach, which is a worse failure than a short scroll inside the table.
# A row is as tall as the controls in it, and the themed inputs are around 50px,
# so this is a claim about how much of a panel one table may occupy rather than
# a count that can be raised for free.
MAX_VISIBLE_TABLE_ROWS = 5


def _apply_combo_model_roles(combo: QComboBox) -> None:
    """Force per-item foreground/background roles to match the combo palette.

    Why: With an application-wide stylesheet installed, Qt can route painting
    through QStyleSheetStyle. In that mode, some popup views may end up drawing
    item text using the style's default (often black) rather than the palette's
    `Text` role, yielding near-invisible items on dark backgrounds.

    Setting model roles makes the delegate paint with explicit brushes.
    """

    model = combo.model()
    if model is None:
        return

    try:
        rows = int(model.rowCount())
    except Exception:  # noqa: BLE001
        return

    pal = combo.palette()
    fg = QBrush(pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text))

    col = int(combo.modelColumn())
    for r in range(max(0, rows)):
        idx = model.index(r, col)
        # Best-effort; not all models accept writes.
        try:
            model.setData(idx, fg, Qt.ItemDataRole.ForegroundRole)
            # Do NOT force BackgroundRole.
            #
            # BackgroundRole can interfere with Qt's own hover/selection
            # painting (e.g. causing HighlightedText to be used against the
            # Base background), which is a common cause of "black text" on a
            # dark popup.
            #
            # Popup background is instead controlled by the view/viewport
            # palette + autofill.
        except Exception:  # noqa: BLE001
            return


def _bind_combo_popup_palette(combo: QComboBox) -> None:
    """Bind popup view + viewport palette to the combo palette deterministically.

    Must be safe to call repeatedly, including at popup show-time.
    """

    view = combo.view()
    if view is None:
        return

    src = combo.palette()

    # Note: QComboBox popups are item views inside a QAbstractScrollArea; the
    # actual painting happens on the viewport widget, so we set palette +
    # autofill on both.
    view.setAutoFillBackground(True)
    view.setPalette(src)

    vp = view.viewport()
    if vp is not None:
        vp.setAutoFillBackground(True)
        vp.setPalette(src)

    # Ensure visible roles across all color groups. Some styles/platforms can
    # end up using WindowText/ButtonText rather than Text for delegates.
    pal = view.palette()
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        pal.setColor(
            group, QPalette.ColorRole.Text, src.color(group, QPalette.ColorRole.Text)
        )
        pal.setColor(
            group,
            QPalette.ColorRole.WindowText,
            src.color(group, QPalette.ColorRole.WindowText),
        )
        pal.setColor(
            group,
            QPalette.ColorRole.ButtonText,
            src.color(group, QPalette.ColorRole.ButtonText),
        )
        pal.setColor(
            group, QPalette.ColorRole.Base, src.color(group, QPalette.ColorRole.Base)
        )
        pal.setColor(
            group,
            QPalette.ColorRole.Window,
            src.color(group, QPalette.ColorRole.Window),
        )
        pal.setColor(
            group,
            QPalette.ColorRole.Highlight,
            src.color(group, QPalette.ColorRole.Highlight),
        )

        # Use normal Text color for HighlightedText (see harden_combobox_popup
        # rationale below).
        pal.setColor(
            group,
            QPalette.ColorRole.HighlightedText,
            src.color(group, QPalette.ColorRole.Text),
        )

        # The popup FLOATS, so it is painted on the elevated surface rather
        # than on the same Base as the closed combo. Copying Base straight
        # across is what the rest of this function does and it is wrong here:
        # measured in the dark theme, it put the open list within six levels of
        # luminance of the window behind it, which is the same invisibility the
        # menus had. `elevated` rides on ToolTipBase; see `theme._apply_common_palette`.
        elevated = src.color(group, QPalette.ColorRole.ToolTipBase)
        pal.setColor(group, QPalette.ColorRole.Base, elevated)
        pal.setColor(group, QPalette.ColorRole.Window, elevated)

    view.setPalette(pal)
    if vp is not None:
        vp.setPalette(pal)


class _ComboPopupHardenerFilter(QObject):
    """Always-on show-time hardener for QComboBox popups.

    Rationale: Qt popups can be re-polished at show-time and may lose palette
    bindings or model roles due to stylesheet/style interactions and late model
    population. We therefore re-assert palette + roles at *every* popup show.
    """

    def __init__(self, combo: QComboBox) -> None:
        super().__init__(combo)
        self._combo = combo

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show:
            combo = self._combo

            # Re-assert palette at show-time (after Qt polish / stylesheet).
            # Important: this must apply the *hardened* palette roles, not just
            # the raw combo palette.
            _bind_combo_popup_palette(combo)

            # Force model roles to prevent invisible text.
            _apply_combo_model_roles(combo)

        return False


def harden_combobox_popup(combo: QComboBox) -> None:
    """Make QComboBox popups render deterministically under Fusion + palette.

    Motivation: Qt combo popups are separate widgets (views) and can end up with
    unexpected palette roles when a global stylesheet is active, particularly
    with the Fusion style on Windows.

    We avoid styling popup colors via CSS and instead bind the popup view's
    palette roles to the combo/application palette.
    """

    combo.setEditable(False)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    combo.setMinimumHeight(26)

    # Bind popup to a hardened palette immediately (and also at show-time via
    # the installed event filter).
    _bind_combo_popup_palette(combo)

    # Always-on show-time hardener.
    #
    # Important: In production we must *not* rely on model signals firing or
    # the initial construction-time palette binding to survive Qt polish.
    view = combo.view()
    if view is None:
        return

    vp = view.viewport()
    if not hasattr(view, "_ll_combo_popup_hardener_filter"):
        hardener = _ComboPopupHardenerFilter(combo)
        view.installEventFilter(hardener)
        if vp is not None:
            vp.installEventFilter(hardener)
        # Prevent GC; PySide widgets allow arbitrary Python attrs.
        view._ll_combo_popup_hardener_filter = hardener  # type: ignore[attr-defined]

    # Apply explicit per-item model roles to avoid stylesheet-driven palette
    # fallbacks that can render items effectively invisible.
    _apply_combo_model_roles(combo)

    model = combo.model()
    if model is not None and not getattr(model, "_ll_combo_role_hooked", False):

        def _refresh_roles(*_args) -> None:
            _apply_combo_model_roles(combo)

        try:
            model.modelReset.connect(_refresh_roles)
            model.rowsInserted.connect(_refresh_roles)
            model.dataChanged.connect(_refresh_roles)
        except Exception:  # noqa: BLE001
            pass
        model._ll_combo_role_hooked = True  # type: ignore[attr-defined]

    # Debug-only instrumentation removed.


def stretch_table_columns(table: QTableWidget, stretch_column: int) -> None:
    """Give one column the slack and size the others to what they hold.

    A table left on Qt's default column width paints every column the same
    fixed width whatever is in it, so a long name is clipped inside its cell
    while the space it needed sits empty further along the same row. Nothing
    scrolls, because the columns together are NARROWER than the viewport: the
    text is simply cut, and there is no scrollbar to suggest otherwise.
    """

    header = table.horizontalHeader()
    for column in range(table.columnCount()):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if column == stretch_column
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(column, mode)


def fit_rows_to_contents(table: QTableWidget) -> None:
    """Let a row be as tall as the tallest thing in it.

    Qt's default row height is a constant that knows nothing about the cell
    widgets put into it, and the themed inputs are taller than it: a spin box
    asking for 51px was drawn into a 30px row, so its lower half including the
    DOWN button fell outside the row and was never painted. The number then sat
    against the bottom of what was left and read as badly aligned, which is the
    same fault described from the other side. Deriving the height removes both,
    and it keeps deriving it if the theme's control metrics ever change.
    """

    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)


def _settled_row_height(table: QTableWidget, row: int) -> int:
    """How tall a row WILL be, rather than how tall it currently reads.

    A header on `ResizeToContents` recalculates lazily, so straight after a row
    is filled `rowHeight()` still reports the old default and a table measured
    then comes out short by whatever has not been recalculated yet. In that mode
    the content hint is the authoritative answer and it is available at once.
    Under any other mode the row's height is a setting rather than a
    consequence, so the setting is what counts.
    """

    mode = table.verticalHeader().sectionResizeMode(row)
    if mode == QHeaderView.ResizeMode.ResizeToContents:
        return table.sizeHintForRow(row)
    return table.rowHeight(row)


def size_table_to_rows(
    table: QTableWidget, max_visible_rows: int = MAX_VISIBLE_TABLE_ROWS
) -> None:
    """Give a table the height its rows actually need, up to the cap.

    Qt's size hint for a scroll area is a constant that has never looked at the
    model, so a two-row table asked for exactly as much room as a twenty-row
    one. Both readings were wrong in opposite directions: the short table
    reserved empty space, and the long one truncated to a scrollbar of its own
    inside a panel that was already scrolling. Two nested scrolling surfaces
    are what made the panel feel stuck, since the inner one silently absorbed
    the wheel meant for the outer.

    Call it after any change to the row count, because the height is a fact
    about the contents and the contents are what change.
    """

    visible_rows = min(table.rowCount(), max_visible_rows)
    rows = sum(_settled_row_height(table, row) for row in range(visible_rows))
    chrome = table.horizontalHeader().sizeHint().height() + 2 * table.frameWidth()
    wanted = rows + chrome
    # Only when it differs, because this is driven by the signals that fire when
    # rows change and resizing the table is itself a change.
    if table.height() != wanted:
        table.setFixedHeight(wanted)

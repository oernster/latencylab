from __future__ import annotations

from PySide6.QtGui import QBrush, QPalette
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox


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
        pal.setColor(group, QPalette.ColorRole.Text, src.color(group, QPalette.ColorRole.Text))
        pal.setColor(group, QPalette.ColorRole.WindowText, src.color(group, QPalette.ColorRole.WindowText))
        pal.setColor(group, QPalette.ColorRole.ButtonText, src.color(group, QPalette.ColorRole.ButtonText))
        pal.setColor(group, QPalette.ColorRole.Base, src.color(group, QPalette.ColorRole.Base))
        pal.setColor(group, QPalette.ColorRole.Window, src.color(group, QPalette.ColorRole.Window))
        pal.setColor(group, QPalette.ColorRole.Highlight, src.color(group, QPalette.ColorRole.Highlight))

        # Use normal Text color for HighlightedText (see harden_combobox_popup
        # rationale below).
        pal.setColor(group, QPalette.ColorRole.HighlightedText, src.color(group, QPalette.ColorRole.Text))

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

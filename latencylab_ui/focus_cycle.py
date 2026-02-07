from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QAbstractSpinBox,
    QComboBox,
    QLayout,
    QMainWindow,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QWidget,
)


class FocusCycleController(QObject):
    """Enforce a deterministic keyboard focus cycle for a specific window.

    Rules implemented:
    - Pre-Tab: no child widget focused; no menu title selected.
    - First Tab: selects the first top-level menu title (left-to-right).
    - Then: cycle through interactive controls (excluding text areas), using
      layout insertion order (which corresponds to left-to-right, then
      top-to-bottom for this UI).
    - Tab / Right advance; Shift+Tab / Left go backwards.
    - Wrap in both directions.
    - Skip disabled/hidden controls.
    """

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._focus_cycle_started = False
        self._installed = False

    def install(self) -> None:
        if self._installed:  # pragma: no cover
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Ensure we reliably uninstall even if the owner is destroyed without
        # a clean closeEvent path (e.g., some unit tests).
        self._window.destroyed.connect(lambda *_a: self.uninstall())

        self._installed = True

        self._window.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._window.menuBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ensure_initial_state()

    def uninstall(self) -> None:
        if not getattr(self, "_installed", False):  # pragma: no cover
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._installed = False

    def ensure_initial_state(self) -> None:
        """Reset to the expected pre-Tab state."""

        self._focus_cycle_started = False
        self._window.menuBar().setActiveAction(None)

        fw = QApplication.focusWidget()
        if fw is not None and fw is not self._window and fw.window() is self._window:
            fw.clearFocus()

        self._window.setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        # During interpreter shutdown / QObject teardown, Python attributes may
        # be cleared while Qt can still invoke this callback. Never raise.
        try:
            window = self._window
            installed = self._installed
        except AttributeError:
            return False

        if not installed:
            return False

        # Qt may invoke eventFilter after the owner window has been deleted.
        # Accessing it would raise RuntimeError.
        try:
            _ = window.isVisible()
        except RuntimeError:
            # Best-effort uninstall; swallow any errors.
            try:
                self.uninstall()
            except Exception:  # noqa: BLE001
                pass
            return False  # pragma: no cover

        if not window.isVisible():
            return super().eventFilter(watched, event)

        if event.type() != event.Type.KeyPress:
            return super().eventFilter(watched, event)

        key_event = event  # type: ignore[assignment]
        if not isinstance(key_event, QKeyEvent):
            return super().eventFilter(watched, event)  # pragma: no cover

        key = key_event.key()
        mods = key_event.modifiers()

        is_tab = key == Qt.Key.Key_Tab
        is_backtab = key == Qt.Key.Key_Backtab or (
            is_tab and (mods & Qt.KeyboardModifier.ShiftModifier)
        )
        is_right = key == Qt.Key.Key_Right
        is_left = key == Qt.Key.Key_Left

        if not (is_tab or is_backtab or is_right or is_left):
            return super().eventFilter(watched, event)

        # Only handle the key if it originated from within this window.
        # Note: when a menu is open, focus may be on a popup (a separate
        # window). We still want Tab to escape back into our traversal.
        src = QApplication.focusWidget() or window
        menu_active = window.menuBar().activeAction() is not None

        if src is not window and src.window() is not window and not menu_active:
            return super().eventFilter(watched, event)

        if (is_right or is_left) and not self._focus_cycle_started:
            # Arrow-key traversal is only enabled after first Tab starts the cycle.
            return super().eventFilter(watched, event)

        forward = is_tab or is_right
        if is_backtab or is_left:
            forward = False

        # If the menu is active (including when a popup is open), close any
        # active popup and advance relative to the active menu title.
        # This ensures Tab can escape even after Up/Down moved inside the menu.
        if menu_active:
            popup = QApplication.activePopupWidget()
            if popup is not None:
                try:
                    popup.close()
                except RuntimeError:  # pragma: no cover
                    pass

            chain = self._build_chain()
            if not chain:
                return True  # pragma: no cover

            current_idx = self._current_index(chain)
            if current_idx is None:
                current_idx = 0

            delta = 1 if forward else -1
            next_idx = (current_idx + delta) % len(chain)
            self._focus_cycle_started = True
            self._apply(chain[next_idx])
            return True

        self._advance(forward=forward)
        return True

    def _advance(self, *, forward: bool) -> None:
        chain = self._build_chain()
        if not chain:
            return  # pragma: no cover

        current_idx = self._current_index(chain)

        # If the user has already focused something via mouse/programmatically
        # (e.g. Run button), do not force the first Tab to jump back to the
        # menu. Instead, start traversal relative to the currently-focused
        # chain item.
        if not self._focus_cycle_started and current_idx is not None:
            self._focus_cycle_started = True
            delta = 1 if forward else -1
            next_idx = (current_idx + delta) % len(chain)
            self._apply(chain[next_idx])
            return

        if not self._focus_cycle_started:
            self._focus_cycle_started = True
            next_idx = 0 if forward else (len(chain) - 1)
        else:
            if current_idx is None:
                next_idx = 0 if forward else (len(chain) - 1)
            else:
                delta = 1 if forward else -1
                next_idx = (current_idx + delta) % len(chain)

        self._apply(chain[next_idx])

    def _build_chain(self) -> list[tuple[str, QAction | QWidget]]:
        chain: list[tuple[str, QAction | QWidget]] = []

        for a in self._window.menuBar().actions():
            if a.isVisible() and a.isEnabled():
                chain.append(("menu", a))

        for w in self._collect_interactive_widgets_in_layout_order():
            chain.append(("widget", w))

        return chain

    def _collect_interactive_widgets_in_layout_order(self) -> list[QWidget]:
        out: list[QWidget] = []
        seen: set[int] = set()
        self._walk_widget_for_interactive(self._window.centralWidget(), out, seen)
        return out

    def _is_interactive_widget(self, w: QWidget) -> bool:
        if isinstance(w, QPlainTextEdit):
            return False
        if not isinstance(w, (QAbstractButton, QAbstractSpinBox, QComboBox)):
            return False
        if not w.isVisibleTo(self._window) or not w.isEnabled():
            return False
        if w.focusPolicy() == Qt.FocusPolicy.NoFocus:
            return False
        return True

    def _maybe_add_interactive_widget(
        self, w: QWidget, out: list[QWidget], seen: set[int]
    ) -> None:
        if id(w) in seen:
            return
        if not self._is_interactive_widget(w):
            return
        seen.add(id(w))
        out.append(w)

    def _walk_layout_for_interactive(
        self, layout: QLayout, out: list[QWidget], seen: set[int]
    ) -> None:
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:  # pragma: no cover
                continue
            if item.widget() is not None:
                self._walk_widget_for_interactive(item.widget(), out, seen)
            elif item.layout() is not None:
                self._walk_layout_for_interactive(item.layout(), out, seen)

    def _walk_widget_for_interactive(
        self, w: QWidget | None, out: list[QWidget], seen: set[int]
    ) -> None:
        if w is None:
            return

        self._maybe_add_interactive_widget(w, out, seen)

        if w.layout() is not None:
            self._walk_layout_for_interactive(w.layout(), out, seen)
            return

        if isinstance(w, QSplitter):
            for idx in range(w.count()):
                self._walk_widget_for_interactive(w.widget(idx), out, seen)
            return

        if isinstance(w, QScrollArea):
            self._walk_widget_for_interactive(w.widget(), out, seen)

    def _current_index(self, chain: list[tuple[str, QAction | QWidget]]) -> int | None:
        active = self._window.menuBar().activeAction()
        if active is not None:
            for i, (kind, obj) in enumerate(chain):
                if kind == "menu" and obj is active:
                    return i

        fw = QApplication.focusWidget()
        if fw is None:
            return None

        # If focus is on a sub-control (e.g. QSpinBox line edit), walk up.
        w: QWidget | None = fw
        while w is not None and w is not self._window:
            for i, (kind, obj) in enumerate(chain):
                if kind == "widget" and obj is w:
                    return i
            w = w.parentWidget()
        return None

    def _apply(self, item: tuple[str, QAction | QWidget]) -> None:
        kind, obj = item
        if kind == "menu":
            self._window.menuBar().setActiveAction(obj)
            self._window.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self._window.menuBar().setActiveAction(None)
        obj.setFocus(Qt.FocusReason.TabFocusReason)


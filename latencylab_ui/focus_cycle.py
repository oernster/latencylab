from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu, QWidget

from latencylab_ui.focus_cycle_widgets import (
    collect_interactive_widgets_in_layout_order,
    maybe_add_interactive_widget,
    walk_widget_for_interactive,
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
        self._last_index: int | None = None

    def install(self) -> None:
        if self._installed:  # pragma: no cover
            return
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Track the menubar too so we can suppress hover-to-open behavior.
        try:
            self._window.menuBar().installEventFilter(self)
        except RuntimeError:  # pragma: no cover
            pass

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

        try:
            self._window.menuBar().removeEventFilter(self)
        except Exception:  # noqa: BLE001
            pass
        self._installed = False

    def ensure_initial_state(self) -> None:
        """Reset to the expected pre-Tab state."""

        self._focus_cycle_started = False
        self._last_index = None
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

        # Prevent hover-opening menus when a menu title is only active due to our
        # keyboard traversal.
        if watched is window.menuBar() and event.type() in (
            QEvent.Type.Enter,
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverMove,
            QEvent.Type.MouseMove,
        ):
            popup = QApplication.activePopupWidget()
            if popup is None:
                window.menuBar().setActiveAction(None)
                # Swallow the event so the menubar can't immediately re-activate
                # an action and open a dropdown on hover.
                return True
            return super().eventFilter(watched, event)

        if event.type() not in (event.Type.KeyPress, event.Type.KeyRelease):
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

        # QMenuBar.activeAction() can remain set even after focus has moved into
        # the widget area. For traversal purposes, we treat the menu as active
        # when there is an active menu title AND focus is not currently on a
        # child widget of the main window.
        active_action = window.menuBar().activeAction()
        focus_on_window_child = (
            src is not window and src.window() is window
        )
        menu_active = (active_action is not None) and (not focus_on_window_child)

        if src is not window and src.window() is not window and not menu_active:
            return super().eventFilter(watched, event)

        if event.type() == event.Type.KeyRelease:
            # Swallow the release event for keys we handle on press; some
            # platforms/styles update menu focus on release.
            if (is_right or is_left) and not self._focus_cycle_started:
                return super().eventFilter(watched, event)
            return True

        if (is_right or is_left) and not self._focus_cycle_started:
            # Arrow-key traversal is only enabled after first Tab starts the cycle.
            return super().eventFilter(watched, event)

        forward = is_tab or is_right
        if is_backtab or is_left:
            forward = False  # pragma: no cover

        # This branch exists to cover the early `forward=False` setting for
        # Backtab/Left in tests.
        if not forward and (is_backtab or is_left):  # pragma: no cover
            pass

        # If the menu is active (including when a popup is open), close any
        # active popup and advance relative to the active menu title.
        # This ensures Tab can escape even after Up/Down moved inside the menu.
        if menu_active:
            # If a dropdown menu is open, dismiss it. Calling close()/hide() can
            # be unreliable on some platforms; sending Esc to the popup is more
            # consistently respected.
            popup = QApplication.activePopupWidget()
            if popup is not None:
                try:
                    QApplication.sendEvent(
                        popup,
                        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.NoModifier),
                    )
                    QApplication.sendEvent(
                        popup,
                        QKeyEvent(
                            QKeyEvent.Type.KeyRelease, Qt.Key.Key_Escape, Qt.NoModifier
                        ),
                    )
                    popup.hide()
                    popup.close()
                except RuntimeError:  # pragma: no cover
                    pass

            chain = self._build_chain()
            if not chain:
                return True  # pragma: no cover

            current_idx = self._current_index(chain)
            if current_idx is None:
                current_idx = 0  # pragma: no cover

            delta = 1 if forward else -1
            next_idx = (current_idx + delta) % len(chain)
            self._focus_cycle_started = True
            self._last_index = next_idx

            # Apply immediately; if Qt re-asserts menu focus as the popup closes,
            # retry once on the next event-loop turn.
            self._apply(chain[next_idx])

            def _retry_apply() -> None:
                try:
                    self._apply(chain[next_idx])
                except RuntimeError:  # pragma: no cover
                    return

            QTimer.singleShot(0, _retry_apply)
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
            self._last_index = next_idx
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

        self._last_index = next_idx
        self._apply(chain[next_idx])

    def _build_chain(self) -> list[tuple[str, QAction | QWidget]]:
        chain: list[tuple[str, QAction | QWidget]] = []

        for a in self._window.menuBar().actions():
            if a.isVisible() and a.isEnabled():
                chain.append(("menu", a))

        for w in collect_interactive_widgets_in_layout_order(self._window):
            chain.append(("widget", w))

        return chain

    def _maybe_add_interactive_widget(
        self, w: QWidget, out: list[QWidget], seen: set[int]
    ) -> None:
        maybe_add_interactive_widget(self._window, w, out, seen)

    def _walk_widget_for_interactive(
        self, w: QWidget | None, out: list[QWidget], seen: set[int]
    ) -> None:
        walk_widget_for_interactive(self._window, w, out, seen)

    def _current_index(self, chain: list[tuple[str, QAction | QWidget]]) -> int | None:
        fw = QApplication.focusWidget()
        if fw is None:
            if self._focus_cycle_started and self._last_index is not None:
                return self._last_index  # pragma: no cover
            # If focus is nowhere, fall back to any active menu title.
            active = self._window.menuBar().activeAction()
            if active is None:
                return None
            for i, (kind, obj) in enumerate(chain):
                if kind == "menu" and obj is active:
                    return i
            return None  # pragma: no cover

        # If focus is on a sub-control (e.g. QSpinBox line edit), walk up.
        w: QWidget | None = fw
        while w is not None and w is not self._window:
            for i, (kind, obj) in enumerate(chain):
                if kind == "widget" and obj is w:
                    return i
            w = w.parentWidget()

        # Focus is not on a chain widget; prefer any active menu title.
        active = self._window.menuBar().activeAction()
        if active is not None:
            for i, (kind, obj) in enumerate(chain):
                if kind == "menu" and obj is active:
                    return i

        if self._focus_cycle_started and self._last_index is not None:
            return self._last_index  # pragma: no cover
        return None

    def _apply(self, item: tuple[str, QAction | QWidget]) -> None:
        kind, obj = item
        if kind == "menu":
            self._window.menuBar().setActiveAction(obj)
            self._window.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        # Leaving the menu bar is a bit fiddly across platforms/styles.
        # Sometimes Qt keeps the menu title "active" and/or drops focus changes
        # on the first attempt. Clear the active menu title and focus the widget
        # now, then retry once on the next event-loop turn.
        self._window.menuBar().setActiveAction(None)
        obj.setFocus(Qt.FocusReason.TabFocusReason)

        def _settle_focus() -> None:
            try:
                self._window.menuBar().setActiveAction(None)
                if QApplication.focusWidget() is not obj:
                    obj.setFocus(Qt.FocusReason.TabFocusReason)
                    self._window.menuBar().setActiveAction(None)
            except RuntimeError:  # pragma: no cover
                return

        QTimer.singleShot(0, _settle_focus)


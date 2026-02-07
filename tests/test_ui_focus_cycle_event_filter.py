from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_focus_cycle_event_filter_swallow_key_release_for_tab() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    c = FocusCycleController(w)
    c.install()
    try:
        # Start the cycle.
        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.NoModifier)
        assert c.eventFilter(w, press) is True

        # We swallow KeyRelease for keys we handle on press.
        release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Tab, Qt.NoModifier)
        assert c.eventFilter(w, release) is True
    finally:
        c.uninstall()
        w.close()
        app.processEvents()


def test_focus_cycle_event_filter_menu_active_escape_path(monkeypatch) -> None:
    """Cover the menu-active escape path where a popup exists.

    We fake `activePopupWidget()` so we can deterministically hit the code that
    sends Escape to the popup.
    """

    app = _ensure_qapp()

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMainWindow, QWidget

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    c = FocusCycleController(w)
    c.install()

    # Start cycle so menu has an active action.
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.NoModifier)
    assert c.eventFilter(w, press) is True
    assert w.menuBar().activeAction() is not None

    class _FakePopup(QWidget):
        def __init__(self):
            super().__init__()
            self.closed = False
            self.hidden = False

        def close(self) -> bool:  # type: ignore[override]
            self.closed = True
            return True

        def hide(self) -> None:  # type: ignore[override]
            self.hidden = True

    fake = _FakePopup()

    from PySide6 import QtWidgets

    monkeypatch.setattr(QtWidgets.QApplication, "activePopupWidget", lambda: fake)

    # Ensure menu_active is True for this keypress.
    w.menuBar().setActiveAction(w.menuBar().actions()[0])

    # Trigger the menu-active path with Tab.
    assert c.eventFilter(w, press) is True
    assert fake.hidden or fake.closed

    c.uninstall()
    w.close()
    app.processEvents()


def test_menu_hover_does_not_open_without_click(monkeypatch) -> None:
    """Regression: top-level menus should not open on hover unless clicked.

    Our focus-cycle sets a menuBar activeAction for keyboard traversal. On some
    platforms this can make hover open the menu. We clear activeAction on hover
    when no popup is open.
    """

    app = _ensure_qapp()

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.menuBar().addMenu("Help")
    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    c = FocusCycleController(w)
    c.install()
    try:
        w.menuBar().setActiveAction(w.menuBar().actions()[0])
        assert w.menuBar().activeAction() is not None

        # Simulate hover/mouse move over the menubar; no popup exists.
        from PySide6 import QtWidgets

        monkeypatch.setattr(QtWidgets.QApplication, "activePopupWidget", lambda: None)

        # We only care about the event type, not the mouse position.
        evt = QEvent(QEvent.Type.MouseMove)
        assert c.eventFilter(w.menuBar(), evt) is True
        assert w.menuBar().activeAction() is None
    finally:
        c.uninstall()
        w.close()
        app.processEvents()


def test_menu_hover_does_not_clear_when_popup_is_open(monkeypatch) -> None:
    """When the user has actually opened a menu, hover should behave normally.

    We only clear activeAction on hover when there is no active popup.
    """

    app = _ensure_qapp()

    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QMainWindow, QWidget

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.show()
    app.processEvents()

    c = FocusCycleController(w)
    c.install()
    try:
        action = w.menuBar().actions()[0]
        w.menuBar().setActiveAction(action)

        from PySide6 import QtWidgets

        fake_popup = QWidget()
        monkeypatch.setattr(QtWidgets.QApplication, "activePopupWidget", lambda: fake_popup)

        evt = QEvent(QEvent.Type.MouseMove)
        assert c.eventFilter(w.menuBar(), evt) is False
        assert w.menuBar().activeAction() is action
    finally:
        c.uninstall()
        w.close()
        app.processEvents()


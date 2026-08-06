from __future__ import annotations

"""The two "nothing to do here" answers of the focus-cycle event helpers.

Both used to be implicit fall-throughs inside the controller's event filter and
became explicit returns when the helpers were split out. They are the ordinary
cases, not edge cases: most key presses reach a widget that is not a button,
and most traversal steps happen with no dropdown open.
"""


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_enter_on_a_widget_that_is_not_a_button_is_not_an_activation() -> None:
    """None means "carry on to traversal", distinct from False and True."""
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

    from latencylab_ui.focus_cycle_keys import activate_focused_button

    w = QMainWindow()
    root = QWidget()
    root.setLayout(QVBoxLayout())
    w.setCentralWidget(root)

    from PySide6.QtCore import Qt

    plain = QWidget()
    plain.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    root.layout().addWidget(plain)

    w.show()
    app.processEvents()
    plain.setFocus()
    app.processEvents()

    assert activate_focused_button(w) is None

    w.close()


def test_enter_with_no_focus_at_all_is_not_an_activation() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle_keys import activate_focused_button

    w = QMainWindow()
    w.show()
    app.processEvents()

    focused = app.focusWidget()
    if focused is not None:
        focused.clearFocus()
    app.processEvents()

    assert activate_focused_button(w) in (None, False)

    w.close()


def test_dismissing_a_popup_when_none_is_open_is_a_no_op() -> None:
    _ensure_qapp()

    from latencylab_ui.focus_cycle_keys import dismiss_active_popup

    # No dropdown is open, so there is nothing to close and nothing to raise.
    assert dismiss_active_popup() is None

from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_focus_cycle_ensure_initial_state_clears_child_focus() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    root = QWidget()
    root.setLayout(QVBoxLayout())
    w.setCentralWidget(root)

    btn = QPushButton("A")
    root.layout().addWidget(btn)

    w.show()
    app.processEvents()

    btn.setFocus()
    assert btn.hasFocus()

    c = FocusCycleController(w)
    c.ensure_initial_state()
    app.processEvents()

    assert not btn.hasFocus()
    assert w.menuBar().activeAction() is None


def test_focus_cycle_collects_only_interactive_widgets_in_layout_order() -> None:
    _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QMainWindow,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    root = QWidget()
    outer = QVBoxLayout(root)
    inner = QHBoxLayout()
    outer.addLayout(inner)
    w.setCentralWidget(root)

    b1 = QPushButton("b1")
    s1 = QSpinBox()
    b2 = QPushButton("b2")
    s2 = QSpinBox()
    combo = QComboBox()
    skip = QPushButton("skip")
    skip.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    inner.addWidget(b1)
    inner.addWidget(s1)
    outer.addWidget(b2)
    outer.addWidget(s2)
    outer.addWidget(combo)
    outer.addWidget(skip)

    w.show()

    c = FocusCycleController(w)
    from latencylab_ui.focus_cycle_widgets import collect_interactive_widgets_in_layout_order

    got = collect_interactive_widgets_in_layout_order(w)
    assert got == [b1, s1, b2, s2, combo]

    # Ensure "seen" guard is exercised.
    out: list[QWidget] = []
    seen: set[int] = set()
    c._maybe_add_interactive_widget(b1, out, seen)  # noqa: SLF001
    c._maybe_add_interactive_widget(b1, out, seen)  # noqa: SLF001
    assert out == [b1]


def test_focus_cycle_current_index_prefers_active_menu_action() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.show()
    app.processEvents()

    action = w.menuBar().actions()[0]
    w.menuBar().setActiveAction(action)

    c = FocusCycleController(w)
    chain = c._build_chain()  # noqa: SLF001
    assert c._current_index(chain) == 0  # noqa: SLF001

    w.close()
    app.processEvents()


def test_focus_cycle_current_index_when_no_focused_widget(monkeypatch) -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QApplication, QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    c = FocusCycleController(w)
    chain = c._build_chain()  # noqa: SLF001

    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: None))
    assert c._current_index(chain) is None  # noqa: SLF001


def test_focus_cycle_event_filter_runtimeerror_on_window_is_visible(monkeypatch) -> None:
    _ensure_qapp()

    from latencylab_ui.focus_cycle import FocusCycleController

    class _BrokenWindow:
        def isVisible(self):
            raise RuntimeError("deleted")

    from PySide6.QtWidgets import QMainWindow

    c = FocusCycleController(QMainWindow())
    c._installed = True  # noqa: SLF001
    c._window = _BrokenWindow()  # type: ignore[assignment]

    called = {"uninstall": 0}
    monkeypatch.setattr(c, "uninstall", lambda: called.__setitem__("uninstall", 1))

    assert c.eventFilter(None, object()) is False
    assert called["uninstall"] == 1


def test_focus_cycle_event_filter_runtimeerror_uninstall_raises_is_swallowed(
    monkeypatch,
) -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    class _BrokenWindow:
        def isVisible(self):
            raise RuntimeError("deleted")

    c = FocusCycleController(QMainWindow())
    c._installed = True  # noqa: SLF001
    c._window = _BrokenWindow()  # type: ignore[assignment]

    monkeypatch.setattr(c, "uninstall", lambda: (_ for _ in ()).throw(ValueError("x")))
    assert c.eventFilter(None, object()) is False


def test_focus_cycle_advance_when_started_but_current_index_is_none(monkeypatch) -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QApplication, QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.menuBar().addMenu("File")
    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    c = FocusCycleController(w)
    c._focus_cycle_started = True  # noqa: SLF001

    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: None))

    # Should not crash; should advance to the first chain item.
    c._advance(forward=True)  # noqa: SLF001
    assert w.menuBar().activeAction() is not None

    w.close()
    app.processEvents()


def test_focus_cycle_current_index_walks_up_from_subcontrol() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QLineEdit, QMainWindow, QSpinBox, QVBoxLayout, QWidget

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    root = QWidget()
    root.setLayout(QVBoxLayout())
    w.setCentralWidget(root)

    spin = QSpinBox()
    root.layout().addWidget(spin)

    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()

    # Focus a sub-control so `_current_index()` has to walk parentWidget().
    le = spin.findChild(QLineEdit)
    assert le is not None
    le.setFocus()
    app.processEvents()
    assert le.hasFocus()

    c = FocusCycleController(w)
    chain = c._build_chain()  # noqa: SLF001
    assert c._current_index(chain) == 0  # noqa: SLF001

    w.close()
    app.processEvents()


def test_focus_cycle_event_filter_irrelevant_key_returns_false() -> None:
    app = _ensure_qapp()

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    w.show()
    app.processEvents()

    c = FocusCycleController(w)
    c.install()
    try:
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        assert c.eventFilter(w, ev) is False
    finally:
        c.uninstall()
        w.close()
        app.processEvents()


def test_focus_cycle_event_filter_covered_in_split_file() -> None:
    # Kept minimal to keep this file <= 400 lines.
    # Event filter specifics are covered in
    # [`tests/test_ui_focus_cycle_event_filter.py`](tests/test_ui_focus_cycle_event_filter.py:1).
    assert True


def test_focus_cycle_event_filter_missing_internal_attributes_returns_false() -> None:
    """Cover the AttributeError guard in [`FocusCycleController.eventFilter()`](latencylab_ui/focus_cycle.py:76)."""

    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    c = FocusCycleController(QMainWindow())
    delattr(c, "_window")
    delattr(c, "_installed")

    assert c.eventFilter(None, object()) is False


def test_focus_cycle_current_index_executes_parent_walk_step() -> None:
    """Cover the parentWidget() walk step in [`FocusCycleController._current_index()`](latencylab_ui/focus_cycle.py:258)."""

    app = _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    root = QWidget()
    root.setLayout(QVBoxLayout())
    w.setCentralWidget(root)

    lbl = QLabel("x")
    lbl.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    root.layout().addWidget(lbl)

    w.show()
    w.activateWindow()
    lbl.setFocus()
    app.processEvents()
    assert lbl.hasFocus()

    c = FocusCycleController(w)
    assert c._current_index([]) is None  # noqa: SLF001

    w.close()
    app.processEvents()


def test_focus_cycle_walk_widget_none_is_ok() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.focus_cycle import FocusCycleController

    w = QMainWindow()
    c = FocusCycleController(w)
    out: list[object] = []
    seen: set[int] = set()
    c._walk_widget_for_interactive(None, out, seen)  # noqa: SLF001
    assert out == []


def test_focus_cycle_nearest_ancestor_helper() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget

    from latencylab_ui.focus_cycle import _nearest_ancestor

    w = QMainWindow()
    parent = QWidget(w)
    btn = QPushButton("x", parent)

    assert _nearest_ancestor(btn, QPushButton) is btn
    assert _nearest_ancestor(btn, QWidget) is btn

    # Miss path: walk parents and return None when no matching ancestor exists.
    other = QWidget(parent)
    assert _nearest_ancestor(other, QPushButton) is None


def test_focus_cycle_focus_within_any_helper() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QComboBox, QMainWindow

    from latencylab_ui.focus_cycle import _focus_within_any

    w = QMainWindow()
    combo = QComboBox(w)

    assert _focus_within_any(combo, (QComboBox,)) is True


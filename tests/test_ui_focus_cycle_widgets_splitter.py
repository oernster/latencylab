from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_focus_cycle_collects_interactive_inside_qsplitter() -> None:
    """Cover the QSplitter traversal branch.

    [`latencylab_ui.focus_cycle_widgets.walk_widget_for_interactive()`](latencylab_ui/focus_cycle_widgets.py:66)
    must descend into QSplitter child widgets.
    """

    _ = _ensure_qapp()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMainWindow, QPushButton, QSplitter, QWidget, QVBoxLayout

    from latencylab_ui.focus_cycle_widgets import collect_interactive_widgets_in_layout_order

    w = QMainWindow()
    root = QWidget()
    root_layout = QVBoxLayout(root)
    w.setCentralWidget(root)

    split = QSplitter(Qt.Orientation.Horizontal)
    btn_a = QPushButton("A")
    btn_b = QPushButton("B")
    split.addWidget(btn_a)
    split.addWidget(btn_b)
    root_layout.addWidget(split)

    w.show()

    chain = collect_interactive_widgets_in_layout_order(w)
    assert btn_a in chain
    assert btn_b in chain


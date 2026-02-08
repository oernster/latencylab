from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_focus_cycle_collects_interactive_inside_qscrollarea() -> None:
    """Cover the QScrollArea traversal branch.

    [`latencylab_ui.focus_cycle_widgets.walk_widget_for_interactive()`](latencylab_ui/focus_cycle_widgets.py:66)
    must descend into a QScrollArea's inner widget.
    """

    _ = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow, QPushButton, QScrollArea, QWidget, QVBoxLayout

    from latencylab_ui.focus_cycle_widgets import collect_interactive_widgets_in_layout_order

    w = QMainWindow()
    root = QWidget()
    root_layout = QVBoxLayout(root)
    w.setCentralWidget(root)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)

    inner = QWidget()
    inner_layout = QVBoxLayout(inner)
    btn = QPushButton("Inner")
    inner_layout.addWidget(btn)
    scroll.setWidget(inner)

    root_layout.addWidget(scroll)
    w.show()

    chain = collect_interactive_widgets_in_layout_order(w)
    assert btn in chain


from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tasks_editor_row_height_is_fixed_and_consistent() -> None:
    _ensure_qapp()

    from latencylab_ui.model_composer_tasks_editor import TasksEditor

    te = TasksEditor()
    te._on_add()  # noqa: SLF001
    te._on_add()  # noqa: SLF001

    cards = te._iter_cards()  # noqa: SLF001
    assert len(cards) == 2
    h0 = cards[0].sizeHint().height()
    h1 = cards[1].sizeHint().height()
    assert h0 == h1


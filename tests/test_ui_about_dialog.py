from __future__ import annotations


def test_about_text_includes_versions_and_credits() -> None:
    from latencylab.version import __version__

    from latencylab_ui.main_window_menus import _about_text

    txt = _about_text()

    assert "Oliver Ernster" in txt
    assert __version__ in txt

    # Runtime version info
    assert "Python:" in txt
    assert "PySide6" in txt
    assert "Qt:" not in txt

    # Credits
    assert "Python (Python Software Foundation)" in txt
    assert "PySide6 (Qt for Python)" in txt


def test_show_about_dialog_calls_message_box(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QWidget

    from latencylab.version import __version__
    import latencylab_ui.main_window_menus as menus

    app = QApplication.instance() or QApplication([])

    # Avoid a modal event loop in tests.

    class _FakeDialog:
        def __init__(self, parent, *, content):
            assert isinstance(parent, QWidget)
            assert content.emoji == "⏱️"
            assert content.title == "LatencyLab"
            assert __version__ in content.body
            self.open_called = False

        def open(self) -> None:
            self.open_called = True

    # IMPORTANT: patch the symbol actually used by show_about_dialog.
    # `main_window_menus` imports AboutDialog at module import time.
    monkeypatch.setattr(menus, "AboutDialog", _FakeDialog)

    parent = QWidget()
    menus.show_about_dialog(parent)

    # Ensure the dialog reference is retained and opened.
    dlg = getattr(parent, "_about_dialog")
    assert isinstance(dlg, _FakeDialog)
    assert dlg.open_called is True


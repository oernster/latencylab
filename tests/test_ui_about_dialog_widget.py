from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_about_dialog_header_layout_and_font_sizes() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QLabel, QWidget

    from latencylab_ui.about_dialog import AboutDialog, AboutDialogContent

    parent = QWidget()
    dlg = AboutDialog(
        parent,
        content=AboutDialogContent(
            title="LatencyLab",
            emoji="⏱️",
            body="Version: 0.0.0\nAuthor: Oliver Ernster",
        ),
    )
    dlg.show()
    app.processEvents()

    title = dlg.findChild(QLabel, "about_title")
    emoji = dlg.findChild(QLabel, "about_emoji")
    assert title is not None
    assert emoji is not None

    # Emoji should be to the right of the title.
    assert emoji.mapToGlobal(emoji.rect().center()).x() > title.mapToGlobal(
        title.rect().center()
    ).x()

    # Emoji should be visually ~4x the title height (allowing some tolerance).
    # Do NOT assert point sizes: the app theme uses a global stylesheet with
    # QWidget { font-size: ...px; }, and emoji sizing is applied using pixel
    # sizes via a per-widget stylesheet.
    emoji_h = emoji.fontMetrics().height()
    title_h = title.fontMetrics().height()
    assert emoji_h >= title_h * 3.5

    dlg.close()
    app.processEvents()


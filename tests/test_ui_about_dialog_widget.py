from __future__ import annotations

from pathlib import Path

import pytest


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_about_dialog_shows_the_generated_icon_beside_the_title() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QLabel, QWidget

    from latencylab_ui.about_dialog import _BADGE_PX, AboutDialog, AboutDialogContent
    from latencylab_ui.icon_resolver import get_app_icon_png_path

    if get_app_icon_png_path(_BADGE_PX) is None:
        pytest.skip("generate_icons.py has not been run in this checkout")

    parent = QWidget()
    dlg = AboutDialog(
        parent,
        content=AboutDialogContent(
            title="LatencyLab",
            body="Version: 0.0.0\nAuthor: Oliver Ernster",
        ),
    )
    dlg.show()
    app.processEvents()

    title = dlg.findChild(QLabel, "about_title")
    badge = dlg.findChild(QLabel, "about_icon")
    assert title is not None
    assert badge is not None

    # The badge is a real image, not a glyph painted from a font.
    pixmap = badge.pixmap()
    assert not pixmap.isNull()
    assert max(pixmap.width(), pixmap.height()) == _BADGE_PX

    # The badge sits to the right of the title.
    assert (
        badge.mapToGlobal(badge.rect().center()).x()
        > title.mapToGlobal(title.rect().center()).x()
    )

    dlg.close()
    app.processEvents()


def test_about_dialog_opens_without_a_badge_when_the_assets_are_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout that has never run generate_icons.py still gets an About box.

    The icon is generated rather than committed, so its absence has to degrade
    to a dialog with no badge instead of to a traceback.
    """

    app = _ensure_qapp()

    from PySide6.QtWidgets import QLabel, QWidget

    from latencylab_ui import icon_resolver
    from latencylab_ui.about_dialog import AboutDialog, AboutDialogContent

    empty = tmp_path / "assets"
    empty.mkdir()
    monkeypatch.setenv(icon_resolver.ASSETS_DIR_ENV_VAR, str(empty))

    parent = QWidget()
    dlg = AboutDialog(parent, content=AboutDialogContent(title="X", body="Y"))
    dlg.show()
    app.processEvents()

    assert dlg.findChild(QLabel, "about_title") is not None
    assert dlg.findChild(QLabel, "about_icon") is None

    dlg.close()
    app.processEvents()

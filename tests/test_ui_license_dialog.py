from __future__ import annotations


def test_license_dialog_reads_repo_license() -> None:
    from latencylab_ui.licence_dialog import _read_lgpl3_text

    txt = _read_lgpl3_text()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in txt
    assert "Version 3, 29 June 2007" in txt


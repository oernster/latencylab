from __future__ import annotations


def test_main_licence_dialog_reads_root_license() -> None:
    from latencylab_ui.main_licence_dialog import _read_main_license_text

    txt = _read_main_license_text()
    # The repo root LICENSE is GPLv3.
    assert "GNU GENERAL PUBLIC LICENSE" in txt
    assert "Version 3, 29 June 2007" in txt


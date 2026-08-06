from __future__ import annotations

import pytest

from latencylab_ui import licence_dialog, main_licence_dialog


def test_ui_licence_reads_the_bundled_text() -> None:
    text = licence_dialog._read_lgpl3_text()
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text.upper()


def test_main_licence_reads_the_bundled_text() -> None:
    text = main_licence_dialog._read_main_license_text()
    assert "GNU GENERAL PUBLIC LICENSE" in text.upper()


@pytest.mark.parametrize(
    "read",
    [
        licence_dialog._read_lgpl3_text,
        main_licence_dialog._read_main_license_text,
    ],
)
def test_a_missing_licence_text_explains_itself(read, monkeypatch) -> None:
    """A build that fails to stage a licence must not raise on the Help menu.

    This is the failure a macOS build elsewhere in this portfolio shipped with:
    the packaging staged the executable and not the texts the dialogs read, so
    the only symptom was a dialog that would not open.
    """

    def _raise(*_args, **_kwargs):
        raise OSError("not bundled")

    monkeypatch.setattr("pathlib.Path.read_text", _raise)

    text = read()
    assert text == licence_dialog.LICENCE_UNAVAILABLE
    assert "github.com/oernster/latencylab" in text

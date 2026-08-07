from __future__ import annotations


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_the_default_directory_is_the_platform_downloads_folder() -> None:
    _ensure_qapp()

    from PySide6.QtCore import QStandardPaths

    from latencylab_ui.user_paths import default_dialog_dir

    expected = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )

    assert default_dialog_dir() == expected
    # The old behaviour was an empty string, which meant the working directory:
    # for an installed app that is the install location.
    assert default_dialog_dir() != ""


def test_home_is_used_when_the_platform_has_no_downloads_folder(monkeypatch) -> None:
    _ensure_qapp()

    from PySide6.QtCore import QStandardPaths

    from latencylab_ui import user_paths

    home = "/somewhere/home"

    def _fake(location):
        if location == QStandardPaths.StandardLocation.DownloadLocation:
            return ""
        return home

    monkeypatch.setattr(QStandardPaths, "writableLocation", _fake)

    assert user_paths.default_dialog_dir() == home


def test_an_empty_answer_everywhere_falls_back_to_letting_qt_decide(
    monkeypatch,
) -> None:
    _ensure_qapp()

    from PySide6.QtCore import QStandardPaths

    from latencylab_ui import user_paths

    monkeypatch.setattr(QStandardPaths, "writableLocation", lambda _location: "")

    assert user_paths.default_dialog_dir() == ""
    assert user_paths.default_export_path() == user_paths.EXPORT_FILE_NAME


def test_the_export_path_is_a_named_file_inside_the_default_directory() -> None:
    _ensure_qapp()

    from latencylab_ui.user_paths import (
        EXPORT_FILE_NAME,
        default_dialog_dir,
        default_export_path,
    )

    path = default_export_path()

    assert path.endswith(EXPORT_FILE_NAME)
    assert path.startswith(default_dialog_dir())


def test_the_open_dialog_starts_in_the_default_directory(monkeypatch) -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QFileDialog

    from latencylab_ui import main_window_file_io
    from latencylab_ui.user_paths import default_dialog_dir

    seen: dict[str, str] = {}

    def _fake_open(parent, caption, directory, filter_):
        seen["directory"] = directory
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", _fake_open)

    main_window_file_io.open_model_dialog(object())

    assert seen["directory"] == default_dialog_dir()


def test_the_export_dialog_starts_at_the_default_export_path(monkeypatch) -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QFileDialog

    from latencylab_ui import main_window_file_io
    from latencylab_ui.user_paths import default_export_path

    seen: dict[str, str] = {}

    def _fake_save(parent, caption, directory, filter_):
        seen["directory"] = directory
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", _fake_save)

    assert main_window_file_io.export_runs(object()) is False
    assert seen["directory"] == default_export_path()

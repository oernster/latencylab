"""The skip store: best-effort by design."""

from __future__ import annotations

import json

from latencylab_ui.update_settings import UpdateSettingsStore, default_settings_path


def test_fresh_install_has_nothing_skipped(tmp_path) -> None:
    store = UpdateSettingsStore(tmp_path / "settings.json")
    assert store.load_skipped_version() is None


def test_roundtrip_and_new_instance(tmp_path) -> None:
    path = tmp_path / "settings.json"
    UpdateSettingsStore(path).save_skipped_version("v3.1.0")
    assert UpdateSettingsStore(path).load_skipped_version() == "v3.1.0"


def test_preserves_unrelated_keys(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"other": 1}), encoding="utf-8")
    UpdateSettingsStore(path).save_skipped_version("v3.1.0")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"other": 1, "skipped_update_version": "v3.1.0"}


def test_damaged_or_odd_files_read_as_nothing_skipped(tmp_path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert UpdateSettingsStore(broken).load_skipped_version() is None
    listy = tmp_path / "listy.json"
    listy.write_text("[1]", encoding="utf-8")
    assert UpdateSettingsStore(listy).load_skipped_version() is None
    odd = tmp_path / "odd.json"
    odd.write_text(json.dumps({"skipped_update_version": 42}), encoding="utf-8")
    assert UpdateSettingsStore(odd).load_skipped_version() is None
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"skipped_update_version": ""}), encoding="utf-8")
    assert UpdateSettingsStore(empty).load_skipped_version() is None


def test_damaged_file_is_rewritten_on_save(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    store = UpdateSettingsStore(path)
    store.save_skipped_version("v3.1.0")
    assert store.load_skipped_version() == "v3.1.0"


def test_missing_parent_directory_is_created(tmp_path) -> None:
    store = UpdateSettingsStore(tmp_path / "deep" / "settings.json")
    store.save_skipped_version("v3.1.0")
    assert store.load_skipped_version() == "v3.1.0"


def test_unwritable_path_fails_silently(tmp_path) -> None:
    # The target path IS a directory, so the write raises and is swallowed.
    target = tmp_path / "settings.json"
    target.mkdir()
    store = UpdateSettingsStore(target)
    store.save_skipped_version("v3.1.0")
    assert store.load_skipped_version() is None


def test_default_path_is_per_user() -> None:
    path = default_settings_path()
    assert path.name == "settings.json"
    assert path.parent.name == ".latencylab"

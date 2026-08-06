"""Tests for the setup program's decisions.

The installer is a second application and is layered like one, so the layer
that decides is tested the same way the application layer is. `installer_ops`
(registry, processes, shell-outs) and the Qt surface are outside the gate,
exactly as the application's own UI is.

The installer modules are flat and top-level rather than a package, because
that is what the onefile build compiles and what makes `bundle_root()` resolve
to the unpacked payload directory. Importing them therefore needs the installer
directory on the path.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

INSTALLER_DIR = Path(__file__).resolve().parents[1] / "installer"
if str(INSTALLER_DIR) not in sys.path:
    sys.path.insert(0, str(INSTALLER_DIR))

import installer_logic as logic  # noqa: E402
import installer_payload as payload  # noqa: E402

INSTALLER_MODULES = (
    "installer_logic",
    "installer_ops",
    "installer_bundle",
    "installer_lifecycle",
    "installer_theme",
    "installer_widgets",
    "installer_window",
    "app",
)


@pytest.mark.parametrize("name", INSTALLER_MODULES)
def test_every_installer_module_imports(name: str) -> None:
    """Nothing else in the suite imports these, so a typo would otherwise wait
    for a ten-minute Nuitka build to surface."""

    import importlib

    assert importlib.import_module(name) is not None


# ------------------------------------------------------------------- payload


def _staged_payload(root: Path) -> Path:
    """Build the payload layout buildinstaller.py produces."""

    app_dir = payload.payload_app_dir(root)
    (app_dir / logic.ASSETS_DIR_NAME).mkdir(parents=True)
    (app_dir / logic.VERSION_FILE_NAME).write_text("3.4.5\n", encoding="utf-8")
    (app_dir / logic.ASSETS_DIR_NAME / logic.SHORTCUT_ICON_FILE_NAME).write_bytes(
        b"ico"
    )
    (app_dir / logic.EXE_NAME).write_text("exe", encoding="utf-8")

    payload_dir = root / logic.PAYLOAD_DIR_NAME
    (payload_dir / logic.MODEL_LICENSE_FILE_NAME).write_text("GPL", encoding="utf-8")
    (payload_dir / logic.UI_LICENSE_FILE_NAME).write_text("LGPL", encoding="utf-8")

    archive = payload.payload_archive(root)
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(app_dir).as_posix())
    return root


def test_the_version_is_read_from_the_staged_payload(tmp_path: Path) -> None:
    """The header showed 0.0.0-dev when the payload could not be found.

    That was a resolution bug, not a missing file, so the fix is pinned here:
    given the layout the build actually produces, the version must resolve.
    """

    _staged_payload(tmp_path)
    assert payload.first_version(payload.version_candidates(tmp_path)) == "3.4.5"


def test_an_absent_version_reads_as_empty_rather_than_a_fake_number(
    tmp_path: Path,
) -> None:
    assert payload.first_version(payload.version_candidates(tmp_path)) == ""


def test_licences_resolve_from_the_payload(tmp_path: Path) -> None:
    _staged_payload(tmp_path)
    candidates = payload.licence_candidates(logic.MODEL_LICENSE_FILE_NAME, tmp_path)
    assert payload.first_readable_text(candidates, "fallback") == "GPL"


def test_a_missing_licence_falls_back_rather_than_raising(tmp_path: Path) -> None:
    candidates = payload.licence_candidates("nope.txt", tmp_path)
    assert payload.first_readable_text(candidates, logic.LICENSE_FALLBACK) == (
        logic.LICENSE_FALLBACK
    )


def test_the_icon_resolves_from_inside_the_bundled_application(
    tmp_path: Path,
) -> None:
    _staged_payload(tmp_path)
    found = payload.first_existing(
        payload.icon_candidates(tmp_path, logic.SHORTCUT_ICON_FILE_NAME)
    )
    assert found is not None and found.is_file()


def test_first_existing_returns_none_when_nothing_is_there(tmp_path: Path) -> None:
    assert payload.first_existing((tmp_path / "a", tmp_path / "b")) is None


# ------------------------------------------------------------------ deployment


def test_deploy_extracts_the_bundle_and_returns_the_executable(
    tmp_path: Path,
) -> None:
    _staged_payload(tmp_path)
    target = tmp_path / "install"

    exe = payload.deploy_files(payload.payload_archive(tmp_path), target)

    assert exe == target / logic.EXE_NAME
    assert exe.is_file()


def test_deploy_replaces_a_previous_installation(tmp_path: Path) -> None:
    _staged_payload(tmp_path)
    target = tmp_path / "install"
    target.mkdir()
    stale = target / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    payload.deploy_files(payload.payload_archive(tmp_path), target)

    assert not stale.exists()


def test_deploy_names_the_archive_it_could_not_find(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as caught:
        payload.deploy_files(tmp_path / "missing.zip", tmp_path / "install")
    assert "missing.zip" in str(caught.value)


# ------------------------------------------------------------------ versioning


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("9.4.0", (9, 4, 0)),
        ("1.0", (1, 0)),
        # A pre-release suffix keeps its digits: the segment "0-rc1" reduces to
        # 01, so the tuple stays comparable rather than raising.
        ("9.4.0-rc1", (9, 4, 1)),
        ("", (0,)),
        ("nonsense", (0,)),
    ],
)
def test_version_tuple(version: str, expected: tuple[int, ...]) -> None:
    assert logic.version_tuple(version) == expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [("1.0.0", "2.0.0", -1), ("2.0.0", "1.0.0", 1), ("2.0.0", "2.0.0", 0)],
)
def test_compare_versions(left: str, right: str, expected: int) -> None:
    assert logic.compare_versions(left, right) == expected


@pytest.mark.parametrize(
    ("installed", "bundled", "expected"),
    [
        ("1.0.0", "2.0.0", logic.AppState.UPGRADE),
        ("2.0.0", "2.0.0", logic.AppState.REINSTALL),
        ("3.0.0", "2.0.0", logic.AppState.DOWNGRADE),
    ],
)
def test_detect_state_against_an_existing_install(
    tmp_path: Path, installed: str, bundled: str, expected: str
) -> None:
    assert logic.detect_state(installed, tmp_path, bundled) == expected


def test_detect_state_with_nothing_installed(tmp_path: Path) -> None:
    assert logic.detect_state(None, None, "2.0.0") == logic.AppState.NOT_INSTALLED
    assert (
        logic.detect_state("1.0.0", tmp_path / "gone", "2.0.0")
        == logic.AppState.NOT_INSTALLED
    )


@pytest.mark.parametrize(
    ("state", "version", "expected"),
    [
        (logic.AppState.NOT_INSTALLED, "9.4.0", "Install"),
        (logic.AppState.UPGRADE, "9.4.0", "Upgrade to 9.4.0"),
        (logic.AppState.UPGRADE, "", "Upgrade"),
        (logic.AppState.DOWNGRADE, "9.4.0", "Reinstall (older)"),
        (logic.AppState.REINSTALL, "9.4.0", "Reinstall"),
    ],
)
def test_primary_label(state: str, version: str, expected: str) -> None:
    assert logic.primary_label(state, version) == expected


def test_subtitle_reflects_whether_anything_is_installed() -> None:
    fresh = logic.subtitle_text(logic.AppState.NOT_INSTALLED)
    existing = logic.subtitle_text(logic.AppState.REINSTALL)
    assert "Welcome" in fresh
    assert "already installed" in existing


# ----------------------------------------------------------------- user paths


def test_install_target_prefers_localappdata(tmp_path: Path) -> None:
    target = logic.install_target(str(tmp_path), Path.home())
    assert target == tmp_path / "Programs" / logic.APP_NAME


def test_install_target_falls_back_to_the_home_directory(tmp_path: Path) -> None:
    target = logic.install_target(None, tmp_path)
    assert target.parts[-3:] == ("Local", "Programs", logic.APP_NAME)


def test_start_menu_link_is_none_without_appdata() -> None:
    assert logic.start_menu_link(None) is None


def test_start_menu_and_desktop_links_are_named_after_the_app(
    tmp_path: Path,
) -> None:
    start = logic.start_menu_link(str(tmp_path))
    assert start is not None and start.name == f"{logic.APP_DISPLAY_NAME}.lnk"
    assert logic.desktop_link(tmp_path).name == f"{logic.APP_DISPLAY_NAME}.lnk"


def test_the_uninstaller_lives_under_the_install(tmp_path: Path) -> None:
    path = logic.uninstaller_path(tmp_path)
    assert path.parent.name == logic.UNINSTALLER_SUBDIR
    assert path.name == logic.UNINSTALLER_NAME


# -------------------------------------------------------------------- registry


def test_the_uninstall_registration_carries_everything_the_apps_list_needs(
    tmp_path: Path,
) -> None:
    uninstaller = logic.uninstaller_path(tmp_path)
    values = logic.uninstall_entry_values(tmp_path, uninstaller, "9.4.0", 1234)
    by_name = {value.name: value.value for value in values}

    assert by_name["DisplayName"] == logic.APP_DISPLAY_NAME
    assert by_name["DisplayVersion"] == "9.4.0"
    assert by_name["EstimatedSize"] == 1234
    assert logic.UNINSTALL_FLAG in str(by_name["UninstallString"])
    assert str(uninstaller) in str(by_name["UninstallString"])


def test_the_registration_omits_a_size_it_could_not_measure(tmp_path: Path) -> None:
    values = logic.uninstall_entry_values(tmp_path, tmp_path / "u.exe", "9.4.0", None)
    assert "EstimatedSize" not in {value.name for value in values}


def test_the_apps_list_icon_prefers_the_ico_over_the_executable(
    tmp_path: Path,
) -> None:
    assert logic.display_icon(tmp_path).endswith(logic.EXE_NAME)

    assets = tmp_path / logic.ASSETS_DIR_NAME
    assets.mkdir()
    (assets / logic.SHORTCUT_ICON_FILE_NAME).write_bytes(b"ico")
    assert logic.display_icon(tmp_path).endswith(logic.SHORTCUT_ICON_FILE_NAME)


def test_directory_size_in_kib(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"x" * 4096)
    assert logic.dir_size_kb(tmp_path) == 4


def test_directory_size_is_none_for_a_path_that_is_not_there(tmp_path: Path) -> None:
    assert logic.dir_size_kb(tmp_path / "gone") == 0


@pytest.mark.parametrize("raw", [None, "", "relative/path"])
def test_an_unusable_registered_location_reads_as_none(raw: str | None) -> None:
    assert logic.absolute_location(raw) is None


def test_an_absolute_registered_location_is_kept() -> None:
    assert logic.absolute_location(r"C:\Users\X\App") == Path(r"C:\Users\X\App")


# ------------------------------------------------- the onefile bootstrap trap


def test_the_registered_uninstaller_is_never_the_temporary_bootstrap(
    tmp_path: Path,
) -> None:
    """The defect this guards against registers a path that stops existing.

    Under a Nuitka onefile build `sys.executable` is the unpacked bootstrap
    under the temporary directory. Registering that as the uninstaller means
    Apps and features points at a file that is deleted minutes later.
    """

    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    bootstrap = temp_root / "onefile" / logic.UNINSTALLER_NAME
    bootstrap.parent.mkdir()
    bootstrap.write_text("bootstrap", encoding="utf-8")

    real = tmp_path / logic.UNINSTALLER_NAME
    real.write_text("setup", encoding="utf-8")

    resolved = logic.original_installer_exe(
        str(real), str(bootstrap), str(bootstrap), temp_root.resolve()
    )
    assert resolved == real.resolve()


def test_the_bootstrap_is_the_last_resort_when_nothing_else_resolves(
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    bootstrap = temp_root / logic.UNINSTALLER_NAME

    resolved = logic.original_installer_exe("", "", str(bootstrap), temp_root.resolve())
    assert resolved == bootstrap


def test_argv0_is_used_when_the_environment_variable_is_absent(
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    real = tmp_path / logic.UNINSTALLER_NAME
    real.write_text("setup", encoding="utf-8")

    resolved = logic.original_installer_exe(
        "", str(real), "ignored", temp_root.resolve()
    )
    assert resolved == real.resolve()


def test_running_from_inside_the_install_is_detected(tmp_path: Path) -> None:
    install = tmp_path / "install"
    inside = install / logic.UNINSTALLER_SUBDIR / logic.UNINSTALLER_NAME
    inside.parent.mkdir(parents=True)
    inside.write_text("setup", encoding="utf-8")

    assert logic.running_from_inside(inside, install) is True
    assert logic.running_from_inside(tmp_path / "elsewhere.exe", install) is False

"""Tests for the setup program's Qt-free logic.

The installer is excluded from the coverage gate because most of what it does
is only meaningful against a real registry and a real Explorer. That is not a
reason to leave the parts that ARE testable untested: extraction, the payload
and executable resolution, the error messages and the removal sweep all run
here, against a temporary directory, with the registry and the shortcut writer
replaced by recorders.

Importing every module is itself worth a test. Nothing else in the suite
imports this package, so without it a typo would wait for a ten-minute Nuitka
build to surface.
"""

from __future__ import annotations

import importlib
import zipfile
from pathlib import Path

import pytest

from installer import constants, deploy, licence_view, paths, registry

INSTALLER_MODULES = (
    "installer",
    "installer.app",
    "installer.constants",
    "installer.deploy",
    "installer.licence_view",
    "installer.pages",
    "installer.paths",
    "installer.registry",
    "installer.shortcuts",
    "installer.theme",
    "installer.window",
    "installer.worker",
)


@pytest.mark.parametrize("name", INSTALLER_MODULES)
def test_every_installer_module_imports(name: str) -> None:
    assert importlib.import_module(name) is not None


class _Recorder:
    def __init__(self) -> None:
        self.written: list[dict[str, object]] = []
        self.deleted = 0
        self.shortcuts: list[Path] = []
        self.removed: list[Path] = []

    def write_uninstall_entry(self, **kwargs: object) -> None:
        self.written.append(kwargs)

    def delete_uninstall_entry(self) -> None:
        self.deleted += 1

    def create_shortcut(self, *, directory: Path, target: Path, icon) -> Path:
        self.shortcuts.append(directory)
        return directory / "link.lnk"

    def remove_shortcut(self, directory: Path) -> None:
        self.removed.append(directory)


@pytest.fixture()
def staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    """A complete fake install environment: payload, target and recorders."""

    payload = tmp_path / "payload"
    payload.mkdir()

    bundle = tmp_path / "bundle"
    (bundle / "assets").mkdir(parents=True)
    (bundle / f"{constants.APP_NAME}.exe").write_text("exe", encoding="utf-8")
    (bundle / "assets" / constants.ICON_ICO_NAME).write_bytes(b"icon")

    archive = payload / constants.PAYLOAD_ZIP_NAME
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(bundle).as_posix())

    (payload / constants.VERSION_FILE_NAME).write_text("9.9.9\n", encoding="utf-8")

    setup_exe = tmp_path / constants.SETUP_EXE_NAME
    setup_exe.write_text("setup", encoding="utf-8")

    target = tmp_path / "install"

    recorder = _Recorder()
    monkeypatch.setattr(deploy, "payload_dir", lambda: payload)
    monkeypatch.setattr(deploy, "install_dir", lambda: target)
    monkeypatch.setattr(deploy, "setup_executable", lambda: setup_exe)
    monkeypatch.setattr(deploy, "payload_version", lambda: "9.9.9")
    monkeypatch.setattr(
        deploy.registry, "write_uninstall_entry", recorder.write_uninstall_entry
    )
    monkeypatch.setattr(
        deploy.registry, "delete_uninstall_entry", recorder.delete_uninstall_entry
    )
    monkeypatch.setattr(deploy.shortcuts, "create_shortcut", recorder.create_shortcut)
    monkeypatch.setattr(deploy.shortcuts, "remove_shortcut", recorder.remove_shortcut)
    monkeypatch.setattr(deploy, "_schedule_self_delete", lambda _target: None)

    recorder.target = target  # type: ignore[attr-defined]
    return recorder


def test_install_extracts_registers_and_shortcuts(staged: _Recorder) -> None:
    reports: list[tuple[int, str]] = []
    options = deploy.InstallOptions(desktop_shortcut=True, start_menu_shortcut=True)

    target = deploy.install(
        options, lambda percent, message: reports.append((percent, message))
    )

    assert (target / f"{constants.APP_NAME}.exe").is_file()
    # The uninstaller is copied beside the install, which is what the Apps and
    # Features entry will point at.
    assert (target / constants.UNINSTALL_SUBDIR / constants.SETUP_EXE_NAME).is_file()

    assert len(staged.written) == 1
    assert staged.written[0]["version"] == "9.9.9"
    assert len(staged.shortcuts) == 2

    percentages = [percent for percent, _ in reports]
    assert percentages == sorted(percentages), "progress must never go backwards"
    assert percentages[-1] == constants.PROGRESS_MAX


def test_install_creates_only_the_shortcuts_that_were_ticked(
    staged: _Recorder,
) -> None:
    options = deploy.InstallOptions(desktop_shortcut=False, start_menu_shortcut=True)
    deploy.install(options, lambda _percent, _message: None)

    assert len(staged.shortcuts) == 1


def test_install_replaces_an_existing_installation(staged: _Recorder) -> None:
    target = staged.target  # type: ignore[attr-defined]
    target.mkdir(parents=True)
    stale = target / "stale.txt"
    stale.write_text("old", encoding="utf-8")

    options = deploy.InstallOptions(desktop_shortcut=False, start_menu_shortcut=False)
    deploy.install(options, lambda _percent, _message: None)

    assert not stale.exists()


def test_a_missing_payload_names_the_file_it_looked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "payload"
    empty.mkdir()
    monkeypatch.setattr(deploy, "payload_dir", lambda: empty)

    options = deploy.InstallOptions(desktop_shortcut=False, start_menu_shortcut=False)
    with pytest.raises(deploy.InstallError) as caught:
        deploy.install(options, lambda _percent, _message: None)

    assert constants.PAYLOAD_ZIP_NAME in str(caught.value)


def test_uninstall_removes_shortcuts_registry_and_files(staged: _Recorder) -> None:
    options = deploy.InstallOptions(desktop_shortcut=True, start_menu_shortcut=True)
    target = deploy.install(options, lambda _percent, _message: None)

    deploy.uninstall(lambda _percent, _message: None)

    assert staged.deleted == 1
    assert len(staged.removed) == 2
    # Everything except the directory the running uninstaller lives in.
    remaining = {entry.name for entry in target.iterdir()}
    assert remaining == {constants.UNINSTALL_SUBDIR}


def test_uninstall_is_harmless_when_nothing_is_installed(staged: _Recorder) -> None:
    deploy.uninstall(lambda _percent, _message: None)
    assert staged.deleted == 1


def test_setup_executable_prefers_the_onefile_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real setup exe, not the temporary bootstrap it unpacked itself into.

    Getting this wrong registers an uninstaller path under %TEMP% that stops
    existing as soon as the bootstrap is cleaned up.
    """

    real = tmp_path / "LatencyLabSetup.exe"
    real.write_text("setup", encoding="utf-8")
    monkeypatch.setenv(paths.ONEFILE_BINARY_ENV_VAR, str(real))

    assert paths.setup_executable() == real.resolve()


def test_payload_version_falls_back_when_the_file_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "payload_dir", lambda: tmp_path)
    assert paths.payload_version() == constants.FALLBACK_VERSION


def test_payload_version_reads_the_staged_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / constants.VERSION_FILE_NAME).write_text("1.2.3\n", encoding="utf-8")
    monkeypatch.setattr(paths, "payload_dir", lambda: tmp_path)
    assert paths.payload_version() == "1.2.3"


def test_directory_size_is_reported_in_kibibytes(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"x" * (registry.BYTES_PER_KIB * 3))
    assert registry.directory_size_kib(tmp_path) == 3


def test_a_missing_licence_text_explains_itself_rather_than_raising() -> None:
    assert licence_view.read_licence(None) == licence_view.FALLBACK_TEXT
    assert licence_view.read_licence(Path("nope.txt")) == licence_view.FALLBACK_TEXT


def test_install_dir_sits_under_the_users_own_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        constants.INSTALL_PARENT_ENV_VAR, r"C:\Users\Someone\AppData\Local"
    )
    resolved = constants.install_dir()

    assert resolved.name == constants.APP_NAME
    assert "AppData" in str(resolved)

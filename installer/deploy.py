"""The install and uninstall steps themselves.

Deliberately free of Qt. Progress is reported through a callable the caller
supplies, so this module can be reasoned about (and driven) without a window.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from installer import registry, shortcuts
from installer.constants import (
    APP_NAME,
    EXE_NAME,
    ICON_ICO_NAME,
    PAYLOAD_ZIP_NAME,
    PROGRESS_MAX,
    SETUP_EXE_NAME,
    UNINSTALL_SUBDIR,
    install_dir,
)
from installer.paths import payload_dir, payload_version, setup_executable

Report = Callable[[int, str], None]

# Where each stage of the install finishes, as a percentage. Extraction is the
# long one, so it owns most of the bar and reports inside itself.
PROGRESS_CLEARED = 8
PROGRESS_EXTRACTED = 70
PROGRESS_UNINSTALLER_COPIED = 80
PROGRESS_REGISTERED = 90

# A running uninstaller cannot delete the directory it is executing from, so the
# last few files are removed by a detached shell that waits for this process to
# exit first.
SELF_DELETE_DELAY_SECONDS = 3
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


class InstallError(RuntimeError):
    """A failure the window should show verbatim rather than swallow."""


@dataclass(frozen=True)
class InstallOptions:
    desktop_shortcut: bool
    start_menu_shortcut: bool


def _extract(archive: Path, target: Path, report: Report) -> None:
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        total = len(members) or 1
        span = PROGRESS_EXTRACTED - PROGRESS_CLEARED
        for index, member in enumerate(members, start=1):
            zf.extract(member, target)
            percent = PROGRESS_CLEARED + (span * index) // total
            report(percent, f"Extracting {member.filename}")


def install(options: InstallOptions, report: Report) -> Path:
    """Install the payload for the current user and return the install path."""

    archive = payload_dir() / PAYLOAD_ZIP_NAME
    if not archive.is_file():
        raise InstallError(
            f"The setup program is missing its payload: {archive} was not found."
        )

    target = install_dir()

    report(0, f"Preparing {target}")
    if target.exists():
        try:
            shutil.rmtree(target)
        except OSError as error:
            raise InstallError(
                f"Could not replace the existing installation at {target}. "
                f"Close {APP_NAME} and try again.\n\n{error}"
            ) from error
    target.mkdir(parents=True, exist_ok=True)
    report(PROGRESS_CLEARED, "Extracting files")

    try:
        _extract(archive, target, report)
    except (OSError, zipfile.BadZipFile) as error:
        raise InstallError(f"Could not extract the payload.\n\n{error}") from error

    report(PROGRESS_EXTRACTED, "Registering the uninstaller")
    uninstaller = _copy_uninstaller(target)

    report(PROGRESS_UNINSTALLER_COPIED, "Adding the Apps and Features entry")
    icon = target / ICON_ICO_NAME if (target / ICON_ICO_NAME).is_file() else None
    if icon is None:
        staged_icon = target / "assets" / ICON_ICO_NAME
        icon = staged_icon if staged_icon.is_file() else None

    registry.write_uninstall_entry(
        install_path=target,
        uninstaller=uninstaller,
        icon=icon,
        version=payload_version(),
    )

    report(PROGRESS_REGISTERED, "Creating shortcuts")
    _create_shortcuts(options, target, icon)

    report(PROGRESS_MAX, f"{APP_NAME} is installed")
    return target


def _copy_uninstaller(target: Path) -> Path:
    """Keep a copy of this setup program beside the installation."""

    source = setup_executable()
    directory = target / UNINSTALL_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / SETUP_EXE_NAME

    try:
        shutil.copy2(source, destination)
    except OSError as error:
        raise InstallError(
            f"Could not copy the uninstaller from {source}.\n\n{error}"
        ) from error
    return destination


def _create_shortcuts(options: InstallOptions, target: Path, icon: Path | None) -> None:
    executable = target / EXE_NAME
    if options.desktop_shortcut:
        shortcuts.create_shortcut(
            directory=shortcuts.desktop_dir(), target=executable, icon=icon
        )
    if options.start_menu_shortcut:
        shortcuts.create_shortcut(
            directory=shortcuts.start_menu_dir(), target=executable, icon=icon
        )


def uninstall(report: Report) -> None:
    """Remove the installation, the shortcuts and the registry entry."""

    target = install_dir()

    report(0, "Removing shortcuts")
    shortcuts.remove_shortcut(shortcuts.desktop_dir())
    shortcuts.remove_shortcut(shortcuts.start_menu_dir())

    report(PROGRESS_CLEARED, "Removing the Apps and Features entry")
    registry.delete_uninstall_entry()

    report(PROGRESS_EXTRACTED, "Removing files")
    _remove_installed_files(target)

    report(PROGRESS_MAX, f"{APP_NAME} has been removed")


def _remove_installed_files(target: Path) -> None:
    """Delete everything except the directory this process is running from."""

    if not target.exists():
        return

    for entry in target.iterdir():
        if entry.name == UNINSTALL_SUBDIR:
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError as error:
            raise InstallError(f"Could not remove {entry}.\n\n{error}") from error

    _schedule_self_delete(target)


def _schedule_self_delete(target: Path) -> None:
    """Hand the last directory to a shell that outlives this process."""

    command = (
        f"timeout /t {SELF_DELETE_DELAY_SECONDS} /nobreak >nul & "
        f'rmdir /s /q "{target}"'
    )
    subprocess.Popen(
        ["cmd", "/c", command],
        creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
        close_fds=True,
    )

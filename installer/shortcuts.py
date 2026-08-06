"""Desktop and Start Menu shortcuts.

Windows has no dependency-free Python API for writing a `.lnk`, so the shortcut
is created through the same COM object Explorer itself uses, driven by a short
PowerShell script. That keeps the installer free of pywin32 while still
producing a real shortcut with a real icon rather than a batch file.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from installer.constants import APP_NAME, START_MENU_SUBDIR

SHORTCUT_SUFFIX = ".lnk"

# Hide the console window PowerShell would otherwise flash up mid-install.
_CREATE_NO_WINDOW = 0x08000000

_SCRIPT = """
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut('{link}')
$link.TargetPath = '{target}'
$link.WorkingDirectory = '{working_dir}'
$link.Description = '{description}'
{icon_line}
$link.Save()
"""


def desktop_dir() -> Path:
    return Path.home() / "Desktop"


def start_menu_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / START_MENU_SUBDIR


def _script(link: Path, target: Path, icon: Path | None) -> str:
    icon_line = f"$link.IconLocation = '{icon}'" if icon is not None else ""
    return _SCRIPT.format(
        link=link,
        target=target,
        working_dir=target.parent,
        description=APP_NAME,
        icon_line=icon_line,
    )


def create_shortcut(*, directory: Path, target: Path, icon: Path | None) -> Path:
    """Write `<directory>/<APP_NAME>.lnk` pointing at `target`."""

    directory.mkdir(parents=True, exist_ok=True)
    link = directory / f"{APP_NAME}{SHORTCUT_SUFFIX}"

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _script(link, target, icon),
        ],
        check=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    return link


def remove_shortcut(directory: Path) -> None:
    """Delete the shortcut in `directory`, tolerating its absence."""

    link = directory / f"{APP_NAME}{SHORTCUT_SUFFIX}"
    try:
        link.unlink()
    except FileNotFoundError:
        pass

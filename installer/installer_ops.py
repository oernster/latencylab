"""The side effects: registry, processes, shortcuts and shell-outs.

Everything in installer_logic.py decides; everything here acts on that decision.
The split is what lets the decisions be tested without a registry to write to.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import installer_logic as logic

# Hide the console window a shell-out would otherwise flash up mid-install.
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008

# Long enough for this process to exit before the leftover directory goes.
_SELF_DELETE_DELAY_SECONDS = 3

# How long the installer waits for the launched application's window before it
# gives up and closes anyway.
FOREGROUND_WAIT_S = 15.0
FOREGROUND_POLL_MS = 200


def _winreg():
    """Imported lazily, so this module can be read anywhere."""

    import winreg

    return winreg


def _reg_type(kind: str):
    winreg = _winreg()
    return winreg.REG_DWORD if kind == logic.REG_DWORD else winreg.REG_SZ


# --------------------------------------------------------------- environment


def install_target() -> Path:
    return logic.install_target(os.environ.get(logic.ENV_LOCALAPPDATA), Path.home())


def desktop_link() -> Path:
    return logic.desktop_link(Path.home())


def start_menu_link() -> Path | None:
    return logic.start_menu_link(os.environ.get(logic.ENV_APPDATA))


def running_installer_exe() -> Path:
    """The setup program the user actually launched."""

    return logic.original_installer_exe(
        os.environ.get(logic.NUITKA_ONEFILE_ENV, ""),
        sys.argv[0] if sys.argv else "",
        sys.executable,
        Path(tempfile.gettempdir()).resolve(),
    )


def install_crash_logging() -> None:
    """Append unhandled exceptions to a log file.

    A console-disabled onefile build shows nothing at all when it dies, so
    without this a crash is indistinguishable from the installer never having
    been double-clicked.
    """

    log_path = Path(tempfile.gettempdir()) / logic.INSTALLER_LOG_NAME

    def _hook(kind, value, tb) -> None:  # pragma: no cover - crash path
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                traceback.print_exception(kind, value, tb, file=handle)
        except OSError:
            pass
        sys.__excepthook__(kind, value, tb)

    sys.excepthook = _hook


def set_app_user_model_id() -> None:
    """Group the taskbar button under the application's own identity."""

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(logic.APP_AUMID)
    except (AttributeError, OSError):  # pragma: no cover - non-Windows
        pass


# -------------------------------------------------------------------- registry


def read_installed() -> tuple[str | None, Path | None]:
    """Return the registered version and install location, if any."""

    winreg = _winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, logic.UNINSTALL_KEY, 0, winreg.KEY_READ
        ) as key:
            version, _ = winreg.QueryValueEx(key, "DisplayVersion")
            location, _ = winreg.QueryValueEx(key, "InstallLocation")
    except (FileNotFoundError, OSError):
        return None, None
    return str(version), logic.absolute_location(str(location))


def write_uninstall_entry(values: tuple[logic.RegistryValue, ...]) -> None:
    winreg = _winreg()
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, logic.UNINSTALL_KEY, 0, winreg.KEY_WRITE
    ) as key:
        for value in values:
            winreg.SetValueEx(key, value.name, 0, _reg_type(value.kind), value.value)


def delete_uninstall_entry() -> None:
    winreg = _winreg()
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, logic.UNINSTALL_KEY)
    except (FileNotFoundError, OSError):
        # Already gone. An uninstall that runs twice is not a failure.
        pass


# ------------------------------------------------------------------- processes


def is_app_running() -> bool:
    """Whether the application is running, via tasklist.

    Replacing a running executable is how an install ends up half applied, so
    every action is gated on this.
    """

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {logic.EXE_NAME}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=_CREATE_NO_WINDOW,
            check=False,
        )
    except OSError:  # pragma: no cover - tasklist is always present on Windows
        return False
    return logic.EXE_NAME.lower() in result.stdout.lower()


def launch(exe_path: Path):
    """Start the installed application, returning the process or None."""

    try:
        return subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            creationflags=_DETACHED_PROCESS,
            close_fds=True,
        )
    except OSError:  # pragma: no cover - surfaced by the window as a status
        return None


def bring_process_window_to_front(pid: int) -> bool:
    """Front the window belonging to `pid`, if it has one yet.

    A window that appears after the installer has closed is denied focus by
    Windows and only flashes on the taskbar, so this runs while the installer
    still owns the foreground.
    """

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover - non-Windows
        return False

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    try:
        user32.EnumWindows(_callback, 0)
    except OSError:  # pragma: no cover - defensive
        return False

    if not found:
        return False
    user32.SetForegroundWindow(found[0])
    return True


# ------------------------------------------------------------------- shortcuts


_SHORTCUT_SCRIPT = """
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut('{link}')
$link.TargetPath = '{target}'
$link.WorkingDirectory = '{working_dir}'
$link.Description = '{description}'
{icon_line}
$link.Save()
"""


def create_shortcut(link: Path, target: Path, icon: Path | None) -> None:
    """Write a real .lnk through the Windows scripting host.

    There is no dependency-free Python API for this. A batch file is not a
    shortcut: it has no icon and it flashes a console.
    """

    link.parent.mkdir(parents=True, exist_ok=True)
    script = _SHORTCUT_SCRIPT.format(
        link=link,
        target=target,
        working_dir=target.parent,
        description=logic.APP_DISPLAY_NAME,
        icon_line=f"$link.IconLocation = '{icon}'" if icon else "",
    )
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


def remove_shortcut(link: Path | None) -> None:
    if link is None:
        return
    try:
        link.unlink()
    except (FileNotFoundError, OSError):
        pass


# ------------------------------------------------------------------- removal


def remove_tree_except(target: Path, keep: str) -> None:
    """Delete everything under `target` except the named subdirectory."""

    import shutil

    if not target.exists():
        return
    for entry in target.iterdir():
        if entry.name == keep:
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        except OSError:
            continue


def schedule_self_delete(target: Path) -> None:
    """Hand the last directory to a shell that outlives this process.

    The running uninstaller lives inside the directory being removed, so it
    cannot be the thing that deletes it.
    """

    command = (
        f"timeout /t {_SELF_DELETE_DELAY_SECONDS} /nobreak >nul & "
        f'rmdir /s /q "{target}"'
    )
    try:
        subprocess.Popen(
            ["cmd", "/c", command],
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS,
            close_fds=True,
        )
    except OSError:  # pragma: no cover - defensive
        pass

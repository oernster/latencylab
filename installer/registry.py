"""The HKCU Apps-and-Features entry.

Writing this key is what makes the installation appear in Settings, so an
uninstall is something Windows offers rather than something the user has to
find. HKCU rather than HKLM keeps the whole thing elevation-free.
"""

from __future__ import annotations

from pathlib import Path

from installer.constants import APP_NAME, APP_PUBLISHER, UNINSTALL_FLAG, UNINSTALL_KEY

# Windows records the install size in kibibytes.
BYTES_PER_KIB = 1024

# The Apps list offers Modify and Repair unless told the installer has neither.
NO_MODIFY = 1
NO_REPAIR = 1


def _winreg():
    """Imported lazily so the module can be read and reasoned about anywhere."""

    import winreg

    return winreg


def directory_size_kib(path: Path) -> int:
    """The installed size Windows displays, in kibibytes."""

    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                # A file that vanished mid-scan changes the reported size, not
                # whether the install succeeded.
                continue
    return total // BYTES_PER_KIB


def write_uninstall_entry(
    *,
    install_path: Path,
    uninstaller: Path,
    icon: Path | None,
    version: str,
) -> None:
    winreg = _winreg()

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_WRITE
    ) as key:
        values: list[tuple[str, int, object]] = [
            ("DisplayName", winreg.REG_SZ, APP_NAME),
            ("DisplayVersion", winreg.REG_SZ, version),
            ("Publisher", winreg.REG_SZ, APP_PUBLISHER),
            ("InstallLocation", winreg.REG_SZ, str(install_path)),
            ("UninstallString", winreg.REG_SZ, f'"{uninstaller}" {UNINSTALL_FLAG}'),
            ("NoModify", winreg.REG_DWORD, NO_MODIFY),
            ("NoRepair", winreg.REG_DWORD, NO_REPAIR),
            (
                "EstimatedSize",
                winreg.REG_DWORD,
                directory_size_kib(install_path),
            ),
        ]
        if icon is not None:
            values.append(("DisplayIcon", winreg.REG_SZ, str(icon)))

        for name, value_type, value in values:
            winreg.SetValueEx(key, name, 0, value_type, value)


def delete_uninstall_entry() -> None:
    """Remove the Apps-and-Features entry, tolerating its absence."""

    winreg = _winreg()
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        # Already gone: an uninstall that runs twice is not a failure.
        pass

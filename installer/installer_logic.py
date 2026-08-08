"""Installer decisions, with no Qt, no registry and no subprocess.

Everything the installer decides lives here: where files go, which licence text
to read, how two versions compare, what the install state is and what the
uninstall registration should say. The side effects that carry those decisions
out live in installer_ops.py and the screen that presents them lives in
installer_window.py, so this module is exercised by the test suite exactly like
the application layer of the app it installs.

Nothing here imports from the `latencylab` packages: the installer stays
standalone. Nothing here reads `__file__` either. The bundle root is passed in
by the entry point, whose location is the one the onefile bootstrap defines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

APP_NAME = "LatencyLab"
APP_DISPLAY_NAME = "LatencyLab"
APP_TAGLINE = "Design-time latency exploration for event-driven systems"
APP_PUBLISHER = "Oliver Ernster"
APP_URL = "https://ernster.dev/latencylab/"

# Payload layout produced by buildinstaller.py: payload/LatencyLab/ holds the
# bundle's non-binary files (read by the installer window), payload/LatencyLab.zip
# the full bundle for deployment and the licence texts sit beside them.
PAYLOAD_DIR_NAME = "payload"
MODEL_LICENSE_FILE_NAME = "LICENSE"
UI_LICENSE_FILE_NAME = "LGPL3.txt"
INSTALLER_LICENSE_FILE_NAME = "INSTALLER_LICENSE"
VERSION_FILE_NAME = "VERSION"
EXE_NAME = "LatencyLab.exe"

# The bundle ships as a single zip because Nuitka's onefile build drops loose
# executables and DLLs from an included data directory; the installer extracts it.
PAYLOAD_ARCHIVE_NAME = "LatencyLab.zip"

# The application's icon resolver looks inside an assets directory beside the
# executable, so the installer reads its badge from the same place.
ASSETS_DIR_NAME = "assets"
ICON_FILE_NAME = "latencylab_icon_256.png"
SHORTCUT_ICON_FILE_NAME = "latencylab.ico"

# Per-user locations. No administrator rights are required anywhere here.
ENV_LOCALAPPDATA = "LOCALAPPDATA"
ENV_APPDATA = "APPDATA"
_PROGRAMS_DIR_NAME = "Programs"
_LOCAL_APPDATA_SUBPATH = ("AppData", "Local")
_START_MENU_SUBPATH = ("Microsoft", "Windows", "Start Menu", "Programs")
_DESKTOP_DIR_NAME = "Desktop"
_SHORTCUT_EXT = ".lnk"

# The registered uninstaller is a copy of this installer placed under the
# install root, so Apps and features can re-run it with --uninstall.
UNINSTALLER_SUBDIR = "_uninstall"
UNINSTALLER_NAME = "LatencyLabSetup.exe"
UNINSTALL_FLAG = "--uninstall"

# Under a Nuitka onefile build sys.executable is the unpacked temporary
# bootstrap, so the real launcher is discovered through this variable instead.
NUITKA_ONEFILE_ENV = "NUITKA_ONEFILE_BINARY"
_EXE_SUFFIX = ".exe"

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\LatencyLab"

# So Windows groups the taskbar button and the shortcut under one identity.
APP_AUMID = "uk.codecrafter.latencylab"

# A console-disabled onefile shows no traceback when it dies, so unhandled
# exceptions are appended here for the user to send back.
INSTALLER_LOG_NAME = "latencylab-installer.log"

LICENSE_FALLBACK = "The licence text was not bundled with this installer."
INSTALLER_LICENSE_FALLBACK = (
    "The installer licence notice was not bundled with this installer."
)

_BYTES_PER_KIB = 1024

# Registry value kinds, named here so the decision about what to write stays
# free of winreg; installer_ops maps these onto the winreg constants.
REG_SZ = "sz"
REG_DWORD = "dword"

FALLBACK_VERSION = "0.0.0"


@dataclass(frozen=True, slots=True)
class RegistryValue:
    """One value to write under the HKCU uninstall key."""

    name: str
    kind: str
    value: str | int


class AppState:
    """The installed-versus-bundled relationship, driving the primary action."""

    NOT_INSTALLED = "not_installed"
    UPGRADE = "upgrade"
    REINSTALL = "reinstall"
    DOWNGRADE = "downgrade"


# ----------------------------------------------------------------- user paths


def _local_appdata(local_appdata: str | None, home: Path) -> Path:
    if local_appdata:
        return Path(local_appdata)
    return home.joinpath(*_LOCAL_APPDATA_SUBPATH)


def install_target(local_appdata: str | None, home: Path) -> Path:
    """Return the per-user install directory for the application."""

    return _local_appdata(local_appdata, home) / _PROGRAMS_DIR_NAME / APP_NAME


def start_menu_link(appdata: str | None) -> Path | None:
    """Return the per-user Start Menu shortcut path; None when unavailable."""

    if not appdata:
        return None
    programs = Path(appdata).joinpath(*_START_MENU_SUBPATH)
    return programs / f"{APP_DISPLAY_NAME}{_SHORTCUT_EXT}"


def desktop_link(home: Path) -> Path:
    """Return the per-user Desktop shortcut path."""

    return home / _DESKTOP_DIR_NAME / f"{APP_DISPLAY_NAME}{_SHORTCUT_EXT}"


def uninstaller_path(install_dir: Path) -> Path:
    """Return where the registered uninstaller copy lives under an install."""

    return install_dir / UNINSTALLER_SUBDIR / UNINSTALLER_NAME


# ------------------------------------------------------------------ versioning


def version_tuple(version: str) -> tuple[int, ...]:
    """Return a comparable tuple of the numeric parts of a version string."""

    parts: list[int] = []
    for raw in version.strip().split("."):
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0 or 1 for left < right, left == right or left > right."""

    a = version_tuple(left)
    b = version_tuple(right)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def detect_state(installed: str | None, location: Path | None, bundled: str) -> str:
    """Classify an existing install against the bundled version."""

    if installed is None or location is None or not location.exists():
        return AppState.NOT_INSTALLED
    comparison = compare_versions(bundled or FALLBACK_VERSION, installed)
    if comparison > 0:
        return AppState.UPGRADE
    if comparison < 0:
        return AppState.DOWNGRADE
    return AppState.REINSTALL


def primary_label(state: str, version: str) -> str:
    """Return the primary button caption for an install state."""

    if state == AppState.NOT_INSTALLED:
        return "Install"
    if state == AppState.UPGRADE:
        return f"Upgrade to {version}" if version else "Upgrade"
    if state == AppState.DOWNGRADE:
        return "Reinstall (older)"
    return "Reinstall"


def subtitle_text(state: str) -> str:
    """Return the subtitle reflecting whether this is a fresh install."""

    if state == AppState.NOT_INSTALLED:
        return f"Welcome to the {APP_DISPLAY_NAME} installer"
    return f"{APP_DISPLAY_NAME} is already installed"


# -------------------------------------------------------------------- registry


def dir_size_kb(path: Path) -> int | None:
    """Return the total size of a directory in KiB; None on error."""

    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError:
        return None
    return total // _BYTES_PER_KIB


def display_icon(install_dir: Path) -> str:
    """Return the Apps-list icon path: the .ico when present, else the exe."""

    icon = install_dir / ASSETS_DIR_NAME / SHORTCUT_ICON_FILE_NAME
    return str(icon if icon.exists() else install_dir / EXE_NAME)


def uninstall_entry_values(
    install_dir: Path,
    uninstaller: Path,
    version: str,
    estimated_kb: int | None,
) -> tuple[RegistryValue, ...]:
    """Return every value the HKCU Apps and features registration carries."""

    values = [
        RegistryValue("DisplayName", REG_SZ, APP_DISPLAY_NAME),
        RegistryValue("DisplayVersion", REG_SZ, version),
        RegistryValue("InstallLocation", REG_SZ, str(install_dir)),
        RegistryValue("UninstallString", REG_SZ, f'"{uninstaller}" {UNINSTALL_FLAG}'),
        RegistryValue("DisplayIcon", REG_SZ, display_icon(install_dir)),
        RegistryValue("Publisher", REG_SZ, APP_PUBLISHER),
        RegistryValue("URLInfoAbout", REG_SZ, APP_URL),
        RegistryValue("NoModify", REG_DWORD, 1),
        RegistryValue("NoRepair", REG_DWORD, 1),
    ]
    if estimated_kb is not None:
        values.append(RegistryValue("EstimatedSize", REG_DWORD, estimated_kb))
    return tuple(values)


def absolute_location(raw: str | None) -> Path | None:
    """Return a registered install location; None when it is unusable."""

    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else None


# --------------------------------------------------- the onefile bootstrap trap


def original_installer_exe(
    env_value: str, argv0: str, executable: str, temp_root: Path
) -> Path:
    """Return the original onefile installer the user launched.

    Under a Nuitka onefile build `sys.executable` is the unpacked temporary
    bootstrap rather than the launcher. Registering that as the uninstaller
    registers a path that stops existing. The real launcher is exposed through
    NUITKA_ONEFILE_BINARY and as `sys.argv[0]`, so those come first and
    `sys.executable` is used only when neither resolves outside the temporary
    directory.
    """

    for raw in (env_value, argv0):
        if not raw:
            continue
        path = Path(raw).resolve()
        if path.suffix.lower() != _EXE_SUFFIX or not path.is_file():
            continue
        if path == temp_root or temp_root in path.parents:
            continue
        return path
    return Path(executable)

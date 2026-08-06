"""Build the LatencyLab Windows bundle with Nuitka.

Produces `installer/payload/LatencyLab/LatencyLab.exe` and everything beside it.
`buildinstaller.py` then wraps that directory into the setup program, so this
script never produces something a user installs directly.

    python buildexe.py            # release, no console
    set LATENCYLAB_BUILD_DEBUG=1  # keep a console attached for tracebacks
    python buildexe.py

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import stamp_version
from build_utils import (
    PROJECT_ROOT,
    VERSION_FILE,
    pe_version,
    read_version,
    remove_tree,
    require_windows,
    run,
    section,
)

APP_DISPLAY_NAME = "LatencyLab"
EXE_NAME = "LatencyLab"
APP_AUTHOR = "Oliver Ernster"

# What Windows shows as the process name in Task Manager and in the "open with"
# dialog. It is the application's NAME, never its tagline: a marketing sentence
# here is what Windows then lists the program as.
FILE_DESCRIPTION = "LatencyLab"

# The repo-root shim is already the canonical launcher, so the frozen build and
# `python runner.py` enter through exactly the same code.
ENTRY_SCRIPT = PROJECT_ROOT / "runner.py"

ICON_FILE = PROJECT_ROOT / "assets" / "latencylab.ico"

# Loose files the bundle needs at the paths the running app looks for them:
# version.py reads VERSION from the bundle root, main_licence_dialog.py reads
# LICENSE from the bundle root and licence_dialog.py reads LGPL3.txt from beside
# its own module.
DATA_FILES: tuple[tuple[Path, str], ...] = (
    (VERSION_FILE, "VERSION"),
    (PROJECT_ROOT / "LICENSE", "LICENSE"),
    (
        PROJECT_ROOT / "latencylab_ui" / "LGPL3.txt",
        "latencylab_ui/LGPL3.txt",
    ),
)

# Whole directories: the generated icons the resolver looks for beside the exe,
# and the example models, so a fresh install has something to open.
DATA_DIRS: tuple[tuple[Path, str], ...] = (
    (PROJECT_ROOT / "assets", "assets"),
    (PROJECT_ROOT / "examples", "examples"),
)

PAYLOAD_DIR = PROJECT_ROOT / "installer" / "payload"
BUNDLE_DIR = PAYLOAD_DIR / APP_DISPLAY_NAME

# Nuitka names its standalone output after the entry script.
NUITKA_OUTPUT_DIR = PAYLOAD_DIR / f"{ENTRY_SCRIPT.stem}.dist"

DEBUG_ENV_VAR = "LATENCYLAB_BUILD_DEBUG"
CONSOLE_MODE_RELEASE = "disable"
CONSOLE_MODE_DEBUG = "attach"


def _debug_requested() -> bool:
    return os.environ.get(DEBUG_ENV_VAR, "").strip() not in ("", "0", "false")


def _nuitka_command(version: str) -> list[str]:
    console_mode = CONSOLE_MODE_DEBUG if _debug_requested() else CONSOLE_MODE_RELEASE
    numeric_version = pe_version(version)

    command = [
        "python",
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        f"--jobs={os.cpu_count() or 1}",
        f"--windows-console-mode={console_mode}",
        f"--output-dir={PAYLOAD_DIR}",
        f"--output-filename={EXE_NAME}.exe",
        f"--company-name={APP_AUTHOR}",
        f"--product-name={APP_DISPLAY_NAME}",
        f"--file-version={numeric_version}",
        f"--product-version={numeric_version}",
        f"--file-description={FILE_DESCRIPTION}",
        f"--copyright=Copyright {APP_AUTHOR}",
    ]

    if ICON_FILE.is_file():
        command.append(f"--windows-icon-from-ico={ICON_FILE}")
    else:
        print(f"WARNING: {ICON_FILE} is missing. Run `python generate_icons.py`.")

    for source, destination in DATA_FILES:
        command.append(f"--include-data-file={source}={destination}")
    for source, destination in DATA_DIRS:
        command.append(f"--include-data-dir={source}={destination}")

    # The entry script is always last.
    command.append(str(ENTRY_SCRIPT))
    return command


def main() -> int:
    require_windows()

    section("Stamping the version into the static documents")
    stamp_version.main()

    version = read_version()
    print(f"Building {APP_DISPLAY_NAME} {version} (PE {pe_version(version)})")

    section("Clearing the previous bundle")
    remove_tree(NUITKA_OUTPUT_DIR)
    remove_tree(BUNDLE_DIR)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    section("Running Nuitka")
    run(_nuitka_command(version), cwd=PROJECT_ROOT)

    section("Staging the bundle")
    if not NUITKA_OUTPUT_DIR.is_dir():
        raise SystemExit(f"Nuitka produced no bundle at {NUITKA_OUTPUT_DIR}")
    shutil.move(str(NUITKA_OUTPUT_DIR), str(BUNDLE_DIR))

    executable = BUNDLE_DIR / f"{EXE_NAME}.exe"
    if not executable.is_file():
        raise SystemExit(f"Expected an executable at {executable}")

    print(f"\nBuilt {executable}")
    print("Next: python buildinstaller.py")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Wrap the built bundle into the LatencyLab setup program.

Run `python buildexe.py` first. This zips the bundle it produced, then builds
the bespoke PySide6 installer as a single onefile executable carrying that zip
as opaque data.

    python buildinstaller.py   ->   dist-installer/LatencyLabSetup.exe

Why a zip rather than the directory: a Nuitka onefile build strips loose
executables and DLLs out of an `--include-data-dir`, so a payload staged as
loose files loses exactly the parts that matter. Zipped, it is opaque data the
installer extracts at deploy time.

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
    publish,
    read_version,
    remove_file,
    remove_tree,
    require_windows,
    run,
    section,
)

APP_DISPLAY_NAME = "LatencyLab"
APP_AUTHOR = "Oliver Ernster"
INSTALLER_NAME = f"{APP_DISPLAY_NAME}Setup"

# The process name Windows shows for the setup program. As with the app itself,
# this is a name and never a tagline.
FILE_DESCRIPTION = f"{APP_DISPLAY_NAME} Setup"

INSTALLER_ENTRY = PROJECT_ROOT / "installer" / "app.py"
PAYLOAD_DIR = PROJECT_ROOT / "installer" / "payload"
BUNDLE_DIR = PAYLOAD_DIR / APP_DISPLAY_NAME
PAYLOAD_ZIP = PAYLOAD_DIR / f"{APP_DISPLAY_NAME}.zip"

ICON_FILE = PROJECT_ROOT / "assets" / "latencylab.ico"

# Staged beside the zip so the installer window can show them before the user
# commits to anything. The UI licence is copied out of the package it belongs
# to, so there is only ever one copy of the text in the repository.
STAGED_FILES: tuple[tuple[Path, str], ...] = (
    (VERSION_FILE, "VERSION"),
    (PROJECT_ROOT / "LICENSE", "LICENSE"),
    (PROJECT_ROOT / "latencylab_ui" / "LGPL3.txt", "LGPL3.txt"),
    (PROJECT_ROOT / "INSTALLER_LICENSE", "INSTALLER_LICENSE"),
)

# The installer window shows the app's own badge, so the generated icons ship
# inside the payload directory as well as inside the zip.
STAGED_ASSETS_DIR = PROJECT_ROOT / "assets"

# Build into a temp directory and move, so a locked previous exe fails the move
# rather than the build.
TEMP_DIST_DIR = PROJECT_ROOT / "dist-installer.build"
DIST_DIR = PROJECT_ROOT / "dist-installer"


def stage_payload() -> None:
    if not BUNDLE_DIR.is_dir():
        raise SystemExit(f"No bundle at {BUNDLE_DIR}. Run `python buildexe.py` first.")

    remove_file(PAYLOAD_ZIP)
    shutil.make_archive(str(BUNDLE_DIR), "zip", root_dir=BUNDLE_DIR)

    for source, name in STAGED_FILES:
        if not source.is_file():
            raise SystemExit(f"Missing file to stage: {source}")
        shutil.copy2(source, PAYLOAD_DIR / name)

    staged_assets = PAYLOAD_DIR / STAGED_ASSETS_DIR.name
    remove_tree(staged_assets)
    if STAGED_ASSETS_DIR.is_dir():
        shutil.copytree(STAGED_ASSETS_DIR, staged_assets)
    else:
        print(f"WARNING: {STAGED_ASSETS_DIR} is missing. Run generate_icons.py.")


def _nuitka_command(version: str) -> list[str]:
    numeric_version = pe_version(version)

    command = [
        "python",
        "-m",
        "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        f"--jobs={os.cpu_count() or 1}",
        "--windows-console-mode=disable",
        f"--output-dir={TEMP_DIST_DIR}",
        f"--output-filename={INSTALLER_NAME}.exe",
        f"--company-name={APP_AUTHOR}",
        f"--product-name={APP_DISPLAY_NAME} Setup",
        f"--file-version={numeric_version}",
        f"--product-version={numeric_version}",
        f"--file-description={FILE_DESCRIPTION}",
        f"--copyright=Copyright {APP_AUTHOR}",
        f"--include-data-dir={PAYLOAD_DIR}=payload",
    ]

    if ICON_FILE.is_file():
        command.append(f"--windows-icon-from-ico={ICON_FILE}")

    command.append(str(INSTALLER_ENTRY))
    return command


def main() -> int:
    require_windows()

    section("Stamping the version into the static documents")
    stamp_version.main()

    version = read_version()
    print(f"Packaging {INSTALLER_NAME} for {APP_DISPLAY_NAME} {version}")

    section("Staging the payload")
    stage_payload()
    print(f"Payload zipped to {PAYLOAD_ZIP}")

    section("Building the installer")
    remove_tree(TEMP_DIST_DIR)
    run(_nuitka_command(version), cwd=PROJECT_ROOT)

    section("Publishing")
    built = TEMP_DIST_DIR / f"{INSTALLER_NAME}.exe"
    if not built.is_file():
        raise SystemExit(f"Nuitka produced no installer at {built}")

    published = publish(built, DIST_DIR / f"{INSTALLER_NAME}.exe")
    remove_tree(TEMP_DIST_DIR)

    print(f"\nBuilt {published}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

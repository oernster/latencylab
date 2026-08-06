"""Build a signed, optionally notarised macOS DMG for LatencyLab.

Run on macOS from the repository root with the virtual environment active:

    python builddmg.py

Signing uses DEVELOPER_ID_APPLICATION if set. Notarisation runs only when both
APPLE_ID and APPLE_APP_PASSWORD are present, so an unnotarised local build is
the default rather than a failure.

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import stamp_version
from build_utils import PROJECT_ROOT, VERSION_FILE, read_version, remove_tree, section
from dmg_icon import png_to_icns, set_volume_icon

APP_NAME = "LatencyLab"
BUNDLE_ID = "uk.codecrafter.LatencyLab"
ENTRY_SCRIPT = PROJECT_ROOT / "runner.py"

DIST_DIR = PROJECT_ROOT / "dist"
WORK_DIR = PROJECT_ROOT / "build"
APP_BUNDLE = DIST_DIR / f"{APP_NAME}.app"

ICNS_SOURCE_PNG = PROJECT_ROOT / "assets" / "latencylab_icon_1024.png"
ICNS_FILE = PROJECT_ROOT / "assets" / "latencylab.icns"

# Arch-tagged, so nobody reinstalls a stale same-named DMG out of Downloads.
DMG_ARCH = "arm64"

DEVELOPER_ID = os.environ.get(
    "DEVELOPER_ID_APPLICATION",
    "Developer ID Application: Oliver Ernster (W7K465GKFJ)",
)
APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "W7K465GKFJ")

# LatencyLab is a plain Qt application: no web engine, so no JIT entitlement.
# The one entitlement it needs is to load the Qt frameworks we signed ourselves.
ENTITLEMENTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
"""

# Data staged into the bundle, at the paths the running app reads them from.
DATA_FILES: tuple[tuple[Path, str], ...] = (
    (VERSION_FILE, "."),
    (PROJECT_ROOT / "LICENSE", "."),
    (PROJECT_ROOT / "latencylab_ui" / "LGPL3.txt", "latencylab_ui"),
)
DATA_DIRS: tuple[tuple[Path, str], ...] = (
    (PROJECT_ROOT / "assets", "assets"),
    (PROJECT_ROOT / "examples", "examples"),
)

# create-dmg reports 2 when it cannot set a custom window background, which is
# normal on a headless machine and is not a failure.
CREATE_DMG_OK_CODES = (0, 2)

DMG_WINDOW_SIZE = ("640", "400")
DMG_ICON_SIZE = "128"
DMG_APP_POSITION = ("160", "200")
DMG_LINK_POSITION = ("480", "200")


def require(tool: str, brew_formula: str | None = None) -> None:
    if shutil.which(tool):
        return
    formula = brew_formula or tool
    print(f"{tool} is missing; installing {formula} with Homebrew")
    subprocess.run(["brew", "install", formula], check=True)
    if not shutil.which(tool):
        raise SystemExit(f"{tool} is still unavailable after installing {formula}")


def run(command: list[str], *, check: bool = True) -> int:
    print("$ " + " ".join(command))
    return subprocess.run(command, check=check).returncode


def build_app(entitlements: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        f"--name={APP_NAME}",
        f"--distpath={DIST_DIR}",
        f"--workpath={WORK_DIR}",
        f"--icon={ICNS_FILE}",
        f"--osx-bundle-identifier={BUNDLE_ID}",
        f"--codesign-identity={DEVELOPER_ID}",
        f"--osx-entitlements-file={entitlements}",
        "--collect-submodules=latencylab",
        "--collect-submodules=latencylab_ui",
    ]
    for source, destination in DATA_FILES + DATA_DIRS:
        command.append(f"--add-data={source}{os.pathsep}{destination}")
    command.append(str(ENTRY_SCRIPT))
    run(command)


def strip_object_files(bundle: Path) -> None:
    """Remove the stray Mach-O object files PySide6 ships in its QML plugins.

    `codesign --deep` silently skips a `.o` and Gatekeeper then rejects the
    bundle for containing unsigned code. Deleting them is the fix; they are
    build residue and nothing loads them.
    """

    removed = 0
    for path in bundle.rglob("*.o"):
        path.unlink()
        removed += 1
    for path in sorted(bundle.rglob("objects-*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    print(f"Removed {removed} stray object files")


def sign(target: Path, entitlements: Path) -> None:
    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements),
            "--sign",
            DEVELOPER_ID,
            str(target),
        ]
    )
    run(["codesign", "--verify", "--deep", "--strict", str(target)])


def create_dmg(version: str, staging: Path) -> Path:
    dmg = DIST_DIR / f"{APP_NAME.lower()}-{version}-macos-{DMG_ARCH}.dmg"
    if dmg.exists():
        dmg.unlink()

    code = run(
        [
            "create-dmg",
            "--volname",
            f"{APP_NAME} {version}",
            "--window-size",
            *DMG_WINDOW_SIZE,
            "--icon-size",
            DMG_ICON_SIZE,
            "--icon",
            f"{APP_NAME}.app",
            *DMG_APP_POSITION,
            "--app-drop-link",
            *DMG_LINK_POSITION,
            str(dmg),
            str(staging),
        ],
        check=False,
    )
    if code not in CREATE_DMG_OK_CODES:
        raise SystemExit(f"create-dmg failed with exit code {code}")
    return dmg


def notarise(dmg: Path) -> None:
    if not (APPLE_ID and APPLE_APP_PASSWORD):
        print("APPLE_ID or APPLE_APP_PASSWORD unset: skipping notarisation")
        return

    run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(dmg),
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
            "--wait",
        ]
    )
    run(["xcrun", "stapler", "staple", str(dmg)])


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("builddmg.py runs on macOS only.")

    require("create-dmg")
    require("codesign")

    section("Stamping the version into the static documents")
    stamp_version.main()
    version = read_version()

    section("Clearing previous output")
    remove_tree(DIST_DIR)
    remove_tree(WORK_DIR)

    section("Preparing the icon")
    if not ICNS_FILE.is_file():
        raise SystemExit(f"{ICNS_FILE} is missing. Run `python generate_icons.py`.")

    handle, entitlements_path = tempfile.mkstemp(suffix=".plist")
    entitlements = Path(entitlements_path)
    os.close(handle)
    entitlements.write_text(ENTITLEMENTS_XML, encoding="utf-8")

    try:
        section("Building the application bundle")
        build_app(entitlements)
        if not APP_BUNDLE.is_dir():
            raise SystemExit(f"PyInstaller produced no bundle at {APP_BUNDLE}")

        section("Stripping stray object files")
        strip_object_files(APP_BUNDLE)

        section("Signing the bundle")
        sign(APP_BUNDLE, entitlements)

        section("Creating the disk image")
        staging = WORK_DIR / "dmg"
        remove_tree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        # ditto rather than copytree: it preserves the framework symlinks whose
        # replacement would invalidate the signature just applied.
        run(["ditto", str(APP_BUNDLE), str(staging / APP_BUNDLE.name)])
        dmg = create_dmg(version, staging)

        section("Setting the volume icon")
        try:
            png_to_icns(ICNS_SOURCE_PNG, WORK_DIR / "volume.icns", WORK_DIR)
            set_volume_icon(dmg, WORK_DIR / "volume.icns", WORK_DIR)
        except (subprocess.CalledProcessError, OSError) as error:
            print(f"Volume icon skipped: {error}")

        section("Signing the disk image")
        run(["codesign", "--force", "--sign", DEVELOPER_ID, str(dmg)])

        section("Notarising")
        notarise(dmg)

        print(f"\nBuilt {dmg}")
    finally:
        entitlements.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

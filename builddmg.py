"""Build a signed, optionally notarised macOS DMG for LatencyLab.

Run on macOS from the repository root with the virtual environment active:

    pip install -e .[build]
    python builddmg.py   ->   latencylab.dmg

PyInstaller comes from that build extra and is checked for before anything is
built, so a missing one costs a second rather than a failed ten-minute run.

Signing uses DEVELOPER_ID_APPLICATION if set. Notarisation runs only when both
APPLE_ID and APPLE_APP_PASSWORD are present, so an unnotarised local build is
the default rather than a failure.

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import stamp_version
from build_utils import (
    PROJECT_ROOT,
    VERSION_FILE,
    read_version,
    remove_file,
    remove_tree,
    section,
)
from dmg_icon import png_to_icns, set_file_icon

APP_NAME = "LatencyLab"
APP_AUTHOR = "Oliver Ernster"
# The same string buildexe.py writes into the Windows resource block.
COPYRIGHT = f"Copyright {APP_AUTHOR}"
BUNDLE_ID = "uk.codecrafter.LatencyLab"
ENTRY_SCRIPT = PROJECT_ROOT / "runner.py"

DIST_DIR = PROJECT_ROOT / "dist"
WORK_DIR = PROJECT_ROOT / "build"
APP_BUNDLE = DIST_DIR / f"{APP_NAME}.app"

# The opaque macOS variant, not the transparent one the other platforms use:
# the disk image icon is drawn onto the Finder window and the desktop, where a
# transparent canvas leaves the mark sitting on pale grey. See generate_icons.py.
ICNS_SOURCE_PNG = PROJECT_ROOT / "assets" / "latencylab_icon_mac_1024.png"
ICNS_FILE = PROJECT_ROOT / "assets" / "latencylab.icns"

# The DMG lands at the repository root under a fixed name, because that is
# where the person who ran the build looks for it. dist/ is PyInstaller's
# scratch space and gets deleted at the start of every run.
DMG_FILE = PROJECT_ROOT / f"{APP_NAME.lower()}.dmg"

# The version and the architecture the name no longer carries. They travel in
# the volume name instead, so a mounted image still says which build it is.
# PyInstaller builds for the interpreter running it, so the build machine is
# what this has to report; it was hardcoded and labelled an Intel build arm64.
DMG_ARCH = platform.machine()

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


def require_brew(tool: str, brew_formula: str | None = None) -> None:
    """Install a Homebrew-provided tool if it is absent."""

    if shutil.which(tool):
        return
    formula = brew_formula or tool
    print(f"{tool} is missing; installing {formula} with Homebrew")
    subprocess.run(["brew", "install", formula], check=True)
    if not shutil.which(tool):
        raise SystemExit(f"{tool} is still unavailable after installing {formula}")


def require_xcode(tool: str) -> None:
    """Fail with the command that actually supplies an Xcode tool.

    codesign is not a Homebrew formula, so routing it through require_brew
    produced `brew install codesign` and an error naming the wrong problem.
    """

    if shutil.which(tool):
        return
    raise SystemExit(
        f"{tool} is missing. Install the Xcode command line tools with "
        "`xcode-select --install`."
    )


def require_pyinstaller() -> None:
    """Check the build dependency in this interpreter, not on PATH.

    The build runs `sys.executable -m PyInstaller`, so a PyInstaller installed
    elsewhere on PATH does not count. Without this the build died several
    minutes in on a bare `No module named PyInstaller`.
    """

    if importlib.util.find_spec("PyInstaller") is not None:
        return
    raise SystemExit(
        f"PyInstaller is not installed in {sys.executable}. "
        "Install the build extra with `pip install -e .[build]`."
    )


def run(command: list[str], *, check: bool = True) -> int:
    """Run a command, echoing it, and abort the build cleanly if it fails.

    `check` here means "abort", not "raise": a build script failing on a
    traceback out of subprocess buries the command that actually failed.
    """

    print("$ " + " ".join(command), flush=True)
    code = subprocess.run(command).returncode
    if check and code != 0:
        raise SystemExit(f"Command failed with exit code {code}: {command[0]}")
    return code


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


def stamp_bundle_version(bundle: Path, version: str) -> None:
    """Write the release version into the bundle's Info.plist.

    PyInstaller has no command line option for the macOS bundle version, so it
    writes its own default and the shipped app reported 0.0.0 in Finder's Get
    Info while VERSION said otherwise. This has to run before signing, because
    Info.plist is part of what the signature seals.
    """

    info_plist = bundle / "Contents" / "Info.plist"
    info = plistlib.loads(info_plist.read_bytes())
    info["CFBundleShortVersionString"] = version
    info["CFBundleVersion"] = version
    info["NSHumanReadableCopyright"] = COPYRIGHT
    info_plist.write_bytes(plistlib.dumps(info))
    print(f"Stamped {info_plist.name} with version {version}")


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


def create_dmg(version: str, staging: Path, volume_icon: Path | None) -> Path:
    dmg = DMG_FILE
    remove_file(dmg)

    command = [
        "create-dmg",
        "--volname",
        f"{APP_NAME} {version} ({DMG_ARCH})",
    ]
    # create-dmg sets the mounted volume's icon itself, and gets the
    # custom-icon bit to survive compression, which doing it by hand afterwards
    # did not.
    if volume_icon is not None:
        command += ["--volicon", str(volume_icon)]

    code = run(
        command
        + [
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

    require_pyinstaller()
    require_brew("create-dmg")
    require_xcode("codesign")

    section("Stamping the version into the static documents")
    stamp_version.main()
    version = read_version()

    section("Clearing previous output")
    remove_tree(DIST_DIR)
    remove_tree(WORK_DIR)
    remove_file(DMG_FILE)

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

        section("Stamping the bundle version")
        stamp_bundle_version(APP_BUNDLE, version)

        section("Stripping stray object files")
        strip_object_files(APP_BUNDLE)

        section("Signing the bundle")
        sign(APP_BUNDLE, entitlements)

        section("Staging the bundle for the disk image")
        staging = WORK_DIR / "dmg"
        remove_tree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        # ditto rather than copytree: it preserves the framework symlinks whose
        # replacement would invalidate the signature just applied.
        run(["ditto", str(APP_BUNDLE), str(staging / APP_BUNDLE.name)])

        # Built before the image, because create-dmg wants the volume icon at
        # creation time. A failure costs icons and nothing else, so the build
        # carries on without one.
        section("Building the disk image icon")
        volume_icon: Path | None = None
        try:
            volume_icon = png_to_icns(
                ICNS_SOURCE_PNG, WORK_DIR / f"{APP_NAME}.icns", WORK_DIR
            )
        except (subprocess.CalledProcessError, OSError) as error:
            print(f"Disk image icon skipped: {error}")

        section("Creating the disk image")
        dmg = create_dmg(version, staging, volume_icon)

        # After the image exists and before it is signed: this writes a
        # resource fork, and the signature should seal the finished file.
        section("Setting the disk image file icon")
        if volume_icon is None:
            print("No icon was built: leaving the generic disk image icon")
        else:
            try:
                set_file_icon(dmg, volume_icon, WORK_DIR)
            except (subprocess.CalledProcessError, OSError) as error:
                print(f"File icon skipped: {error}")

        section("Signing the disk image")
        run(["codesign", "--force", "--sign", DEVELOPER_ID, str(dmg)])
        run(["codesign", "--verify", "--strict", str(dmg)])

        section("Notarising")
        notarise(dmg)

        print(f"\nBuilt {dmg}")
    finally:
        entitlements.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

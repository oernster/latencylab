"""Build a signed, optionally notarised macOS DMG for LatencyLab.

Run on macOS from the repository root with the virtual environment active:

    pip install -e .[build]
    python builddmg.py   ->   latencylab.dmg

PyInstaller comes from that build extra and is checked for before anything is
built, so a missing one costs a second rather than a failed ten-minute run.

Signing uses DEVELOPER_ID_APPLICATION if set. Notarisation is mandatory: a
Developer ID signature alone is not enough, because since macOS 10.15 Gatekeeper
rejects signed-but-unnotarised apps with "Apple could not verify ... is free of
malware". APPLE_ID and APPLE_APP_PASSWORD must both be set or the build stops
before anything is built. Set ALLOW_UNNOTARIZED=1 for a local test build; the
result must never be published as a release artifact.

This is a build script. It is exempt from the size cap and from the coverage
gate.
"""

from __future__ import annotations

import importlib.util
import os
import re
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

import stamp_version
from packaging.requirements import InvalidRequirement, Requirement
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

# Notarisation credentials live in the keychain under one profile per app, each
# holding its own app-specific password, so a leaked credential can be revoked
# for a single app. The profile defaults to this app's name: running the build
# from the repo picks up the right credential with nothing to export, and no
# other app's profile can be used by accident. Set APPLE_KEYCHAIN_PROFILE to
# override. Create it with:
#   xcrun notarytool store-credentials <app> \
#     --apple-id <id> --team-id <team> --password <app-specific>
NOTARY_PROFILE = os.environ.get("APPLE_KEYCHAIN_PROFILE", "") or APP_NAME

# The notary service accepts only an app-specific password from appleid.apple.com
# and rejects the Apple account password with HTTP 401. The shape is distinctive,
# so it is checked before the build rather than discovered after it.
APP_SPECIFIC_PASSWORD_RE = re.compile(r"^[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}$")

# Escape hatch for local test builds. Distribution builds must never set this:
# an unnotarised DMG is rejected by Gatekeeper on every machine but the one that
# signed it, and the failure is invisible at build time.
ALLOW_UNNOTARIZED = os.environ.get("ALLOW_UNNOTARIZED", "") == "1"
# Notarisation is the default and the keychain profile always resolves, so the
# only way to skip it is to ask for that explicitly.
NOTARISING = not ALLOW_UNNOTARIZED

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
    """Run a command, echoing it, then abort the build cleanly if it fails.

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
    # create-dmg sets the mounted volume's icon itself and gets the
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


def require_notarisation_credentials() -> None:
    """Stop before the build starts if the release cannot be notarised.

    Checked alongside the other tool requirements so a missing password costs a
    second rather than a failed ten-minute run, the same reasoning that puts the
    PyInstaller check up front.
    """
    if ALLOW_UNNOTARIZED:
        print("ALLOW_UNNOTARIZED=1: local test build, do not release the result")
        return
    if APPLE_ID and APPLE_APP_PASSWORD:
        if not APP_SPECIFIC_PASSWORD_RE.match(APPLE_APP_PASSWORD):
            raise SystemExit(
                "APPLE_APP_PASSWORD is not an app-specific password.\n"
                "Expected four lowercase groups of four, like abcd-efgh-ijkl-mnop.\n"
                "An Apple account password is rejected by the notary service with\n"
                "'HTTP status code: 401. Invalid credentials'.\n"
                "Generate one at https://appleid.apple.com (Sign-In and Security,\n"
                "App-Specific Passwords), or leave both variables unset and store\n"
                f"the credential in the keychain as profile {NOTARY_PROFILE}."
            )
        print(f"Notarising as {APPLE_ID} (team {APPLE_TEAM_ID})")
        return
    print(f"Notarising with keychain profile {NOTARY_PROFILE}")


def notarytool_submit(target: Path) -> None:
    """Submit target to Apple and wait for the verdict.

    A failed submission stops the build rather than leaving an artifact that
    looks distributable. subprocess is called directly rather than through run()
    so that neither the echoed command nor the failure path exposes the
    password. Stapling is separate because the submitted file and the file that
    carries the ticket differ for a bundle: a zip goes up, the .app gets
    stapled.
    """
    cmd = [
        "xcrun",
        "notarytool",
        "submit",
        str(target),
        *notarytool_credentials(),
        "--wait",
    ]
    print(f"$ {redact(cmd)}")
    if subprocess.run(cmd, check=False).returncode == 0:
        return
    raise SystemExit(
        "Notarisation failed (notarytool output above).\n"
        "'HTTP status code: 401' means the credential is wrong: use an\n"
        "app-specific password from https://appleid.apple.com, not your Apple\n"
        "account password.\n"
        "For an 'Invalid' verdict, the per-binary reasons are in:\n"
        f"  xcrun notarytool log <submission-id> --apple-id "
        f"{APPLE_ID or '<apple-id>'} --team-id {APPLE_TEAM_ID}"
    )


def notarytool_credentials() -> list[str]:
    """Authentication arguments for notarytool.

    An explicit APPLE_ID and APPLE_APP_PASSWORD pair wins, for CI that has no
    keychain. Otherwise the per-app profile is used, which keeps the secret out
    of the process arguments where any other process could read it via ps.
    """
    if APPLE_ID and APPLE_APP_PASSWORD:
        return [
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
        ]
    return ["--keychain-profile", NOTARY_PROFILE]


def check_runtime_dependencies() -> None:
    """Fail if anything in requirements.txt is absent from the build interpreter.

    PyInstaller only warns when a package it is told to collect cannot be found,
    so a stale venv yields a bundle that builds, signs and notarises cleanly and
    then dies at launch with ModuleNotFoundError. Checking the interpreter that
    is about to be frozen turns a silent runtime failure into a build failure.
    """
    requirements = PROJECT_ROOT / "requirements.txt"
    if not requirements.is_file():
        raise SystemExit(f"{requirements} is missing.")

    missing: list[str] = []
    checked = 0
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as error:
            raise SystemExit(f"Cannot parse '{line}' in {requirements}: {error}")
        # A marker such as sys_platform == "win32" means the package is not
        # wanted here, so its absence is correct rather than a fault.
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        checked += 1
        try:
            metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            missing.append(requirement.name)

    if missing:
        raise SystemExit(
            f"The build interpreter is missing {len(missing)} of {checked} "
            "requirements:\n"
            + "".join(f"  {name}\n" for name in missing)
            + "PyInstaller would omit them and the app would crash at launch with\n"
            "ModuleNotFoundError. Install them first:\n"
            "  pip install -e .[build]"
        )
    print(f"All {checked} requirements present")


def redact(cmd: list[str]) -> str:
    """Render a command with the value after --password masked.

    run() echoes every command it runs, and CalledProcessError repeats the whole
    argument list in its traceback. Both would otherwise copy the app-specific
    password into build logs and CI output.
    """
    parts: list[str] = []
    mask_next = False
    for arg in (str(c) for c in cmd):
        parts.append("********" if mask_next else arg)
        mask_next = arg == "--password"
    return " ".join(parts)


def notarise_bundle(bundle: Path) -> None:
    """Notarise and staple the .app before it is staged into the disk image.

    Stapling only the DMG leaves the copied-out .app with no local ticket, so
    Gatekeeper falls back to an online check and the app fails to launch for
    anyone offline or behind a restrictive network. notarytool takes archives
    only, so ditto zips the bundle first; the ticket goes on the bundle, since a
    zip cannot carry one.
    """
    if not NOTARISING:
        return
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{APP_NAME}.zip"
        run(["ditto", "-c", "-k", "--keepParent", str(bundle), str(archive)])
        notarytool_submit(archive)
    run(["xcrun", "stapler", "staple", str(bundle)])


def notarise(dmg: Path) -> None:
    if not NOTARISING:
        print("ALLOW_UNNOTARIZED=1: skipping notarisation, do not release this DMG")
        return
    notarytool_submit(dmg)
    run(["xcrun", "stapler", "staple", str(dmg)])
    # stapler validate proves a ticket is attached; spctl replays the check
    # Gatekeeper runs on the end user's machine. Together they catch the silent
    # case where signing succeeded but notarisation never happened.
    run(["xcrun", "stapler", "validate", str(dmg)])
    run(["spctl", "--assess", "--type", "install", "-vv", str(dmg)])


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("builddmg.py runs on macOS only.")

    require_pyinstaller()
    require_brew("create-dmg")
    require_xcode("codesign")
    check_runtime_dependencies()
    require_notarisation_credentials()

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

        # Before staging, so the copy that lands in the image already carries a
        # ticket and validates without a network round trip.
        section("Notarising the bundle")
        notarise_bundle(APP_BUNDLE)

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
        # resource fork; the signature should seal the finished file.
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

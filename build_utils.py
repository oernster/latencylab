"""Helpers shared by the delivery scripts.

`buildexe.py`, `buildinstaller.py` and `builddmg.py` all need the same handful
of things: the version, a subprocess runner that fails loudly, a readable
section header and a directory remover that survives a virus scanner holding a
file open. They live here so the three recipes stay recipes.

This is a build script. It is exempt from the size cap and from the coverage
gate, because what it does is only meaningful against a real toolchain.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_ROOT / "VERSION"

# Matches latencylab/version.py, so a packaging accident produces the same
# obviously-wrong number everywhere rather than a different one per script.
FALLBACK_VERSION = "0.0.0-dev"

# A Windows PE version is exactly four numeric parts.
PE_VERSION_PARTS = 4

# Windows keeps files open behind the build: Explorer previews, the indexer and
# antivirus all do it, and a scanner can hold a freshly written executable for
# several seconds. Retrying beats failing a ten-minute build, so the window is
# generous rather than token.
UNLINK_RETRIES = 40
UNLINK_DELAY_SECONDS = 0.25


def read_version(version_file: Path = VERSION_FILE) -> str:
    """The single source of truth, read the same way the runtime reads it."""

    try:
        return version_file.read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    except OSError:
        return FALLBACK_VERSION


def pe_version(version: str) -> str:
    """A four-part numeric PE version derived from the release version.

    Non-numeric characters are dropped per segment and the result is padded or
    truncated to exactly four parts, so `2.2.0` becomes `2.2.0.0` and
    `2.2.0-rc1` becomes `2.2.0.1` rather than failing the resource compiler.
    """

    parts: list[str] = []
    for segment in version.replace("-", ".").split("."):
        digits = "".join(character for character in segment if character.isdigit())
        parts.append(digits or "0")

    parts = parts[:PE_VERSION_PARTS]
    while len(parts) < PE_VERSION_PARTS:
        parts.append("0")
    return ".".join(parts)


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def run(command: list[str], *, cwd: Path | None = None) -> None:
    """Run a command, echoing it, then abort the build if it fails."""

    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed with exit code {result.returncode}: {command[0]}"
        )


def remove_tree(path: Path) -> None:
    """Delete a directory tree, retrying while something still holds a handle."""

    for attempt in range(UNLINK_RETRIES):
        if not path.exists():
            return
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt == UNLINK_RETRIES - 1:
                raise
            # A read-only file denies its own delete, so clear the attribute
            # across the tree before trying again.
            for child in path.rglob("*"):
                if child.is_file():
                    _clear_read_only(child)
            time.sleep(UNLINK_DELAY_SECONDS)


def _clear_read_only(path: Path) -> None:
    """Drop the read-only attribute, which alone denies a delete."""

    try:
        os.chmod(path, stat.S_IWRITE)
    except OSError:
        pass


def remove_file(path: Path) -> None:
    """Delete a file, retrying while something still holds a handle."""

    for attempt in range(UNLINK_RETRIES):
        if not path.exists():
            return
        try:
            _clear_read_only(path)
            path.unlink()
            return
        except OSError:
            if attempt == UNLINK_RETRIES - 1:
                raise
            time.sleep(UNLINK_DELAY_SECONDS)


def publish(built: Path, destination: Path) -> Path:
    """Move a freshly built artefact into place, over any previous copy.

    Windows will not let a running executable be replaced, and the commonest
    reason a previous build cannot be overwritten is that the last one is still
    open on screen. That is worth saying, because the raw error is
    `PermissionError: [WinError 5] Access is denied` against a path, which
    names neither the cause nor the fix.

    A previous copy that cannot be deleted is renamed aside instead, so a
    scanner holding a stale file for a few more seconds does not fail a build
    that has otherwise finished.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        remove_file(destination)
    except OSError:
        aside = destination.with_suffix(destination.suffix + ".old")
        try:
            remove_file(aside)
            destination.rename(aside)
            print(f"Could not delete the previous {destination.name}; renamed it to")
            print(f"  {aside}")
            print("Delete it yourself once nothing is holding it open.")
        except OSError as error:
            raise SystemExit(
                f"Could not replace {destination}.\n\n"
                f"{error}\n\n"
                "The usual cause is that the previous build is still running: "
                "close any open setup window, and any application it installed, "
                "then run this again. Explorer's preview pane and a virus "
                "scanner can also hold an executable open for a few seconds.\n\n"
                f"The new build is ready at {built} and is not lost."
            ) from error

    shutil.move(str(built), str(destination))
    return destination


def require_windows() -> None:
    if sys.platform != "win32":
        raise SystemExit("This build script targets Windows.")

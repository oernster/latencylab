"""Helpers shared by the delivery scripts.

`buildexe.py`, `buildinstaller.py` and `builddmg.py` all need the same handful
of things: the version, a subprocess runner that fails loudly, a readable
section header and a directory remover that survives a virus scanner holding a
file open. They live here so the three recipes stay recipes.

This is a build script. It is exempt from the size cap and from the coverage
gate, because what it does is only meaningful against a real toolchain.
"""

from __future__ import annotations

import shutil
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
# antivirus all do it. Retrying beats failing a ten-minute build.
UNLINK_RETRIES = 20
UNLINK_DELAY_SECONDS = 0.15


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
            time.sleep(UNLINK_DELAY_SECONDS)


def remove_file(path: Path) -> None:
    """Delete a file, retrying while something still holds a handle."""

    for attempt in range(UNLINK_RETRIES):
        if not path.exists():
            return
        try:
            path.unlink()
            return
        except OSError:
            if attempt == UNLINK_RETRIES - 1:
                raise
            time.sleep(UNLINK_DELAY_SECONDS)


def require_windows() -> None:
    if sys.platform != "win32":
        raise SystemExit("This build script targets Windows.")

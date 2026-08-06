"""Locate the setup program's own files at runtime.

Two things are surprisingly hard inside a onefile build and both are solved
here. The bundled payload is not beside the executable the user double-clicked,
it is beside the unpacked bootstrap; and `sys.executable` points at that
bootstrap rather than at the real setup program, so an installer that copies
`sys.executable` as its own uninstaller copies a temporary file that will not
exist tomorrow.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from installer.constants import (
    ASSETS_DIR_NAME,
    FALLBACK_VERSION,
    PAYLOAD_DIR_NAME,
    VERSION_FILE_NAME,
)

# Nuitka sets this to the path of the original onefile executable. Without it,
# `sys.executable` is the extracted bootstrap under %TEMP%.
ONEFILE_BINARY_ENV_VAR = "NUITKA_ONEFILE_BINARY"


def bundle_dir() -> Path:
    """The directory holding the bundled data files.

    Under a onefile build this is the unpacked bootstrap directory; running
    from source it is the repository root.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    compiled = globals().get("__compiled__")
    containing = getattr(compiled, "containing_dir", None)
    if containing:
        return Path(containing)

    return Path(__file__).resolve().parents[1]


def payload_dir() -> Path:
    """Where the staged application payload lives inside the bundle."""

    return bundle_dir() / PAYLOAD_DIR_NAME


def setup_executable() -> Path:
    """The real setup program, not the temporary onefile bootstrap.

    This is the file copied beside the installation to serve as the registered
    uninstaller, so getting it wrong registers a path that stops existing the
    moment the bootstrap is cleaned up.
    """

    onefile = os.environ.get(ONEFILE_BINARY_ENV_VAR)
    if onefile:
        return Path(onefile).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    return Path(sys.argv[0]).resolve()


def payload_asset(name: str) -> Path | None:
    """A generated icon inside the payload; None when it is absent."""

    candidate = payload_dir() / ASSETS_DIR_NAME / name
    return candidate if candidate.is_file() else None


def payload_file(name: str) -> Path | None:
    """A loose file staged beside the payload; None when it is absent."""

    candidate = payload_dir() / name
    return candidate if candidate.is_file() else None


def payload_version() -> str:
    """The version being installed, read from the staged VERSION file."""

    version_file = payload_file(VERSION_FILE_NAME)
    if version_file is None:
        return FALLBACK_VERSION
    try:
        return version_file.read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    except OSError:
        return FALLBACK_VERSION

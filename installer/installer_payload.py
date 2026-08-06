"""What the payload contains, where each part sits and how it is deployed.

The setup program carries the built application as an embedded payload. This
module knows that layout and nothing else: which directory holds what, which
candidate paths a text or an icon might be at, plus how it is extracted.

Like installer_logic it is pure. The bundle root is passed in rather than read
from `__file__`, so every function here is testable against a temporary
directory.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import installer_logic as logic


def payload_app_dir(root: Path) -> Path:
    """Return the bundled application directory inside the payload."""

    return root / logic.PAYLOAD_DIR_NAME / logic.APP_NAME


def payload_archive(root: Path) -> Path:
    """Return the zipped application bundle inside the payload."""

    return root / logic.PAYLOAD_DIR_NAME / logic.PAYLOAD_ARCHIVE_NAME


def licence_candidates(file_name: str, root: Path) -> tuple[Path, ...]:
    """Return where a bundled text file may sit, nearest copy first."""

    return (
        root / file_name,
        root / logic.PAYLOAD_DIR_NAME / file_name,
        payload_app_dir(root) / file_name,
    )


def version_candidates(root: Path) -> tuple[Path, ...]:
    """Return where the bundled VERSION file may sit, nearest copy first."""

    return (
        payload_app_dir(root) / logic.VERSION_FILE_NAME,
        root / logic.PAYLOAD_DIR_NAME / logic.VERSION_FILE_NAME,
        root / logic.VERSION_FILE_NAME,
    )


def icon_candidates(root: Path, file_name: str) -> tuple[Path, ...]:
    """Return where a bundled icon may sit, nearest copy first."""

    return (
        payload_app_dir(root) / logic.ASSETS_DIR_NAME / file_name,
        root / logic.PAYLOAD_DIR_NAME / logic.ASSETS_DIR_NAME / file_name,
        root / logic.ASSETS_DIR_NAME / file_name,
    )


def first_readable_text(candidates: tuple[Path, ...], fallback: str) -> str:
    """Return the first candidate that reads; the fallback when none do."""

    for candidate in candidates:
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return fallback


def first_version(candidates: tuple[Path, ...]) -> str:
    """Return the first non-empty version text found; an empty string otherwise.

    Empty rather than a fabricated number: a version the installer invented is
    worse than one it admits it could not find.
    """

    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return ""


def first_existing(candidates: tuple[Path, ...]) -> Path | None:
    """Return the first candidate that is a file; None when none is."""

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def deploy_files(archive: Path, target: Path) -> Path:
    """Extract the bundled application archive to `target`; return the exe.

    Any previous install at the target is removed first, so the result is a
    clean deployment rather than one version's files layered over another's.
    """

    if not archive.is_file():
        raise FileNotFoundError(f"Bundled application not found at {archive}.")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(target)
    return target / logic.EXE_NAME

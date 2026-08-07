"""Where a bundled data directory landed, whatever the app was packaged with.

A directory that sits beside the source tree in development sits beside the
executable in a Nuitka standalone build, under `Contents/Resources` in a macOS
bundle and under `/app` inside a Flatpak. Both `assets/` and `examples/` have
exactly that problem, so the search lives here once rather than being written
out per directory and drifting.

The search is expressed as an ordered list of candidates built from explicit
inputs rather than read from the environment inside the loop, which keeps it
testable without a packaged build to run against.
"""

from __future__ import annotations

import sys
from pathlib import Path

# A macOS bundle puts the executable in Contents/MacOS; the data is staged one
# level across in Contents/Resources.
MACOS_RESOURCES_DIR_NAME = "Resources"

# Flatpak stages the app under /app, so bundled directories land at a fixed root.
FLATPAK_ROOT = Path("/app")


def source_root() -> Path:
    """The repository root when running from a checkout."""

    return Path(__file__).resolve().parents[1]


def compiled_dir() -> Path | None:
    """The directory of a Nuitka standalone build; None when not compiled.

    Nuitka injects `__compiled__` into every module it builds. Reading it out of
    `globals()` keeps this importable from source, where the name is absent.
    """

    compiled = globals().get("__compiled__")
    containing = getattr(compiled, "containing_dir", None)
    return Path(containing) if containing else None


def executable_dir() -> Path | None:
    """The directory of the running executable, when the app is frozen."""

    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def bundle_dir() -> Path | None:
    """Where PyInstaller unpacked the bundled data; None when not PyInstaller.

    This is asked FIRST among the packaged layouts because it is the only one
    that is stated rather than inferred. Guessing from the executable works on
    Windows, where the data sits beside the exe, and is a coin toss inside a
    macOS .app: PyInstaller has moved collected data between `Contents/MacOS`,
    `Contents/Resources` and `Contents/Frameworks` across releases, with
    symlinks papering over some of it. `sys._MEIPASS` is PyInstaller's own
    answer to the question and does not move.
    """

    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def candidate_dirs(
    *,
    dir_name: str,
    env_value: str | None,
    executable_dir: Path | None,
    compiled_dir: Path | None,
    source_root: Path,
    bundle_dir: Path | None = None,
    flatpak_dir: Path | None = None,
) -> tuple[Path, ...]:
    """Every place `dir_name` could be, most specific first.

    The order matters: an explicit override beats a stated packaged layout,
    which beats an inferred one, which beats the source tree. A build that
    ships its own copy therefore never silently reads the developer's.
    """

    candidates: list[Path] = []

    if env_value:
        candidates.append(Path(env_value))

    # Stated rather than inferred, so it goes before the guesses.
    if bundle_dir is not None:
        candidates.append(bundle_dir / dir_name)

    for base in (compiled_dir, executable_dir):
        if base is None:
            continue
        candidates.append(base / dir_name)
        candidates.append(base.parent / MACOS_RESOURCES_DIR_NAME / dir_name)

    candidates.append(
        flatpak_dir if flatpak_dir is not None else FLATPAK_ROOT / dir_name
    )
    candidates.append(source_root / dir_name)

    # Preserve order while dropping the duplicates a compiled-and-frozen build
    # produces, so the caller sees each directory once.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return tuple(unique)


def first_existing_dir(candidates: tuple[Path, ...]) -> Path | None:
    """The first candidate that exists; None if none do."""

    for path in candidates:
        if path.is_dir():
            return path
    return None

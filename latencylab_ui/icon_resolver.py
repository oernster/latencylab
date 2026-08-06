"""Locate the generated icon assets, whatever the app was packaged with.

`assets/` sits beside the source tree in development, beside the executable in a
Nuitka standalone build, under `Contents/Resources` in a macOS bundle and at
`/app/assets` inside a Flatpak. The code that wants an icon should not know any
of that, so every caller asks here.

The search is expressed as an ordered list of candidate directories built from
explicit inputs rather than read from the environment inside the loop, which
keeps it testable without a packaged build to run against.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ASSETS_DIR_NAME = "assets"

# An escape hatch for anyone running the UI from an unusual layout. It is
# also the hook the tests use to prove the override wins.
ASSETS_DIR_ENV_VAR = "LATENCYLAB_ASSETS_DIR"

# Flatpak stages the app under /app, so the assets land at a fixed path.
FLATPAK_ASSETS_DIR = Path("/app") / ASSETS_DIR_NAME

# A macOS bundle puts the executable in Contents/MacOS; PyInstaller stages data
# one level across in Contents/Resources.
MACOS_RESOURCES_DIR_NAME = "Resources"

ICO_NAME = "latencylab.ico"
PNG_STEM = "latencylab_icon"
CANONICAL_PNG_NAME = f"{PNG_STEM}.png"

# The sizes generate_icons.py writes. Kept here so a caller asking for a size
# that was never generated gets the nearest one that was, rather than a path
# that does not exist.
AVAILABLE_PNG_SIZES = (16, 24, 32, 48, 64, 96, 128, 256, 512, 1024)

# What the About badge and the installer window ask for.
BADGE_PNG_SIZE = 256


def _source_root() -> Path:
    """The repository root when running from a checkout."""

    return Path(__file__).resolve().parents[1]


def _compiled_dir() -> Path | None:
    """The directory of a Nuitka standalone build; None when not compiled.

    Nuitka injects `__compiled__` into every module it builds. Reading it out of
    `globals()` keeps this importable from source, where the name is absent.
    """

    compiled = globals().get("__compiled__")
    containing = getattr(compiled, "containing_dir", None)
    return Path(containing) if containing else None


def _executable_dir() -> Path | None:
    """The directory of the running executable, when the app is frozen."""

    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def candidate_asset_dirs(
    *,
    env_value: str | None,
    executable_dir: Path | None,
    compiled_dir: Path | None,
    source_root: Path,
    flatpak_dir: Path = FLATPAK_ASSETS_DIR,
) -> tuple[Path, ...]:
    """Every place `assets/` could be, most specific first.

    The order matters: an explicit override beats a packaged layout; a packaged
    layout beats the source tree. A build that ships its own assets therefore
    never silently reads the developer's.
    """

    candidates: list[Path] = []

    if env_value:
        candidates.append(Path(env_value))

    for base in (compiled_dir, executable_dir):
        if base is None:
            continue
        candidates.append(base / ASSETS_DIR_NAME)
        # A macOS bundle: the executable sits in Contents/MacOS.
        candidates.append(base.parent / MACOS_RESOURCES_DIR_NAME / ASSETS_DIR_NAME)

    candidates.append(flatpak_dir)
    candidates.append(source_root / ASSETS_DIR_NAME)

    # Preserve order while dropping the duplicates a compiled-and-frozen build
    # produces, so the caller sees each directory once.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return tuple(unique)


def find_assets_dir(candidates: tuple[Path, ...] | None = None) -> Path | None:
    """The first candidate directory that exists; None if none do."""

    if candidates is None:
        candidates = candidate_asset_dirs(
            env_value=os.environ.get(ASSETS_DIR_ENV_VAR),
            executable_dir=_executable_dir(),
            compiled_dir=_compiled_dir(),
            source_root=_source_root(),
        )

    for path in candidates:
        if path.is_dir():
            return path
    return None


def nearest_available_size(size: int) -> int:
    """The generated size closest to `size`.

    Ties go to the larger of the two, because downscaling a slightly-too-big
    icon looks better than upscaling a slightly-too-small one.
    """

    return min(
        AVAILABLE_PNG_SIZES, key=lambda available: (abs(available - size), -available)
    )


def get_app_icon_path(assets_dir: Path | None = None) -> Path | None:
    """The window and shortcut icon: the multi-size .ico, else the 256 PNG.

    Windows wants the `.ico` so the taskbar and Explorer pick their own frame.
    Every other platform is happy with the PNG, which is also the fallback if
    generate_icons.py has not been run.
    """

    if assets_dir is None:
        assets_dir = find_assets_dir()
    if assets_dir is None:
        return None

    for name in (ICO_NAME, CANONICAL_PNG_NAME):
        candidate = assets_dir / name
        if candidate.is_file():
            return candidate
    return None


def get_app_icon_png_path(
    size: int = BADGE_PNG_SIZE, assets_dir: Path | None = None
) -> Path | None:
    """The generated PNG nearest to `size`; None when the set is absent."""

    if assets_dir is None:
        assets_dir = find_assets_dir()
    if assets_dir is None:
        return None

    candidate = assets_dir / f"{PNG_STEM}_{nearest_available_size(size)}.png"
    return candidate if candidate.is_file() else None

"""Single source of truth for the LatencyLab version.

The only real version string lives in the ``VERSION`` file at the repository
root. Everything else derives from it:

- this module reads it at runtime (the About dialog and any bug report),
- ``pyproject.toml`` declares its version dynamic and reads the same file,
- ``stamp_version.py`` writes it into the GitHub Pages site under ``docs/``.

No other file is allowed to carry a literal version.
"""

from __future__ import annotations

from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"

# What an installed distribution sees: there the built metadata carries the
# number and no source tree is present to read.
FALLBACK_VERSION = "0.0.0-dev"


def read_version(version_file: Path = VERSION_FILE) -> str:
    """Return the version recorded in ``version_file``.

    Falls back to :data:`FALLBACK_VERSION` when the file is missing, empty or
    unreadable, so importing the package never fails on a packaging accident.
    """

    try:
        return version_file.read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    except OSError:
        return FALLBACK_VERSION


__version__: str = read_version()

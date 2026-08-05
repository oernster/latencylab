#!/usr/bin/env python3
"""Stamp the single-source version into the GitHub Pages site.

The repository keeps exactly one real version string: the ``VERSION`` file at
the project root. Python code reads it at runtime through
``latencylab.version`` and the packaging metadata reads it as a dynamic field.
Static files cannot read ``VERSION`` at render time, so they instead carry a
delimited token::

    <!--VERSION-->0.0.0<!--/VERSION-->

This script rewrites whatever sits between every such token's delimiters,
across the site under ``docs/`` and nowhere else. No documentation outside the
site carries version data, so the site is the whole stamped surface. It is
idempotent: stamping an already-current file changes nothing.

Usage (from the project root)::

    python stamp_version.py

Run it after every version bump so the site never drifts from ``VERSION``.
"""

from __future__ import annotations

import re
from pathlib import Path

from latencylab.version import read_version

PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT / "docs"

# Delimiters that bracket a stamped version in a static file. The text between
# them is owned by this script and is overwritten from VERSION on every run.
VERSION_TOKEN_OPEN = "<!--VERSION-->"
VERSION_TOKEN_CLOSE = "<!--/VERSION-->"
VERSION_TOKEN_PATTERN = re.compile(
    re.escape(VERSION_TOKEN_OPEN) + ".*?" + re.escape(VERSION_TOKEN_CLOSE),
    re.DOTALL,
)


def target_files(docs_dir: Path = DOCS_DIR) -> list[Path]:
    """Return the site files that may carry a version token, deduplicated."""

    candidates: set[Path] = set(docs_dir.rglob("*.html"))
    candidates.update(docs_dir.rglob("*.md"))
    return sorted(candidates)


def stamp_file(path: Path, version: str) -> bool:
    """Rewrite version tokens in one file. Return True if the file changed."""

    original = path.read_bytes().decode("utf-8")
    stamped = VERSION_TOKEN_PATTERN.sub(
        lambda _match: f"{VERSION_TOKEN_OPEN}{version}{VERSION_TOKEN_CLOSE}",
        original,
    )
    if stamped == original:
        return False
    path.write_bytes(stamped.encode("utf-8"))
    return True


def main(docs_dir: Path = DOCS_DIR, version: str | None = None) -> int:
    """Stamp every site file and report what was touched."""

    resolved = version or read_version()
    changed = [path for path in target_files(docs_dir) if stamp_file(path, resolved)]
    print(f"[stamp_version] VERSION = {resolved}")
    if not changed:
        print("[stamp_version] No files needed stamping.")
        return 0
    for path in changed:
        print(f"[stamp_version] Stamped {path.relative_to(docs_dir.parent)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

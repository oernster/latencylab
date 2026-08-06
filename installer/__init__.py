"""The bespoke LatencyLab setup program.

The package exposes its entry point and nothing else; every other module here
is an implementation detail of the window it builds.
"""

from __future__ import annotations

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Run the setup program. Imported lazily so `installer.constants` and the
    other Qt-free modules can be read without PySide6 present."""

    from installer.app import main as _main

    return _main(argv)

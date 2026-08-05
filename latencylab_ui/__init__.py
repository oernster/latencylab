"""PySide6 desktop UI client for the LatencyLab simulation engine.

This package is intentionally a *client* of the headless core:

- Core stays UI-agnostic (no Qt imports under `latencylab/`).
- UI runs simulations in a background thread and renders results.

Run from source:

    python -m latencylab_ui
"""

from __future__ import annotations

# The UI has no version of its own: it ships from the same tree as the core and
# reports the core's number, which is read from the root VERSION file.
from latencylab.version import __version__

__all__ = ["__version__"]

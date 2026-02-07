"""PySide6 desktop UI client for the LatencyLab simulation engine.

This package is intentionally a *client* of the headless core:

- Core stays UI-agnostic (no Qt imports under `latencylab/`).
- UI runs simulations in a background thread and renders results.

Run from source:

    python -m latencylab_ui
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"


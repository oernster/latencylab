from __future__ import annotations

"""Repo-root convenience shim for launching the LatencyLab UI.

This keeps the most common local workflow short:

    python runner.py

It delegates to the canonical UI entry point:

    python -m latencylab_ui
"""

import sys


def main() -> int:
    """Launch the LatencyLab UI.

    Arguments are forwarded exactly as in `python -m latencylab_ui`.
    """

    # `latencylab_ui.__main__.main()` is responsible for printing the friendly
    # PySide6-missing message if the GUI dependency is not installed.
    from latencylab_ui.__main__ import main as ui_main

    # Make argv look like the canonical entry point (`python -m latencylab_ui`),
    # while preserving any user-provided arguments.
    sys.argv = ["latencylab_ui", *sys.argv[1:]]

    return ui_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

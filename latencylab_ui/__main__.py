from __future__ import annotations

import sys


def main() -> int:
    """Entry point for `python -m latencylab_ui`.

    This is the source-run path. The packaged build starts at `runner.py`.
    """

    try:
        from latencylab_ui.app import run_app
    except ImportError as e:  # pragma: no cover
        # Common first-run experience: PySide6 not installed.
        sys.stderr.write(
            "LatencyLab UI requires PySide6. Install it (e.g. `pip install PySide6`)\n"
        )
        sys.stderr.write(f"ImportError: {e}\n")
        return 2

    return run_app(argv=sys.argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

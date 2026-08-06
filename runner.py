from __future__ import annotations

"""Repo-root convenience shim for launching the LatencyLab UI.

This keeps the most common local workflow short:

    python runner.py

It delegates to the canonical UI entry point:

    python -m latencylab_ui
"""


def main() -> int:
    """Launch the LatencyLab UI.

    Arguments are forwarded exactly as in `python -m latencylab_ui`.

    `sys.argv` is left exactly as the operating system supplied it. It used to
    be rewritten here so `argv[0]` read as the module name, which was cosmetic
    even from source (`python -m` puts the path of `__main__.py` there, not the
    module name) and fatal once frozen: Nuitka's PySide6 plugin reads `argv[0]`
    when a Windows icon is compiled in, pulls the icons out of that file and
    asserts it found at least one. Pointed at a bare module name it finds no
    file, and the frozen application dies before its first window, silently,
    because the release build has no console to print the traceback to.
    """

    # `latencylab_ui.__main__.main()` is responsible for printing the friendly
    # PySide6-missing message if the GUI dependency is not installed.
    from latencylab_ui.__main__ import main as ui_main

    return ui_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

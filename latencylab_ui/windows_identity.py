from __future__ import annotations

"""Telling Windows which application this process is.

Windows groups taskbar buttons, and matches a running window to the shortcut
that started it, by Application User Model ID. The installer already writes one
on the shortcut it registers; the application never claimed the same one, so
Windows had no way to know they were the same program. The visible result was
that the pinned icon and the running window were two different taskbar items:
clicking the pinned one did nothing to the window that was already open, and
launching from the jump list produced a second copy beside the first.

The value is the installer's, not a second one invented here. Two IDs would
reproduce the bug in a form that is harder to see.
"""

import sys

# Must match `installer.installer_logic.APP_AUMID`. Duplicated deliberately
# rather than imported: the installer is a separate program that is not shipped
# inside the application, so importing across that boundary would put a build
# dependency on it. The pairing is asserted by a test instead.
APP_AUMID = "uk.codecrafter.latencylab"

WINDOWS_PLATFORM = "win32"


def claim_app_identity(*, platform: str | None = None) -> bool:
    """Claim the AUMID on Windows; a no-op everywhere else.

    Returns whether the identity was claimed, which is what the tests read.
    Failure is not raised: an application that cannot tell the shell its name
    still runs perfectly well, and nothing the user is doing should stop for it.
    """

    if (platform or sys.platform) != WINDOWS_PLATFORM:
        return False

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_AUMID)
    except (AttributeError, OSError):  # pragma: no cover - non-Windows shells
        return False
    return True

"""Identity, paths and sizes for the LatencyLab setup program.

Every literal the installer needs lives here, so the window, the deployer and
the registry writer cannot disagree about what is being installed or where.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LatencyLab"
APP_PUBLISHER = "Oliver Ernster"
APP_TAGLINE = "Design-time latency exploration for event-driven systems"

EXE_NAME = f"{APP_NAME}.exe"
SETUP_EXE_NAME = f"{APP_NAME}Setup.exe"

# The payload directory bundled inside the setup executable.
PAYLOAD_DIR_NAME = "payload"
PAYLOAD_ZIP_NAME = f"{APP_NAME}.zip"

# Per-user and no administrator: everything lands under the user's own profile,
# which is what lets this install without an elevation prompt.
INSTALL_PARENT_ENV_VAR = "LOCALAPPDATA"
INSTALL_SUBDIR = Path("Programs") / APP_NAME

# The copy of this setup program kept beside the install so Windows has
# something to run when the user clicks Uninstall.
UNINSTALL_SUBDIR = "_uninstall"
UNINSTALL_FLAG = "--uninstall"

# HKCU rather than HKLM, for the same no-elevation reason.
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"

START_MENU_SUBDIR = Path("Microsoft") / "Windows" / "Start Menu" / "Programs"

# Assets, resolved inside the payload rather than from the source tree.
ICON_ICO_NAME = "latencylab.ico"
BADGE_PNG_NAME = "latencylab_icon_256.png"
ASSETS_DIR_NAME = "assets"

LICENCE_MODEL_NAME = "LICENSE"
LICENCE_UI_NAME = "LGPL3.txt"
LICENCE_INSTALLER_NAME = "INSTALLER_LICENSE"

VERSION_FILE_NAME = "VERSION"
FALLBACK_VERSION = "0.0.0-dev"

# Window geometry. Fixed width, because a resizable wizard buys nothing and a
# reflowing licence pane is worse than a scrolling one.
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 520
CONTENT_MARGIN = 18
CONTENT_SPACING = 12
BADGE_PX = 64

# Progress runs 0 to 100; the deployer reports real percentages.
PROGRESS_MIN = 0
PROGRESS_MAX = 100


def install_dir() -> Path:
    """Where the application is installed for the current user."""

    parent = os.environ.get(INSTALL_PARENT_ENV_VAR)
    base = Path(parent) if parent else Path.home() / "AppData" / "Local"
    return base / INSTALL_SUBDIR

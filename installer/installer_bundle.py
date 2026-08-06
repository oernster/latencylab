"""Reads of the installer's own payload: version, licences and icon.

This is the one place the installer asks where it is. Under the onefile build
that answer is the bootstrap's unpacked directory, which is where Nuitka places
the embedded payload, so every other module takes the bundle root from here
rather than reading `__file__` for itself. Nothing looks at `sys.executable`
(which under onefile is the temporary bootstrap, not the payload's home).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

import installer_logic as logic
import installer_payload as payload


def bundle_root() -> Path:
    """Return the directory holding the unpacked payload and licences."""

    return Path(__file__).resolve().parent


def licence_text(file_name: str) -> str:
    """Return a bundled licence text by file name; a fallback when absent."""

    return payload.first_readable_text(
        payload.licence_candidates(file_name, bundle_root()),
        logic.LICENSE_FALLBACK,
    )


def installer_licence_text() -> str:
    """Return the installer licence notice; a fallback when absent."""

    return payload.first_readable_text(
        payload.licence_candidates(logic.INSTALLER_LICENSE_FILE_NAME, bundle_root()),
        logic.INSTALLER_LICENSE_FALLBACK,
    )


def app_version() -> str:
    """Return the bundled application version; an empty string when absent."""

    return payload.first_version(payload.version_candidates(bundle_root()))


def _icon_path(file_name: str) -> Path | None:
    return payload.first_existing(payload.icon_candidates(bundle_root(), file_name))


def app_icon() -> QIcon:
    """Return the bundled application icon; an empty icon when absent."""

    path = _icon_path(logic.SHORTCUT_ICON_FILE_NAME) or _icon_path(logic.ICON_FILE_NAME)
    return QIcon(str(path)) if path is not None else QIcon()


def shortcut_icon() -> Path | None:
    """Return the multi-size .ico shortcuts and the Apps list should use."""

    return _icon_path(logic.SHORTCUT_ICON_FILE_NAME)

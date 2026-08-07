"""Where a file dialog should start.

An empty start path means "the working directory", which is the wrong answer
for an installed application: the working directory of a shortcut launch is the
install location, so Open and Export both opened inside the installed program
rather than anywhere the user keeps files.

Downloads is the right default because it is where a model arrives from a
colleague or a browser, and where an export is expected to land. The location is
asked of the platform rather than assembled from the home directory, so a
redirected or localised Downloads folder is honoured.
"""

from __future__ import annotations

from PySide6.QtCore import QStandardPaths

# Most specific first. Home is the fallback for a system with no Downloads
# location at all; the empty string after it means "let Qt decide", which is the
# old behaviour and is only reached when the platform answers nothing.
_PREFERRED_LOCATIONS = (
    QStandardPaths.StandardLocation.DownloadLocation,
    QStandardPaths.StandardLocation.HomeLocation,
)

# The name an export is offered under, so the dialog opens with something
# sensible typed in rather than an empty field.
EXPORT_FILE_NAME = "latencylab-runs.zip"


def default_dialog_dir() -> str:
    """The directory a file dialog should open in."""

    for location in _PREFERRED_LOCATIONS:
        path = QStandardPaths.writableLocation(location)
        if path:
            return path
    return ""


def default_export_path() -> str:
    """The full path an export dialog should be pre-filled with."""

    directory = default_dialog_dir()
    if not directory:
        return EXPORT_FILE_NAME
    return f"{directory}/{EXPORT_FILE_NAME}"

"""Persistence for the update check's one setting: the skipped version.

LatencyLab has had no per-user settings until now, so this is the settings
file as well as the skip store. Deliberately best-effort: losing the note
costs one extra prompt after the next release, so a damaged or unreadable
file reads as nothing-skipped and is rewritten whole on the next save, with
unrelated keys a future writer may add preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

_APP_DIR = ".latencylab"
_FILENAME = "settings.json"
_JSON_INDENT = 2
_SKIPPED_UPDATE_KEY = "skipped_update_version"


def default_settings_path() -> Path:
    """The per-user location the settings are saved to and restored from."""

    return Path.home() / _APP_DIR / _FILENAME


class UpdateSettingsStore:
    """Persists the update check's settings in a small JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else default_settings_path()

    def load_skipped_version(self) -> str | None:
        """The exact release tag the user chose to skip, else None."""

        value = self._read_all().get(_SKIPPED_UPDATE_KEY)
        return value if isinstance(value, str) and value else None

    def save_skipped_version(self, version: str) -> None:
        data = self._read_all()
        data[_SKIPPED_UPDATE_KEY] = version
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, indent=_JSON_INDENT), encoding="utf-8"
            )
        except OSError:
            # Best-effort: the worst case is one extra prompt next release.
            pass

    def _read_all(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

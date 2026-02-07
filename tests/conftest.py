from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _qt_offscreen() -> None:
    """Ensure Qt can initialize in CI/headless environments."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _add_repo_root_to_syspath() -> None:
    """Make local packages importable when running tests from `tests/`.

    Some Windows/PyTest invocations end up with `tests/` as the import root.
    Ensure the repo root is on `sys.path` so `import latencylab_ui` works.
    """

    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


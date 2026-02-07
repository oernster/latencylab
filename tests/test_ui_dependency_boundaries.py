from __future__ import annotations

from pathlib import Path


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def test_no_qt_imports_in_core_latencylab_package() -> None:
    """Hard boundary: core must never import Qt.

    This test intentionally scans source text so it passes even when PySide6 is
    not installed.
    """

    core_root = Path(__file__).resolve().parents[1] / "latencylab"
    offenders: list[str] = []
    for p in _iter_py_files(core_root):
        txt = p.read_text(encoding="utf-8")
        if "PySide6" in txt or "PyQt" in txt or "qtpy" in txt:
            offenders.append(str(p))

    assert not offenders, f"Qt imports found under latencylab/: {offenders}"


def test_core_does_not_reference_latencylab_ui_package() -> None:
    core_root = Path(__file__).resolve().parents[1] / "latencylab"
    offenders: list[str] = []
    for p in _iter_py_files(core_root):
        txt = p.read_text(encoding="utf-8")
        if "latencylab_ui" in txt:
            offenders.append(str(p))

    assert not offenders, f"core references latencylab_ui: {offenders}"


from __future__ import annotations

from pathlib import Path


def _iter_repo_py_files(root: Path) -> list[Path]:
    files: list[Path] = []

    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            ".mypy_cache",
            ".pytest_cache",
        } & parts:
            continue
        files.append(p)

    return sorted(files)


def test_all_python_files_are_at_most_400_lines() -> None:
    """Maintainability guardrail.

    LatencyLab intentionally keeps modules small and focused.
    """

    root = Path(__file__).resolve().parents[1]
    max_lines = 400

    offenders: list[tuple[str, int]] = []
    for p in _iter_repo_py_files(root):
        # Count physical lines (includes blanks/comments) for a simple, robust gate.
        line_count = len(p.read_text(encoding="utf-8").splitlines())
        if line_count > max_lines:
            offenders.append((str(p.relative_to(root)).replace("\\", "/"), line_count))

    assert not offenders, (
        "Python files must be <= 400 lines. Offenders:\n"
        + "\n".join(f"- {path}: {n}" for path, n in offenders)
    )


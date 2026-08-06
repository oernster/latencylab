from __future__ import annotations

from pathlib import Path

# The size a file may reach and no further. Test files count exactly as source
# files do: a 400-line test is as hard to navigate as a 400-line module, then
# harder still to be sure is complete.
LINE_CAP = 400

# How far below the cap a file is already too close to it.
DANGER_BAND_PERCENT = 5

# The last comfortable size. Derived from the cap rather than written as a
# second literal, so changing the cap moves the band with it and the two can
# never drift apart.
DANGER_BAND_FLOOR = LINE_CAP - (LINE_CAP * DANGER_BAND_PERCENT // 100)

# Delivery scripts are exempt: these alone. Each is a linear recipe read top
# to bottom: a sequence of toolchain flags and staged files where splitting the
# sequence across modules costs more than it buys. Nothing else is exempt. The
# installer's own user interface is application code and stays in scope, which
# is the distinction that matters: the recipe that invokes Nuitka is a script,
# the window it produces is a program.
BUILD_SCRIPTS = frozenset(
    {
        "generate_icons.py",
        "generate_scripts.py",
        "stamp_version.py",
        "buildexe.py",
        "buildinstaller.py",
        "builddmg.py",
        "build_utils.py",
        "dmg_icon.py",
    }
)


# Directories that hold no source. The build outputs matter as much as the
# caches here: a staged payload contains a copy of the whole application plus
# whatever scaffolding the toolchain left behind; measuring build output
# against a maintainability rule says nothing about maintainability.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "payload",
        "dist",
        "dist-installer",
        "dist-installer.build",
        "build",
        ".flatpak-build",
        ".flatpak-builder",
    }
)


def _iter_repo_py_files(root: Path) -> list[Path]:
    files: list[Path] = []

    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if EXCLUDED_DIRS & parts:
            continue
        # Exempt only at the repository root: a module that happens to share a
        # name with a build script deeper in the tree is still application code.
        if p.parent == root and p.name in BUILD_SCRIPTS:
            continue
        files.append(p)

    return sorted(files)


def _line_counts(root: Path) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    for p in _iter_repo_py_files(root):
        # Physical lines (blanks and comments included) for a simple, robust gate.
        n = len(p.read_text(encoding="utf-8").splitlines())
        counts.append((str(p.relative_to(root)).replace("\\", "/"), n))
    return counts


def test_all_python_files_are_at_most_400_lines() -> None:
    """Maintainability guardrail.

    LatencyLab intentionally keeps modules small and focused.
    """

    root = Path(__file__).resolve().parents[1]

    offenders = [(path, n) for path, n in _line_counts(root) if n > LINE_CAP]

    assert (
        not offenders
    ), f"Python files must be <= {LINE_CAP} lines. Offenders:\n" + "\n".join(
        f"- {path}: {n}" for path, n in offenders
    )


def test_the_build_script_exemption_has_no_stale_entries() -> None:
    """An exemption for a file that no longer exists is a hole, not a rule.

    A deleted or renamed build script would otherwise leave a name behind that
    silently exempts whatever takes it next.
    """

    root = Path(__file__).resolve().parents[1]

    missing = sorted(name for name in BUILD_SCRIPTS if not (root / name).is_file())

    assert not missing, (
        "These names are exempt from the size cap but no longer exist at the "
        "repository root. Remove them from BUILD_SCRIPTS:\n"
        + "\n".join(f"- {name}" for name in missing)
    )


def test_no_python_file_sits_just_below_the_cap() -> None:
    """The half of the rule that is easy to argue away, yet worth keeping.

    Shaving a file to 399 buys nothing. The next edit breaks it, the same file
    is decomposed again, the work is paid for twice and in between a reader
    still has a 399-line file. A file that has to be split is split properly,
    to a size with room in it.

    The cap itself stays legal: 400 is the stated target rather than a number to
    creep up on. What this refuses is the approach to it.
    """

    root = Path(__file__).resolve().parents[1]

    offenders = [
        (path, n) for path, n in _line_counts(root) if DANGER_BAND_FLOOR < n < LINE_CAP
    ]

    assert not offenders, (
        f"Python files must not sit between {DANGER_BAND_FLOOR + 1} and "
        f"{LINE_CAP - 1} lines: decompose to a size with room in it, not to "
        f"{LINE_CAP - 1}. Offenders:\n"
        + "\n".join(f"- {path}: {n}" for path, n in offenders)
    )

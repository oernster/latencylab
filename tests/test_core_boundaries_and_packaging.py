from __future__ import annotations

"""Two structural rules about the distributable core.

The first keeps the model layer pure: `model`, `types` and `validate` describe
and check a model and must not read the filesystem. `io` sits beside them at the
same level, so nothing about the layout stops one of them reaching for it, and
the moment one does the core stops being testable without a temporary
directory.

The second pins what the wheel contains. The packaging rule once globbed the
LGPL front end into a GPL wheel for several releases while every document said
otherwise. The glob is fixed; this is the test whose absence let it happen.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The modules that describe and validate a model, as opposed to loading one.
PURE_CORE_MODULES = ("model", "types", "validate")

# What those modules must not reach for. `io` is the package's own file-loading
# module; the rest are the standard ways to reach a disk or a network.
FORBIDDEN_IMPORTS = (
    "latencylab.io",
    "io",
    "os",
    "os.path",
    "pathlib",
    "shutil",
    "socket",
    "urllib",
    "urllib.request",
)


def _imported_names(path: Path) -> set[str]:
    """Every module named by an import in `path`, absolute or relative."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # `from . import io` inside the package.
                for alias in node.names:
                    names.add(alias.name)
            elif node.module:
                names.add(node.module)
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
    return names


def test_pure_core_modules_do_not_touch_the_filesystem() -> None:
    offenders: list[str] = []
    for module in PURE_CORE_MODULES:
        path = REPO_ROOT / "latencylab" / f"{module}.py"
        assert path.is_file(), f"{path} is missing, so this test checks nothing"
        for imported in sorted(_imported_names(path)):
            if imported in FORBIDDEN_IMPORTS:
                offenders.append(f"- latencylab/{module}.py imports {imported}")

    assert not offenders, (
        "The model layer must stay free of I/O. Loading belongs in "
        "latencylab/io.py.\n" + "\n".join(offenders)
    )


def test_io_is_still_the_module_that_does_the_loading() -> None:
    """Guards the rule above from passing because nothing loads anything.

    If `io.py` ever stops reading files, the forbidden list has been satisfied
    by moving the problem rather than by keeping the boundary.
    """
    io_imports = _imported_names(REPO_ROOT / "latencylab" / "io.py")
    assert io_imports & {"json", "pathlib", "os"}, (
        "latencylab/io.py no longer imports anything that reads a file, so the "
        "purity rule above may be checking an empty boundary"
    )


def test_the_wheel_contains_only_the_headless_core() -> None:
    """What setuptools would ship, checked rather than described.

    `latencylab*` also globs `latencylab_ui`, so the Qt front end is excluded by
    name in pyproject.toml. That exclusion is the difference between a GPL wheel
    and one carrying LGPL code, so it is worth a test rather than a comment.
    """
    from setuptools import find_packages

    discovered = sorted(
        find_packages(
            where=str(REPO_ROOT),
            include=["latencylab*"],
            exclude=["plans*", "examples*", "tests*", "latencylab_ui*"],
        )
    )

    assert discovered == ["latencylab"], (
        "The distributable must be the headless core alone. Discovered: "
        f"{discovered}"
    )

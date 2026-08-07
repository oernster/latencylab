"""The example models the application can open from its own menu.

The set is DISCOVERED from `examples/` rather than listed here, which is the
same decision the validation test already makes: adding a model to that
directory opts it into both the test and the menu, and there is no second place
to update. A hand-written list would drift the moment one was renamed.

Labels are derived from the file name for the same reason. A per-file caption
would read better, but it would be a mapping keyed on file names, which is the
drift this module exists to avoid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from latencylab_ui.packaged_dir import (
    FLATPAK_ROOT,
    bundle_dir,
    candidate_dirs,
    compiled_dir,
    executable_dir,
    first_existing_dir,
    source_root,
)

EXAMPLES_DIR_NAME = "examples"

# An escape hatch for anyone running the UI from an unusual layout, and the
# hook the tests use to prove the override wins.
EXAMPLES_DIR_ENV_VAR = "LATENCYLAB_EXAMPLES_DIR"

FLATPAK_EXAMPLES_DIR = FLATPAK_ROOT / EXAMPLES_DIR_NAME

MODEL_SUFFIX = ".json"

WORD_SEPARATOR = "_"


@dataclass(frozen=True, slots=True)
class ExampleModel:
    """One shipped model, and what the menu should call it."""

    label: str
    path: Path


def candidate_example_dirs(
    *,
    env_value: str | None,
    executable_dir: Path | None,
    compiled_dir: Path | None,
    source_root: Path,
    bundle_dir: Path | None = None,
    flatpak_dir: Path = FLATPAK_EXAMPLES_DIR,
) -> tuple[Path, ...]:
    """Every place `examples/` could be, most specific first."""

    return candidate_dirs(
        dir_name=EXAMPLES_DIR_NAME,
        env_value=env_value,
        executable_dir=executable_dir,
        compiled_dir=compiled_dir,
        source_root=source_root,
        bundle_dir=bundle_dir,
        flatpak_dir=flatpak_dir,
    )


def find_examples_dir(candidates: tuple[Path, ...] | None = None) -> Path | None:
    """The first candidate directory that exists; None if none do."""

    if candidates is None:
        candidates = candidate_example_dirs(
            env_value=os.environ.get(EXAMPLES_DIR_ENV_VAR),
            executable_dir=executable_dir(),
            compiled_dir=compiled_dir(),
            source_root=source_root(),
            bundle_dir=bundle_dir(),
        )

    return first_existing_dir(candidates)


def label_for(path: Path) -> str:
    """A menu label derived from the file name.

    `cold_start.json` would become "Cold start": sentence case, not title case,
    because these are descriptions rather than names.
    """

    words = path.stem.replace(WORD_SEPARATOR, " ").strip()
    if not words:
        return path.name
    return words[0].upper() + words[1:]


def list_examples(examples_dir: Path | None = None) -> tuple[ExampleModel, ...]:
    """Every shipped model, in a stable order; empty when none are bundled.

    Sorted by the file name rather than the label so the order cannot change
    with the labelling rule, and so two files that happen to render the same
    label still have a defined order.
    """

    if examples_dir is None:
        examples_dir = find_examples_dir()
    if examples_dir is None:
        return ()

    paths = sorted(
        (p for p in examples_dir.iterdir() if p.is_file() and p.suffix == MODEL_SUFFIX),
        key=lambda p: p.name,
    )
    return tuple(ExampleModel(label=label_for(p), path=p) for p in paths)

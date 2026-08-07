from __future__ import annotations

from pathlib import Path

import pytest

from latencylab_ui import example_models


def _write(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text("{}", encoding="utf-8")
    return path


def test_candidates_put_the_override_first_and_the_source_tree_last() -> None:
    candidates = example_models.candidate_example_dirs(
        env_value=r"C:\override",
        executable_dir=Path(r"C:\frozen"),
        compiled_dir=Path(r"C:\compiled"),
        source_root=Path(r"C:\src"),
    )

    assert candidates[0] == Path(r"C:\override")
    assert candidates[-1] == Path(r"C:\src") / "examples"


def test_candidates_include_the_flatpak_and_macos_layouts() -> None:
    candidates = example_models.candidate_example_dirs(
        env_value=None,
        executable_dir=Path("/App.app/Contents/MacOS"),
        compiled_dir=None,
        source_root=Path("/src"),
    )

    assert Path("/App.app/Contents/Resources/examples") in candidates
    assert example_models.FLATPAK_EXAMPLES_DIR in candidates


def test_the_shipped_examples_are_found_from_a_checkout() -> None:
    found = example_models.find_examples_dir()

    assert found is not None
    assert (found / "checkout.json").is_file()


def test_find_returns_none_when_no_candidate_exists(tmp_path: Path) -> None:
    assert example_models.find_examples_dir((tmp_path / "absent",)) is None


def test_the_environment_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(example_models.EXAMPLES_DIR_ENV_VAR, str(tmp_path))

    assert example_models.find_examples_dir() == tmp_path


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("checkout", "Checkout"),
        ("cold_start_under_load", "Cold start under load"),
        ("UPPER_case", "UPPER case"),
    ],
)
def test_labels_are_sentence_case_with_underscores_opened_up(
    stem: str, expected: str
) -> None:
    assert example_models.label_for(Path(f"{stem}.json")) == expected


def test_a_file_with_nothing_but_separators_falls_back_to_its_own_name() -> None:
    # `_.json` sentence-cases to a blank label, which would put an unreadable
    # entry on the menu, so the file name is used instead.
    assert example_models.label_for(Path("_.json")) == "_.json"


def test_listing_is_sorted_by_file_name_and_skips_non_models(tmp_path: Path) -> None:
    _write(tmp_path, "beta.json")
    _write(tmp_path, "alpha.json")
    _write(tmp_path, "notes.txt")
    (tmp_path / "nested").mkdir()

    listed = example_models.list_examples(tmp_path)

    assert [e.label for e in listed] == ["Alpha", "Beta"]
    assert [e.path.name for e in listed] == ["alpha.json", "beta.json"]


def test_listing_is_empty_when_no_examples_are_bundled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(example_models, "find_examples_dir", lambda: None)

    assert example_models.list_examples() == ()


def test_listing_defaults_to_the_discovered_directory() -> None:
    listed = example_models.list_examples()

    assert any(e.path.name == "checkout.json" for e in listed)

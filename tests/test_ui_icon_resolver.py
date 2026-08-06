from __future__ import annotations

from pathlib import Path

import pytest

from latencylab_ui import icon_resolver


class _FakeCompiled:
    """Stands in for the `__compiled__` object Nuitka injects into a build."""

    def __init__(self, containing_dir: str) -> None:
        self.containing_dir = containing_dir


def test_source_root_is_the_repository_root() -> None:
    root = icon_resolver._source_root()
    assert (root / "latencylab_ui" / "icon_resolver.py").is_file()


def test_compiled_dir_is_none_when_running_from_source() -> None:
    assert icon_resolver._compiled_dir() is None


def test_compiled_dir_reads_the_nuitka_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        icon_resolver.__dict__, "__compiled__", _FakeCompiled(r"C:\app")
    )
    assert icon_resolver._compiled_dir() == Path(r"C:\app")


def test_executable_dir_is_none_unless_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    assert icon_resolver._executable_dir() is None


def test_executable_dir_is_the_exe_directory_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "LatencyLab.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(exe))
    assert icon_resolver._executable_dir() == tmp_path.resolve()


def test_candidates_put_the_override_first_and_the_source_tree_last() -> None:
    candidates = icon_resolver.candidate_asset_dirs(
        env_value=r"C:\override",
        executable_dir=Path(r"C:\frozen"),
        compiled_dir=Path(r"C:\compiled"),
        source_root=Path(r"C:\src"),
        flatpak_dir=Path("/app/assets"),
    )

    assert candidates[0] == Path(r"C:\override")
    assert candidates[-1] == Path(r"C:\src") / "assets"
    # A packaged layout is consulted before the source tree, so a build never
    # silently reads the developer's assets.
    assert candidates.index(Path(r"C:\compiled") / "assets") < candidates.index(
        Path(r"C:\src") / "assets"
    )


def test_candidates_include_the_macos_resources_layout() -> None:
    candidates = icon_resolver.candidate_asset_dirs(
        env_value=None,
        executable_dir=Path("/App.app/Contents/MacOS"),
        compiled_dir=None,
        source_root=Path("/src"),
    )

    assert Path("/App.app/Contents/Resources/assets") in candidates


def test_candidates_omit_an_absent_override_and_absent_packaging() -> None:
    candidates = icon_resolver.candidate_asset_dirs(
        env_value=None,
        executable_dir=None,
        compiled_dir=None,
        source_root=Path("/src"),
        flatpak_dir=Path("/app/assets"),
    )

    assert candidates == (Path("/app/assets"), Path("/src") / "assets")


def test_candidates_are_deduplicated_when_compiled_and_frozen_agree() -> None:
    same = Path(r"C:\bundle")
    candidates = icon_resolver.candidate_asset_dirs(
        env_value=None,
        executable_dir=same,
        compiled_dir=same,
        source_root=Path(r"C:\src"),
    )

    assert len(candidates) == len(set(candidates))


def test_find_assets_dir_returns_the_first_existing_candidate(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    present = tmp_path / "present"
    present.mkdir()

    assert icon_resolver.find_assets_dir((missing, present)) == present


def test_find_assets_dir_returns_none_when_nothing_exists(tmp_path: Path) -> None:
    assert icon_resolver.find_assets_dir((tmp_path / "nope",)) is None


def test_find_assets_dir_honours_the_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "elsewhere"
    override.mkdir()
    monkeypatch.setenv(icon_resolver.ASSETS_DIR_ENV_VAR, str(override))

    assert icon_resolver.find_assets_dir() == override


@pytest.mark.parametrize(
    ("asked", "expected"),
    [
        (256, 256),
        (100, 96),
        (2048, 1024),
        (1, 16),
        (20, 24),
    ],
)
def test_nearest_available_size(asked: int, expected: int) -> None:
    assert icon_resolver.nearest_available_size(asked) == expected


def test_nearest_available_size_breaks_a_tie_upwards() -> None:
    # 20 is equidistant from 16 and 24; the larger wins because downscaling
    # looks better than upscaling.
    assert icon_resolver.nearest_available_size(20) == 24


def test_app_icon_prefers_the_multi_size_ico(tmp_path: Path) -> None:
    (tmp_path / icon_resolver.ICO_NAME).write_bytes(b"")
    (tmp_path / icon_resolver.CANONICAL_PNG_NAME).write_bytes(b"")

    assert icon_resolver.get_app_icon_path(tmp_path) == (
        tmp_path / icon_resolver.ICO_NAME
    )


def test_app_icon_falls_back_to_the_canonical_png(tmp_path: Path) -> None:
    (tmp_path / icon_resolver.CANONICAL_PNG_NAME).write_bytes(b"")

    assert icon_resolver.get_app_icon_path(tmp_path) == (
        tmp_path / icon_resolver.CANONICAL_PNG_NAME
    )


def test_app_icon_is_none_when_the_directory_holds_neither(tmp_path: Path) -> None:
    assert icon_resolver.get_app_icon_path(tmp_path) is None


def test_app_icon_is_none_when_no_assets_directory_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(icon_resolver, "find_assets_dir", lambda: None)
    assert icon_resolver.get_app_icon_path() is None
    assert icon_resolver.get_app_icon_png_path() is None


def test_app_icon_png_resolves_the_nearest_generated_size(tmp_path: Path) -> None:
    (tmp_path / f"{icon_resolver.PNG_STEM}_96.png").write_bytes(b"")

    assert icon_resolver.get_app_icon_png_path(100, tmp_path) == (
        tmp_path / f"{icon_resolver.PNG_STEM}_96.png"
    )


def test_app_icon_png_is_none_when_that_size_was_never_generated(
    tmp_path: Path,
) -> None:
    assert icon_resolver.get_app_icon_png_path(256, tmp_path) is None


def test_the_real_checkout_resolves_its_generated_icons() -> None:
    """The wiring, checked against the repository rather than a fixture."""

    assets = icon_resolver.find_assets_dir()
    if assets is None:  # pragma: no cover - only on a checkout without assets
        pytest.skip("generate_icons.py has not been run in this checkout")

    assert icon_resolver.get_app_icon_path() == assets / icon_resolver.ICO_NAME
    badge = icon_resolver.get_app_icon_png_path(icon_resolver.BADGE_PNG_SIZE)
    assert badge is not None and badge.is_file()

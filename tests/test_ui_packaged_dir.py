from __future__ import annotations

from pathlib import Path

import pytest

from latencylab_ui import packaged_dir


class _FakeCompiled:
    """Stands in for the `__compiled__` object Nuitka injects into a build."""

    def __init__(self, containing_dir: str) -> None:
        self.containing_dir = containing_dir


def test_source_root_is_the_repository_root() -> None:
    root = packaged_dir.source_root()
    assert (root / "latencylab_ui" / "packaged_dir.py").is_file()


def test_compiled_dir_is_none_when_running_from_source() -> None:
    assert packaged_dir.compiled_dir() is None


def test_compiled_dir_reads_the_nuitka_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(packaged_dir.__dict__, "__compiled__", _FakeCompiled(r"C:\app"))
    assert packaged_dir.compiled_dir() == Path(r"C:\app")


def test_executable_dir_is_none_unless_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    assert packaged_dir.executable_dir() is None


def test_executable_dir_is_the_exe_directory_when_frozen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "LatencyLab.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(exe))
    assert packaged_dir.executable_dir() == tmp_path.resolve()


def test_bundle_dir_is_none_outside_pyinstaller() -> None:
    assert packaged_dir.bundle_dir() is None


def test_bundle_dir_reads_the_pyinstaller_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys._MEIPASS", r"C:\unpacked", raising=False)
    assert packaged_dir.bundle_dir() == Path(r"C:\unpacked")


def test_the_stated_bundle_location_beats_the_inferred_ones() -> None:
    """PyInstaller's own answer outranks guessing from the executable.

    This is what makes the macOS .app work: collected data has moved between
    Contents/MacOS, Contents/Resources and Contents/Frameworks across
    PyInstaller releases, so the inferred paths are a coin toss and the stated
    one is not.
    """

    candidates = packaged_dir.candidate_dirs(
        dir_name="examples",
        env_value=None,
        executable_dir=Path("/App.app/Contents/MacOS"),
        compiled_dir=None,
        source_root=Path("/src"),
        bundle_dir=Path("/App.app/Contents/Frameworks"),
    )

    assert candidates[0] == Path("/App.app/Contents/Frameworks/examples")
    assert candidates.index(Path("/App.app/Contents/Frameworks/examples")) < (
        candidates.index(Path("/App.app/Contents/MacOS/examples"))
    )


def test_an_explicit_override_still_beats_the_bundle_location() -> None:
    candidates = packaged_dir.candidate_dirs(
        dir_name="examples",
        env_value="/override",
        executable_dir=None,
        compiled_dir=None,
        source_root=Path("/src"),
        bundle_dir=Path("/unpacked"),
    )

    assert candidates[0] == Path("/override")


def test_the_flatpak_default_is_derived_from_the_directory_name() -> None:
    candidates = packaged_dir.candidate_dirs(
        dir_name="examples",
        env_value=None,
        executable_dir=None,
        compiled_dir=None,
        source_root=Path("/src"),
    )

    assert Path("/app/examples") in candidates


def test_first_existing_dir_returns_none_when_nothing_exists(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    assert packaged_dir.first_existing_dir((missing,)) is None


def test_first_existing_dir_skips_past_the_absent_candidates(tmp_path: Path) -> None:
    present = tmp_path / "present"
    present.mkdir()

    found = packaged_dir.first_existing_dir((tmp_path / "absent", present))

    assert found == present

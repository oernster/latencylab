from __future__ import annotations

from pathlib import Path

import latencylab
from latencylab.version import FALLBACK_VERSION, VERSION_FILE, read_version

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_version_file_is_the_only_declared_version() -> None:
    import latencylab_ui

    recorded = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert recorded
    assert VERSION_FILE == REPO_ROOT / "VERSION"
    assert latencylab.__version__ == recorded
    assert latencylab_ui.__version__ == recorded


def test_read_version_falls_back_when_the_file_is_absent(tmp_path: Path) -> None:
    assert read_version(tmp_path / "VERSION") == FALLBACK_VERSION


def test_read_version_falls_back_when_the_file_is_empty(tmp_path: Path) -> None:
    empty = tmp_path / "VERSION"
    empty.write_text("   \n", encoding="utf-8")

    assert read_version(empty) == FALLBACK_VERSION


def _site(tmp_path: Path, body: str) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text(body, encoding="utf-8")
    return docs


def test_target_files_collects_html_and_markdown_only(tmp_path: Path) -> None:
    import stamp_version

    docs = _site(tmp_path, "<p>v<!--VERSION-->0.0.0<!--/VERSION--></p>")
    (docs / "notes.md").write_text("# notes", encoding="utf-8")
    (docs / "styles.css").write_text("body{}", encoding="utf-8")

    names = [path.name for path in stamp_version.target_files(docs)]

    assert names == ["index.html", "notes.md"]


def test_stamp_file_rewrites_the_token(tmp_path: Path) -> None:
    import stamp_version

    docs = _site(tmp_path, "<p>v<!--VERSION-->0.0.0<!--/VERSION--></p>")
    page = docs / "index.html"

    assert stamp_version.stamp_file(page, "9.9.9") is True
    assert page.read_text(encoding="utf-8") == (
        "<p>v<!--VERSION-->9.9.9<!--/VERSION--></p>"
    )


def test_stamp_file_leaves_an_already_current_file_alone(tmp_path: Path) -> None:
    import stamp_version

    docs = _site(tmp_path, "<p>v<!--VERSION-->9.9.9<!--/VERSION--></p>")

    assert stamp_version.stamp_file(docs / "index.html", "9.9.9") is False


def test_main_stamps_then_becomes_a_no_op(tmp_path: Path, capsys) -> None:
    import stamp_version

    docs = _site(tmp_path, "<p>v<!--VERSION-->0.0.0<!--/VERSION--></p>")

    assert stamp_version.main(docs, "9.9.9") == 0
    first = capsys.readouterr().out
    assert "VERSION = 9.9.9" in first
    assert "Stamped docs/index.html" in first.replace("\\", "/")

    assert stamp_version.main(docs, "9.9.9") == 0
    assert "No files needed stamping." in capsys.readouterr().out


def test_main_defaults_to_the_version_file(tmp_path: Path, capsys) -> None:
    import stamp_version

    docs = _site(tmp_path, "<p>no token here</p>")

    assert stamp_version.main(docs) == 0
    assert f"VERSION = {latencylab.__version__}" in capsys.readouterr().out

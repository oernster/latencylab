"""The update check's pure core: version compare, skip and asset selection."""

from __future__ import annotations

import pytest

from latencylab_ui.update_core import (
    ReleaseAsset,
    ReleaseInfo,
    UpdateService,
    is_newer,
    platform_key_for,
    select_asset_url,
)

ASSETS = (
    ReleaseAsset("LatencyLabSetup.exe", "https://example.com/LatencyLabSetup.exe"),
    ReleaseAsset("latencylab.dmg", "https://example.com/latencylab.dmg"),
    ReleaseAsset("latencylab.flatpak", "https://example.com/latencylab.flatpak"),
)


class FakeReleaseSource:
    def __init__(self, release: ReleaseInfo | None = None) -> None:
        self._release = release

    def latest_release(self) -> ReleaseInfo | None:
        return self._release


def release(version: str = "v3.1.0", assets=ASSETS) -> ReleaseInfo:
    return ReleaseInfo(
        version=version,
        page_url="https://github.com/oernster/latencylab/releases/latest",
        assets=assets,
    )


def test_newer_equal_and_older() -> None:
    assert is_newer("3.1.0", "3.0.3") is True
    assert is_newer("3.0.3", "3.0.3") is False
    assert is_newer("3.0.2", "3.0.3") is False


def test_prefixes_and_whitespace() -> None:
    assert is_newer("v3.1.0", "3.0.3") is True
    assert is_newer("V3.1.0", "3.0.3") is True
    assert is_newer("  3.1.0  ", "3.0.3") is True


def test_extra_component_compares_positionally() -> None:
    assert is_newer("3.1", "3.0.3") is True
    assert is_newer("3.0.3.1", "3.0.3") is True


@pytest.mark.parametrize("latest", ["", "not-a-version", "3.1.0-rc1", "3..0"])
def test_malformed_latest_is_not_newer(latest: str) -> None:
    assert is_newer(latest, "3.0.3") is False


@pytest.mark.parametrize("current", ["", "0.0.0-dev", "garbage"])
def test_malformed_current_is_not_newer(current: str) -> None:
    assert is_newer("3.1.0", current) is False


def test_unreachable_source_returns_none() -> None:
    service = UpdateService(FakeReleaseSource(None), "3.0.3", "windows")
    assert service.check() is None


def test_newer_release_offers_update_with_asset_and_page() -> None:
    service = UpdateService(FakeReleaseSource(release()), "3.0.3", "windows")
    status = service.check()
    assert status is not None
    assert status.update_available is True
    assert status.latest == "v3.1.0"
    assert status.current == "3.0.3"
    assert status.download_url == "https://example.com/LatencyLabSetup.exe"
    assert status.page_url is not None


def test_same_version_is_not_offered() -> None:
    service = UpdateService(FakeReleaseSource(release("v3.0.3")), "3.0.3", "windows")
    status = service.check()
    assert status is not None
    assert status.update_available is False
    assert status.download_url is None


def test_skipped_version_is_seen_but_not_offered() -> None:
    service = UpdateService(FakeReleaseSource(release()), "3.0.3", "windows")
    status = service.check(skipped_version="v3.1.0")
    assert status is not None
    assert status.update_available is False
    assert status.latest == "v3.1.0"


def test_different_skipped_version_still_offers() -> None:
    service = UpdateService(FakeReleaseSource(release()), "3.0.3", "windows")
    status = service.check(skipped_version="v3.0.9")
    assert status is not None
    assert status.update_available is True


def test_no_matching_asset_falls_back_to_page_only() -> None:
    source = FakeReleaseSource(
        release(assets=(ReleaseAsset("checksums.txt", "https://x/c"),))
    )
    status = UpdateService(source, "3.0.3", "windows").check()
    assert status is not None
    assert status.update_available is True
    assert status.download_url is None


@pytest.mark.parametrize(
    "platform_key,expected",
    [
        ("windows", "https://example.com/LatencyLabSetup.exe"),
        ("macos", "https://example.com/latencylab.dmg"),
        ("linux", "https://example.com/latencylab.flatpak"),
    ],
)
def test_platform_asset_selection(platform_key: str, expected: str) -> None:
    assert select_asset_url(ASSETS, platform_key) == expected


def test_asset_selection_edges() -> None:
    assert select_asset_url((), "windows") is None
    assert select_asset_url(ASSETS, "beos") is None
    upper = (ReleaseAsset("LATENCYLABSETUP.EXE", "https://x/setup"),)
    assert select_asset_url(upper, "windows") == "https://x/setup"


@pytest.mark.parametrize(
    "sys_platform,expected",
    [
        ("win32", "windows"),
        ("darwin", "macos"),
        ("linux", "linux"),
        ("freebsd14", "linux"),
    ],
)
def test_platform_key_mapping(sys_platform: str, expected: str) -> None:
    assert platform_key_for(sys_platform) == expected

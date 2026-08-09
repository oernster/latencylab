"""The GitHub releases adapter, driven through an injected fake opener."""

from __future__ import annotations

import json

import pytest

from latencylab_ui.update_github import (
    _ACCEPT_HEADER,
    _API_URL,
    _TIMEOUT_SECONDS,
    GitHubReleaseSource,
)

PAYLOAD = {
    "tag_name": "v3.1.0",
    "html_url": "https://github.com/oernster/latencylab/releases/tag/v3.1.0",
    "assets": [
        {
            "name": "LatencyLabSetup.exe",
            "browser_download_url": "https://example.com/LatencyLabSetup.exe",
        },
    ],
}


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class FakeOpener:
    def __init__(self, body: bytes | None = None, error: Exception | None = None):
        self._body = body
        self._error = error
        self.request = None
        self.timeout = None

    def __call__(self, request, timeout=None):
        self.request = request
        self.timeout = timeout
        if self._error is not None:
            raise self._error
        return FakeResponse(self._body or b"")


def source_for(payload: dict) -> GitHubReleaseSource:
    return GitHubReleaseSource(FakeOpener(json.dumps(payload).encode("utf-8")))


def test_happy_path() -> None:
    release = source_for(PAYLOAD).latest_release()
    assert release is not None
    assert release.version == "v3.1.0"
    assert release.page_url == PAYLOAD["html_url"]
    assert release.assets[0].name == "LatencyLabSetup.exe"


def test_request_target_headers_and_timeout() -> None:
    opener = FakeOpener(json.dumps(PAYLOAD).encode("utf-8"))
    GitHubReleaseSource(opener).latest_release()
    assert opener.request.full_url == _API_URL
    assert opener.request.get_header("Accept") == _ACCEPT_HEADER
    assert opener.timeout == _TIMEOUT_SECONDS


def test_failures_return_none() -> None:
    assert GitHubReleaseSource(FakeOpener(error=OSError())).latest_release() is None
    assert GitHubReleaseSource(FakeOpener(b"not json")).latest_release() is None
    assert GitHubReleaseSource(FakeOpener(b"[1]")).latest_release() is None


@pytest.mark.parametrize("tag", [None, "", "   ", 42])
def test_missing_or_invalid_tag_returns_none(tag) -> None:
    payload = dict(PAYLOAD)
    if tag is None:
        del payload["tag_name"]
    else:
        payload["tag_name"] = tag
    assert source_for(payload).latest_release() is None


@pytest.mark.parametrize("page_url", [None, "", 42])
def test_missing_or_invalid_page_url_becomes_none(page_url) -> None:
    payload = dict(PAYLOAD)
    if page_url is None:
        del payload["html_url"]
    else:
        payload["html_url"] = page_url
    release = source_for(payload).latest_release()
    assert release is not None
    assert release.page_url is None


@pytest.mark.parametrize("assets", [None, "nope", 42])
def test_missing_or_non_list_assets_become_empty(assets) -> None:
    payload = dict(PAYLOAD)
    if assets is None:
        del payload["assets"]
    else:
        payload["assets"] = assets
    release = source_for(payload).latest_release()
    assert release is not None
    assert release.assets == ()


def test_malformed_asset_entries_are_filtered() -> None:
    payload = dict(PAYLOAD)
    payload["assets"] = [
        "not-a-dict",
        {"browser_download_url": "https://x/no-name"},
        {"name": "", "browser_download_url": "https://x/empty-name"},
        {"name": "no-url.exe"},
        {"name": 42, "browser_download_url": "https://x/int-name"},
        {"name": "good.exe", "browser_download_url": "https://x/good"},
    ]
    release = source_for(payload).latest_release()
    assert release is not None
    assert len(release.assets) == 1
    assert release.assets[0].download_url == "https://x/good"


def test_default_opener_is_urlopen() -> None:
    import urllib.request

    assert GitHubReleaseSource()._opener is urllib.request.urlopen

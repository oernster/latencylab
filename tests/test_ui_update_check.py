"""The update controller: cross-thread delivery, the prompt and the wiring.

The worker thread emits an internal signal connected to a bound method of the
controller, so delivery is queued onto the UI thread; each check therefore
spins the event loop until the outcome lands, which is what proves the
delivery rather than just the logic.
"""

from __future__ import annotations

import time


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeService:
    def __init__(self, status=None, error: Exception | None = None) -> None:
        self._status = status
        self._error = error
        self.calls: list[str | None] = []

    def check(self, skipped_version=None):
        self.calls.append(skipped_version)
        if self._error is not None:
            raise self._error
        return self._status


class FakeSettings:
    def __init__(self, skipped: str | None = None) -> None:
        self.skipped = skipped

    def load_skipped_version(self):
        return self.skipped

    def save_skipped_version(self, version: str) -> None:
        self.skipped = version


def _status(available=True, download_url="https://x/setup.exe", page_url="https://x/r"):
    from latencylab_ui.update_core import UpdateStatus

    return UpdateStatus(
        current="3.0.3",
        latest="v9.9.9",
        update_available=available,
        download_url=download_url,
        page_url=page_url,
    )


def _spin_until(app, condition, seconds=3.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
    assert condition(), "outcome never arrived on the UI thread"


def _controller(service, settings=None):
    from PySide6.QtWidgets import QWidget

    from latencylab_ui.update_check import UpdateCheckController

    window = QWidget()
    controller = UpdateCheckController(window, service, settings or FakeSettings())
    return window, controller


def test_automatic_offer_is_delivered_and_passes_the_skip() -> None:
    app = _ensure_qapp()
    service = FakeService(_status())
    settings = FakeSettings("v3.0.9")
    window, controller = _controller(service, settings)
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    assert service.calls == ["v3.0.9"]
    assert window._update_prompt.isVisible()
    window._update_prompt.close()


def _assert_silent(app, service) -> None:
    window, controller = _controller(service)
    controller.check_automatically()
    _spin_until(app, lambda: bool(service.calls))
    # Drain the queued delivery deterministically: a second queued event
    # posted after the first cannot arrive before it.
    drained: list[bool] = []
    controller._result_ready.connect(lambda *_: drained.append(True))
    controller._result_ready.emit(None, False)
    _spin_until(app, lambda: bool(drained))
    assert not hasattr(window, "_update_prompt")
    assert not hasattr(window, "_update_report")


def test_automatic_unreachable_is_silent() -> None:
    _assert_silent(_ensure_qapp(), FakeService(None))


def test_automatic_up_to_date_is_silent() -> None:
    _assert_silent(_ensure_qapp(), FakeService(_status(available=False)))


def test_manual_up_to_date_and_failure_report() -> None:
    app = _ensure_qapp()
    window, controller = _controller(FakeService(_status(available=False)))
    controller.check_manually()
    _spin_until(app, lambda: hasattr(window, "_update_report"))
    assert "latest version" in window._update_report.text()
    window._update_report.close()

    window2, controller2 = _controller(FakeService(error=RuntimeError("boom")))
    controller2.check_manually()
    _spin_until(app, lambda: hasattr(window2, "_update_report"))
    assert "could not reach GitHub" in window2._update_report.text()
    window2._update_report.close()


def test_manual_ignores_the_skip() -> None:
    app = _ensure_qapp()
    service = FakeService(_status())
    window, controller = _controller(service, FakeSettings("v9.9.9"))
    controller.check_manually()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    assert service.calls == [None]
    window._update_prompt.close()


def test_prompt_download_opens_the_asset_url(monkeypatch) -> None:
    app = _ensure_qapp()
    opened: list[object] = []
    monkeypatch.setattr(
        "latencylab_ui.update_check.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    window, controller = _controller(FakeService(_status()))
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    window._update_prompt.download_button.click()
    from PySide6.QtCore import QUrl

    assert opened == [QUrl("https://x/setup.exe")]


def test_prompt_download_falls_back_to_the_release_page(monkeypatch) -> None:
    app = _ensure_qapp()
    opened: list[object] = []
    monkeypatch.setattr(
        "latencylab_ui.update_check.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    window, controller = _controller(FakeService(_status(download_url=None)))
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    window._update_prompt.download_button.click()
    from PySide6.QtCore import QUrl

    assert opened == [QUrl("https://x/r")]


def test_prompt_with_no_urls_opens_nothing(monkeypatch) -> None:
    app = _ensure_qapp()
    opened: list[object] = []
    monkeypatch.setattr(
        "latencylab_ui.update_check.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    window, controller = _controller(
        FakeService(_status(download_url=None, page_url=None))
    )
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    window._update_prompt.download_button.click()
    assert opened == []


def test_prompt_skip_persists_the_offered_tag() -> None:
    app = _ensure_qapp()
    settings = FakeSettings()
    window, controller = _controller(FakeService(_status()), settings)
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    window._update_prompt.skip_button.click()
    assert settings.skipped == "v9.9.9"


def test_prompt_later_just_closes() -> None:
    app = _ensure_qapp()
    settings = FakeSettings()
    window, controller = _controller(FakeService(_status()), settings)
    controller.check_automatically()
    _spin_until(app, lambda: hasattr(window, "_update_prompt"))
    window._update_prompt.later_button.click()
    assert settings.skipped is None


def test_menu_gains_the_action_only_when_wired() -> None:
    _ensure_qapp()
    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.main_window_menus import build_menus
    from latencylab_ui.update_check import MENU_ITEM_TEXT

    def _texts(window) -> list[str]:
        texts = []
        for action in window.menuBar().actions():
            menu = action.menu()
            if menu is not None:
                texts.extend(a.text() for a in menu.actions())
        return texts

    wired = QMainWindow()
    calls: list[bool] = []
    build_menus(
        wired,
        on_open_model=lambda: None,
        on_open_example=lambda _p: None,
        on_compose_model=lambda: None,
        on_edit_model=lambda: None,
        on_exit=lambda: None,
        examples=(),
        on_check_updates=lambda: calls.append(True),
    )
    texts = _texts(wired)
    assert MENU_ITEM_TEXT in texts
    for action in wired.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        for entry in menu.actions():
            if entry.text() == MENU_ITEM_TEXT:
                entry.trigger()
    assert calls == [True]

    unwired = QMainWindow()
    build_menus(
        unwired,
        on_open_model=lambda: None,
        on_open_example=lambda _p: None,
        on_compose_model=lambda: None,
        on_edit_model=lambda: None,
        on_exit=lambda: None,
        examples=(),
    )
    assert MENU_ITEM_TEXT not in _texts(unwired)


def test_manual_check_is_a_no_op_before_installation() -> None:
    _ensure_qapp()
    from PySide6.QtWidgets import QWidget

    from latencylab_ui.update_check import manual_check

    manual_check(QWidget())


def test_install_then_manual_check_reports() -> None:
    app = _ensure_qapp()
    from PySide6.QtWidgets import QWidget

    from latencylab_ui.update_check import install_update_check, manual_check
    from latencylab_ui.update_core import UpdateService

    class NoSource:
        def latest_release(self):
            return None

    window = QWidget()
    install_update_check(window, UpdateService(NoSource(), "3.0.3", "windows"))
    assert window._update_check is not None
    manual_check(window)
    _spin_until(app, lambda: hasattr(window, "_update_report"))
    assert "could not reach GitHub" in window._update_report.text()
    window._update_report.close()

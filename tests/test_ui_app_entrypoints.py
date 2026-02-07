from __future__ import annotations


def test_ui_app_run_app_no_event_loop(monkeypatch) -> None:
    import latencylab_ui.app as ui_app

    calls = {"apply_theme": 0, "show": 0, "shutdown_connected": 0}

    class _Sig:
        def connect(self, _fn):
            calls["shutdown_connected"] += 1

    class _FakeApp:
        def __init__(self, _argv):
            self.aboutToQuit = _Sig()

        def setApplicationName(self, _s):
            return None

        def setOrganizationName(self, _s):
            return None

        def exec(self) -> int:
            return 0

        def setStyle(self, _s):
            return None

        def setPalette(self, _p):
            return None

        def setStyleSheet(self, _s):
            return None

        def style(self):
            class _S:
                def standardPalette(self):
                    return None

            return _S()

    class _FakeController:
        def shutdown(self):
            return None

    class _FakeWindow:
        def __init__(self, *, run_controller):
            self._c = run_controller

        def resize(self, *_a):
            return None

        def show(self):
            calls["show"] += 1

    monkeypatch.setattr(ui_app, "QApplication", _FakeApp)
    monkeypatch.setattr(ui_app, "RunController", _FakeController)
    monkeypatch.setattr(ui_app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(
        ui_app,
        "apply_theme",
        lambda *_a: calls.__setitem__("apply_theme", calls["apply_theme"] + 1),
    )

    assert ui_app.run_app(argv=["x"]) == 0
    assert calls["apply_theme"] == 1
    assert calls["show"] == 1
    assert calls["shutdown_connected"] == 1


def test_ui_main_delegates(monkeypatch) -> None:
    import latencylab_ui.__main__ as ui_main
    import latencylab_ui.app as ui_app

    def _fake_run_app(argv):
        return 0

    monkeypatch.setattr(ui_app, "run_app", _fake_run_app)
    assert ui_main.main() == 0


def test_ui_main_import_error_path(monkeypatch) -> None:
    import builtins

    import latencylab_ui.__main__ as ui_main

    real_import = builtins.__import__

    def _raising_import(name, *args, **kwargs):
        if name == "latencylab_ui.app":
            raise ImportError("no pyside")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raising_import)
    assert ui_main.main() == 2


def test_ui_package_version() -> None:
    import latencylab_ui

    assert isinstance(latencylab_ui.__version__, str)


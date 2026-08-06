from __future__ import annotations

import sys

import latencylab_ui.__main__ as ui_main_module


def test_runner_delegates_to_latencylab_ui_main(monkeypatch):
    captured = {}

    def fake_ui_main() -> int:
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(ui_main_module, "main", fake_ui_main)
    monkeypatch.setattr(sys, "argv", ["runner.py", "--example", "123"])

    import runner

    rc = runner.main()

    assert rc == 0
    assert captured["argv"] == ["runner.py", "--example", "123"]


def test_runner_leaves_argv_zero_alone(monkeypatch):
    """The regression that cost a release: argv[0] must stay a real path.

    Nuitka's PySide6 plugin reads `sys.argv[0]` when a Windows icon is compiled
    in, extracts the icons from that file and asserts it found at least one.
    Rewriting argv[0] to a module name pointed it at nothing, so the frozen
    application died before its first window with no console to say why. A test
    from source cannot reach that hook, so what is pinned here is the property
    the hook depends on.
    """

    captured = {}

    def fake_ui_main() -> int:
        captured["argv0"] = sys.argv[0]
        return 0

    monkeypatch.setattr(ui_main_module, "main", fake_ui_main)
    monkeypatch.setattr(sys, "argv", [r"C:\Programs\LatencyLab\LatencyLab.exe"])

    import runner

    assert runner.main() == 0
    assert captured["argv0"] == r"C:\Programs\LatencyLab\LatencyLab.exe"

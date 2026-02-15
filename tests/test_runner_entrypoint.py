from __future__ import annotations

import sys

import latencylab_ui.__main__ as ui_main_module


def test_runner_delegates_to_latencylab_ui_main_and_adjusts_argv(monkeypatch):
    captured = {}

    def fake_ui_main() -> int:
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(ui_main_module, "main", fake_ui_main)
    monkeypatch.setattr(sys, "argv", ["runner.py", "--example", "123"])

    import runner

    rc = runner.main()

    assert rc == 0
    assert captured["argv"] == ["latencylab_ui", "--example", "123"]

from __future__ import annotations


def test_elapsed_seconds() -> None:
    from latencylab_ui.run_controller_facade import elapsed_seconds

    assert elapsed_seconds(started_at=None, now=10.0) == 0.0
    assert elapsed_seconds(started_at=5.0, now=10.0) == 5.0
    assert elapsed_seconds(started_at=5.0, now=1.0) == 0.0


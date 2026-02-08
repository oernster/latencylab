from __future__ import annotations

import time


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _spin(app, *, seconds: float = 0.05) -> None:
    """Let Qt process paint/update events deterministically."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()


def test_critical_path_frequency_widget_set_data_twice_clears_rows() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.critical_path_frequency_widget import (
        CriticalPathFrequencyWidget,
    )
    from latencylab_ui.distributions_agg import CriticalPathBar

    host = QMainWindow()
    w = CriticalPathFrequencyWidget(host)
    host.setCentralWidget(w)
    host.resize(520, 220)
    host.show()
    _spin(app)

    w.set_data(
        [
            CriticalPathBar(label_full="A>B>C", label_display="A>B>C", count=2),
            CriticalPathBar(
                label_full="Other (long tail)",
                label_display="Other (long tail)",
                count=1,
            ),
        ]
    )
    _spin(app)
    assert len(w._rows) == 2  # noqa: SLF001
    assert w._rows[0].toolTip().startswith("2  A>B>C")  # noqa: SLF001

    # Second call must clear old rows and rebuild.
    w.set_data([CriticalPathBar(label_full="X>Y", label_display="X>Y", count=5)])
    _spin(app)
    assert len(w._rows) == 1  # noqa: SLF001
    assert w._rows[0].toolTip().startswith("5  X>Y")  # noqa: SLF001

    host.close()
    _spin(app)


def test_critical_path_frequency_widget_clears_empty_placeholder_widget() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.critical_path_frequency_widget import (
        CriticalPathFrequencyWidget,
    )
    from latencylab_ui.distributions_agg import CriticalPathBar

    host = QMainWindow()
    w = CriticalPathFrequencyWidget(host)
    host.setCentralWidget(w)
    host.resize(520, 220)
    host.show()
    _spin(app)

    # First render no data -> placeholder QLabel is created (not tracked in _rows).
    w.set_data([])
    _spin(app)
    assert not w._rows  # noqa: SLF001

    # Second render data -> placeholder must be removed via layout-item cleanup.
    w.set_data([CriticalPathBar(label_full="A", label_display="A", count=1)])
    _spin(app)
    assert len(w._rows) == 1  # noqa: SLF001

    host.close()
    _spin(app)


def test_critical_path_frequency_widget_zero_count_bar_paints_safely() -> None:
    app = _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.critical_path_frequency_widget import (
        CriticalPathFrequencyWidget,
    )
    from latencylab_ui.distributions_agg import CriticalPathBar

    host = QMainWindow()
    w = CriticalPathFrequencyWidget(host)
    host.setCentralWidget(w)
    host.resize(520, 160)
    host.show()
    _spin(app)

    # A zero-count bar produces a ratio of 0.0 and must early-return from paint.
    w.set_data([CriticalPathBar(label_full="Z", label_display="Z", count=0)])
    _spin(app)

    assert len(w._rows) == 1  # noqa: SLF001

    # `grab()` forces a paint without manually calling paintEvent.
    _ = w._rows[0].grab()  # noqa: SLF001

    host.close()
    _spin(app)


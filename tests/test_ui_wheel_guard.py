from __future__ import annotations

import pytest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.wheel_guard import (
    WheelGuard,
    enclosing_scroll_area,
    install_wheel_guard,
)

WHEEL_STEP = -120


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wheel() -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, WHEEL_STEP),
        QPoint(0, WHEEL_STEP),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _panel(app: QApplication):
    """A spin box and a combo inside a scroll area, as the composer has."""

    area = QScrollArea()
    body = QWidget()
    layout = QVBoxLayout(body)

    spin = QSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    layout.addWidget(spin)

    combo = QComboBox()
    combo.addItems(["one", "two", "three"])
    layout.addWidget(combo)

    # Genuinely taller than the viewport, so the panel has somewhere to scroll
    # to and the forwarded event has a visible effect.
    body.setMinimumHeight(1000)

    area.setWidget(body)
    area.resize(200, 80)
    area.show()
    app.processEvents()

    # A shown panel hands focus to its first focusable child, which is exactly
    # the state this guard does NOT apply to. Clear it, so these tests describe
    # a user scrolling past rather than one already in the control.
    spin.clearFocus()
    combo.clearFocus()
    app.processEvents()
    assert spin.hasFocus() is False
    assert combo.hasFocus() is False

    return area, spin, combo


def test_scrolling_past_an_unfocused_spin_box_does_not_change_it(
    app: QApplication,
) -> None:
    """The reported bug: reading a panel rewrote the model on the way past."""

    area, spin, _combo = _panel(app)
    guard = WheelGuard()

    handled = guard.eventFilter(spin, _wheel())

    assert handled is True
    assert spin.value() == 50

    area.close()
    area.deleteLater()


def test_scrolling_past_an_unfocused_combo_does_not_change_it(
    app: QApplication,
) -> None:
    area, _spin, combo = _panel(app)
    guard = WheelGuard()

    handled = guard.eventFilter(combo, _wheel())

    assert handled is True
    assert combo.currentIndex() == 0

    area.close()
    area.deleteLater()


def test_a_focused_control_keeps_its_wheel(app: QApplication) -> None:
    """Aimed at, rather than travelled over, so the wheel is meant for it."""

    area, spin, _combo = _panel(app)
    spin.setFocus()
    app.processEvents()
    assert spin.hasFocus() is True

    guard = WheelGuard()

    assert guard.eventFilter(spin, _wheel()) is False

    area.close()
    area.deleteLater()


def test_the_panel_still_scrolls_when_the_control_is_denied(
    app: QApplication,
) -> None:
    """Blocking without forwarding would leave a dead patch under the pointer,
    which reads as the application having frozen."""

    area, spin, _combo = _panel(app)
    bar = area.verticalScrollBar()
    bar.setValue(0)
    assert bar.maximum() > 0

    guard = WheelGuard()
    guard.eventFilter(spin, _wheel())
    app.processEvents()

    assert bar.value() > 0

    area.close()
    area.deleteLater()


def test_a_control_outside_any_scroll_area_is_still_protected(
    app: QApplication,
) -> None:
    """Nothing to forward to is not a reason to let the value change."""

    spin = QSpinBox()
    spin.setRange(0, 100)
    spin.setValue(7)
    spin.show()
    app.processEvents()
    spin.clearFocus()
    app.processEvents()

    guard = WheelGuard()

    assert guard.eventFilter(spin, _wheel()) is True
    assert spin.value() == 7
    assert enclosing_scroll_area(spin) is None

    spin.close()
    spin.deleteLater()


def test_widgets_that_scroll_rather_than_change_are_left_alone(
    app: QApplication,
) -> None:
    """A list or a text view IS the thing being scrolled."""

    area, _spin, _combo = _panel(app)
    guard = WheelGuard()

    assert guard.eventFilter(area, _wheel()) is False

    area.close()
    area.deleteLater()


def test_events_that_are_not_the_wheel_pass_straight_through(
    app: QApplication,
) -> None:
    spin = QSpinBox()
    guard = WheelGuard()

    assert guard.eventFilter(spin, QEvent(QEvent.Type.Show)) is False

    spin.deleteLater()


def test_the_guard_is_installed_on_the_application(app: QApplication) -> None:
    guard = install_wheel_guard(app)

    assert isinstance(guard, WheelGuard)
    assert guard.parent() is app

    app.removeEventFilter(guard)

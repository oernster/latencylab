from __future__ import annotations

import pytest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.wheel_guard import (
    WHEEL_FOCUS_BIT,
    WheelGuard,
    can_scroll,
    deny_wheel_focus,
    enclosing_scroll_area,
    install_wheel_guard,
    turned_vertically,
)

WHEEL_STEP = -120


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wheel(dx: int = 0, dy: int = WHEEL_STEP) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(dx, dy),
        QPoint(dx, dy),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _takes_the_wheel(widget: QWidget) -> bool:
    return bool(widget.focusPolicy().value & WHEEL_FOCUS_BIT)


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


def _table_panel(app: QApplication):
    """A spin box in a table in a panel, which is the Contexts editor's shape.

    The table is itself a scroll area, so it stands between the control and the
    panel the user is reading.
    """

    area = QScrollArea()
    body = QWidget()
    layout = QVBoxLayout(body)

    table = QTableWidget(1, 1)
    spin = QSpinBox()
    spin.setRange(0, 100)
    spin.setValue(50)
    table.setCellWidget(0, 0, spin)
    layout.addWidget(table)

    body.setMinimumHeight(1000)
    area.setWidget(body)
    area.resize(200, 80)
    area.show()
    app.processEvents()
    spin.clearFocus()
    app.processEvents()

    return area, table, spin


def test_a_wheel_hungry_control_stops_accepting_focus_from_the_wheel(
    app: QApplication,
) -> None:
    """Qt focuses these on the wheel, which both stole focus and defeated the
    rule below by making every travelled-over control a focused one."""

    spin = QSpinBox()
    assert _takes_the_wheel(spin) is True

    guard = WheelGuard()
    handled = guard.eventFilter(spin, QEvent(QEvent.Type.Polish))

    assert handled is False
    assert _takes_the_wheel(spin) is False
    assert spin.focusPolicy() == Qt.FocusPolicy.StrongFocus

    spin.deleteLater()


def test_narrowing_the_policy_keeps_whatever_else_it_said(app: QApplication) -> None:
    """The claim is only that scrolling past something does not choose it."""

    combo = QComboBox()
    combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    assert deny_wheel_focus(combo) is False
    assert combo.focusPolicy() == Qt.FocusPolicy.NoFocus

    combo.deleteLater()


def test_a_control_that_scrolls_rather_than_changes_keeps_its_policy(
    app: QApplication,
) -> None:
    area = QScrollArea()

    assert deny_wheel_focus(area) is False

    area.deleteLater()


def test_installing_the_guard_disarms_controls_that_already_exist(
    app: QApplication,
) -> None:
    """The filter alone would start a generation late."""

    spin = QSpinBox()
    spin.show()
    app.processEvents()
    spin.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
    assert _takes_the_wheel(spin) is True

    guard = install_wheel_guard(app)

    assert _takes_the_wheel(spin) is False

    app.removeEventFilter(guard)
    spin.close()
    spin.deleteLater()


def test_the_wheel_skips_a_scroll_area_with_nowhere_to_go(app: QApplication) -> None:
    """The Contexts fault: the table absorbed the wheel and the panel the user
    was reading never moved, which is the dead patch reached the other way."""

    area, table, spin = _table_panel(app)
    bar = area.verticalScrollBar()
    bar.setValue(0)
    assert bar.maximum() > 0
    assert can_scroll(table, vertical=True) is False

    guard = WheelGuard()
    handled = guard.eventFilter(spin, _wheel())
    app.processEvents()

    assert handled is True
    assert spin.value() == 50
    assert enclosing_scroll_area(spin) is area
    assert bar.value() > 0

    area.close()
    area.deleteLater()


def test_a_sideways_wheel_asks_the_sideways_bar(app: QApplication) -> None:
    """A panel with vertical room but none sideways cannot take a sideways
    wheel, and handing it one would be the dead patch again."""

    area = QScrollArea()
    # Resizable, so the body tracks the viewport's width and the panel has room
    # to move down but none across.
    area.setWidgetResizable(True)
    body = QWidget()
    layout = QVBoxLayout(body)
    spin = QSpinBox()
    layout.addWidget(spin)
    body.setMinimumHeight(1000)
    area.setWidget(body)
    area.resize(200, 80)
    area.show()
    app.processEvents()
    spin.clearFocus()
    app.processEvents()

    assert turned_vertically(_wheel()) is True
    assert turned_vertically(_wheel(dx=WHEEL_STEP, dy=0)) is False
    assert can_scroll(area, vertical=True) is True
    assert can_scroll(area, vertical=False) is False
    assert enclosing_scroll_area(spin, vertical=True) is area
    assert enclosing_scroll_area(spin, vertical=False) is None

    area.close()
    area.deleteLater()

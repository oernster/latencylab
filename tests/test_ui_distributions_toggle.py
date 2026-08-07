from __future__ import annotations

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from latencylab_ui.main_window import MainWindow


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _Controller(QObject):
    """Enough of a controller for the window to build against."""

    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int, int)
    finished = Signal(int, float)

    def __init__(self) -> None:
        super().__init__()
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def is_cancelled(self, _token: int) -> bool:
        return False

    def shutdown(self) -> None:
        return None


def _window(app: QApplication) -> MainWindow:
    window = MainWindow(run_controller=_Controller())
    window.show()
    app.processEvents()
    return window


def test_the_button_carries_the_application_mark_rather_than_an_emoji(
    app: QApplication,
) -> None:
    """An emoji is drawn by whichever font the platform picks, which makes it
    the one thing on the bar the application does not control."""

    window = _window(app)

    assert window._distributions_btn.text() == ""
    assert window._distributions_btn.icon().isNull() is False
    assert window._distributions_btn.isCheckable() is True

    window.close()
    window.deleteLater()


def test_pressing_it_again_puts_the_panel_away(app: QApplication) -> None:
    """A control that only ever opens leaves the dock's own close cross as the
    only way to undo one press."""

    window = _window(app)
    window._distributions_btn.setEnabled(True)

    window._on_show_distributions_clicked()
    app.processEvents()
    assert window._distributions_dock.isVisible() is True
    assert window._distributions_btn.isChecked() is True

    window._on_show_distributions_clicked()
    app.processEvents()
    assert window._distributions_dock.isVisible() is False
    assert window._distributions_btn.isChecked() is False

    window.close()
    window.deleteLater()


def test_the_button_tracks_the_dock_rather_than_the_click(app: QApplication) -> None:
    """Closed by its own cross, the dock is still closed, and a button left
    checked would be claiming otherwise."""

    window = _window(app)
    window._distributions_btn.setEnabled(True)

    window._on_show_distributions_clicked()
    app.processEvents()
    assert window._distributions_btn.isChecked() is True

    window._distributions_dock.hide()
    app.processEvents()

    assert window._distributions_btn.isChecked() is False

    window.close()
    window.deleteLater()


def test_a_refused_press_does_not_leave_the_button_claiming_a_panel(
    app: QApplication,
) -> None:
    """A checkable button has already flipped itself by the time the click
    arrives, so refusing the action has to put it back."""

    window = _window(app)
    window._distributions_btn.setEnabled(False)
    window._distributions_btn.setChecked(True)

    window._on_show_distributions_clicked()
    app.processEvents()

    assert window._distributions_dock.isVisible() is False
    assert window._distributions_btn.isChecked() is False

    window.close()
    window.deleteLater()


def test_showing_the_panel_leaves_the_composer_where_it_is(
    app: QApplication,
) -> None:
    """The two are allowed up together, which is the case the composer's own
    button reads as "switch" rather than "off"."""

    window = _window(app)
    window._distributions_btn.setEnabled(True)
    window._model_composer_dock.show()
    app.processEvents()

    window._on_show_distributions_clicked()
    app.processEvents()

    assert window._distributions_dock.isVisible() is True
    assert window._model_composer_dock.isVisible() is True

    window.close()
    window.deleteLater()

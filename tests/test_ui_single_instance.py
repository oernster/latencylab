from __future__ import annotations

import pytest

from PySide6.QtWidgets import QApplication, QMainWindow

from latencylab_ui import windows_identity
from latencylab_ui.single_instance import (
    InstanceServer,
    another_instance_is_running,
    raise_window,
)

# Per test, so a run never collides with a real LatencyLab on the same machine.
TEST_SERVER = "latencylab-single-instance-tests"


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_nothing_is_running_when_no_server_listens(app: QApplication) -> None:
    assert another_instance_is_running(server_name=f"{TEST_SERVER}-absent") is False


def test_a_second_instance_is_turned_away_and_wakes_the_first(
    app: QApplication,
) -> None:
    """The whole point: the second copy exits and the first comes forward.

    A guard that only refused the second copy would leave the user with
    nothing at all, which is worse than the duplicate window it prevents.
    """

    woken: list[int] = []
    server = InstanceServer(lambda: woken.append(1), server_name=TEST_SERVER)
    assert server.is_listening() is True

    assert another_instance_is_running(server_name=TEST_SERVER) is True

    # The wake arrives on the event loop, not inside the call above.
    for _ in range(50):
        if woken:
            break
        app.processEvents()

    assert woken == [1]

    server.close()


def test_a_stale_name_does_not_lock_the_application_out(app: QApplication) -> None:
    """A crash must not leave the machine unable to start LatencyLab again.

    The first server here stands in for one left behind by a process that
    died; the second must still be able to take the name.
    """

    name = f"{TEST_SERVER}-stale"
    abandoned = InstanceServer(lambda: None, server_name=name)
    assert abandoned.is_listening() is True

    replacement = InstanceServer(lambda: None, server_name=name)

    assert replacement.is_listening() is True

    replacement.close()
    abandoned.close()


def test_raising_a_window_restores_focuses_and_fronts_it(app: QApplication) -> None:
    from PySide6.QtCore import Qt

    window = QMainWindow()
    window.show()
    app.processEvents()
    window.setWindowState(Qt.WindowState.WindowMinimized)
    app.processEvents()

    raise_window(window)
    app.processEvents()

    # Restored is the part that is checkable headlessly; the offscreen platform
    # reports that it does not support raise() or keyboard grabs at all.
    assert bool(window.windowState() & Qt.WindowState.WindowMinimized) is False
    assert window.isVisible() is True

    window.close()
    window.deleteLater()


def test_the_application_claims_the_identity_the_installer_registers() -> None:
    """Two IDs would reproduce the taskbar bug in a harder-to-see form.

    The constant is duplicated rather than imported, because the installer is a
    separate program that the application does not ship, so the pairing is
    asserted here instead of enforced by an import.
    """

    from installer import installer_logic

    assert windows_identity.APP_AUMID == installer_logic.APP_AUMID


def test_claiming_the_identity_is_a_no_op_away_from_windows() -> None:
    assert windows_identity.claim_app_identity(platform="linux") is False
    assert windows_identity.claim_app_identity(platform="darwin") is False


def test_claiming_the_identity_is_attempted_on_windows(monkeypatch) -> None:
    """Exercised by name rather than by running platform, so the Windows path
    is covered on every machine the suite runs on."""

    calls: list[str] = []

    class _Shell:
        @staticmethod
        def SetCurrentProcessExplicitAppUserModelID(value: str) -> None:  # noqa: N802
            calls.append(value)

    class _Windll:
        shell32 = _Shell()

    import ctypes

    monkeypatch.setattr(ctypes, "windll", _Windll(), raising=False)

    assert windows_identity.claim_app_identity(platform="win32") is True
    assert calls == [windows_identity.APP_AUMID]

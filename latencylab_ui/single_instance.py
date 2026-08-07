from __future__ import annotations

"""One LatencyLab per user, and the running one comes to the front.

A second copy is not merely wasteful here: the installer registers a shortcut,
and a shortcut that starts another copy is why clicking the taskbar icon left
the running window where it was and opened a new one beside it.

A bare mutex would stop the second copy and leave the user with nothing at all,
which is worse than the bug. So the guard is a local socket rather than a lock:
the first instance listens, and a second one connects, says "come forward" and
exits. The message is what raises the first window, so the click does what the
user meant instead of being silently swallowed.

A local socket also survives a crash better than a lock file. A stale file has
to be aged or PID-checked to tell "still running" from "died holding it"; a
stale socket name simply refuses connections, which is a question that can be
asked directly. Windows named pipes, AF_UNIX sockets and the Qt wrapper over
both are the same API here, so this is one implementation for all three
platforms.
"""

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Per user rather than per machine: two people on one machine are two users and
# each is entitled to their own copy.
SERVER_NAME = "latencylab-single-instance"

# How long a second instance waits for the first to accept. Short, because the
# answer is local and the user is holding a mouse button: a first instance that
# cannot answer in this time is one this copy should not be waiting behind.
CONNECT_TIMEOUT_MS = 500

# Sent by the second instance and never read for content. What matters is that
# a connection arrived at all.
WAKE_MESSAGE = b"raise"


def another_instance_is_running(*, server_name: str = SERVER_NAME) -> bool:
    """Whether a first instance answered, having been asked to come forward.

    Returns True when this process should exit because another copy took the
    request.
    """

    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(CONNECT_TIMEOUT_MS):
        return False

    socket.write(WAKE_MESSAGE)
    socket.flush()
    socket.waitForBytesWritten(CONNECT_TIMEOUT_MS)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Listens for later copies of the application asking to be let in."""

    def __init__(
        self,
        on_wake: Callable[[], None],
        *,
        server_name: str = SERVER_NAME,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_wake = on_wake
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)

        # A crash leaves the name behind on some platforms, and nothing else
        # is entitled to it: the caller has already established that no live
        # instance answered on it.
        QLocalServer.removeServer(server_name)
        self._server.listen(server_name)

    def is_listening(self) -> bool:
        return self._server.isListening()

    def close(self) -> None:
        self._server.close()

    def _on_new_connection(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.disconnectFromServer()
        self._on_wake()


def raise_window(window) -> None:
    """Bring a window to the front and give it the keyboard.

    All three calls are needed and none is redundant. A minimised window has to
    be restored before anything else will show it; `raise_` orders it above its
    siblings; `activateWindow` is what actually moves the keyboard focus, which
    is the part the user notices missing.
    """

    from PySide6.QtCore import Qt

    window.setWindowState(
        (window.windowState() & ~Qt.WindowState.WindowMinimized)
        | Qt.WindowState.WindowActive
    )
    window.show()
    window.raise_()
    window.activateWindow()

"""The background thread that runs the install.

One rule governs this file. Every signal emitted here is connected, by the
window, to a BOUND METHOD OF A QObject that lives on the interface thread. A
Qt signal connected to a bare callable (a lambda, a module function, a closure)
runs that callable in the SENDER's thread, so the "finished" handler would
execute on this worker and any attempt to retire the worker from inside it
becomes a thread waiting on itself. That is a hang rather than an error, and
it has bitten this portfolio twice.

The same reasoning is why `wait()` at the call site is always bounded.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from installer.deploy import InstallError, InstallOptions, install, uninstall

# How long the window will wait for this thread to retire before giving up and
# closing anyway. An unbounded wait is how a shutdown becomes a hang.
JOIN_TIMEOUT_MS = 10_000


class InstallWorker(QThread):
    """Runs one install or uninstall and reports on it."""

    progress = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, options: InstallOptions | None) -> None:
        super().__init__()
        # None means uninstall: there are no options to choose when removing.
        self._options = options

    def run(self) -> None:  # pragma: no cover - exercised by a real install
        try:
            if self._options is None:
                uninstall(self._report)
                self.succeeded.emit("Removed")
            else:
                target = install(self._options, self._report)
                self.succeeded.emit(str(target))
        except InstallError as error:
            self.failed.emit(str(error))
        except OSError as error:
            self.failed.emit(f"Unexpected failure.\n\n{error}")

    def _report(self, percent: int, message: str) -> None:
        self.progress.emit(percent, message)

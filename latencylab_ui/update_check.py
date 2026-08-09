"""The update check's UI: triggers, worker thread, prompt and reports.

Threading shape (the house pattern): the worker thread emits ``_result_ready``,
which is connected to a bound method of this controller. The controller lives
on the UI thread, so delivery is a queued connection and the slot, plus every
dialog it opens, runs on the UI thread; a signal connected to a bare callable
would run in the worker's thread instead.

Dialogs are shown with ``open()`` rather than ``exec()``, per this
application's standing rule (a modal event loop is fragile under test and CI):
the prompt's buttons carry the outcome instead of a blocking return value.

The automatic check (a few seconds after launch, then daily) honours the
skipped version and is silent on every non-offer outcome. The manual
Help-menu check ignores the skip and reports every outcome.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.about_text import APP_NAME
from latencylab_ui.update_core import UpdateService, UpdateStatus
from latencylab_ui.update_settings import UpdateSettingsStore

# The launch check waits so it never contends with startup work; the periodic
# re-check covers sessions that stay open for days.
_LAUNCH_DELAY_MS = 3000
_RECHECK_INTERVAL_MS = 24 * 60 * 60 * 1000

_TITLE = "Check for Updates"
MENU_ITEM_TEXT = "Check for Updates…"


class UpdatePromptDialog(QDialog):
    """The offer: Download, Skip This Version or Later.

    The caller connects to ``download_chosen`` and ``skip_chosen``; Later and
    the window close simply reject. Buttons act through signals rather than a
    modal return value so the dialog can be driven without ``exec()``.
    """

    download_chosen = Signal()
    skip_chosen = Signal()

    def __init__(self, parent: QWidget, latest: str, current: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(f"{APP_NAME} {latest} is available.\n" f"You are running {current}.")
        )
        row = QHBoxLayout()
        self.download_button = QPushButton("Download")
        self.skip_button = QPushButton("Skip This Version")
        self.later_button = QPushButton("Later")
        for button in (self.download_button, self.skip_button, self.later_button):
            row.addWidget(button)
        layout.addLayout(row)

        self.download_button.clicked.connect(self._choose_download)
        self.skip_button.clicked.connect(self._choose_skip)
        self.later_button.clicked.connect(self.reject)

    def _choose_download(self) -> None:
        self.download_chosen.emit()
        self.accept()

    def _choose_skip(self) -> None:
        self.skip_chosen.emit()
        self.accept()


def install_update_check(window: QWidget, service: UpdateService) -> None:
    """Attach the update controller to the window. The app calls this once.

    Installed from the composition root rather than built inside MainWindow,
    so the window itself stays out of the update check's business (and under
    the size cap): the menu handler below finds the controller by attribute.
    """

    window._update_check = UpdateCheckController(window, service, UpdateSettingsStore())


def manual_check(window: QWidget) -> None:
    """The Help-menu handler: a quiet no-op until a controller is installed."""

    controller = getattr(window, "_update_check", None)
    if controller is not None:
        controller.check_manually()


class UpdateCheckController(QObject):
    """Owns the update check's triggers, worker and dialogs."""

    _result_ready = Signal(object, bool)

    def __init__(
        self,
        window: QWidget,
        service: UpdateService,
        settings: UpdateSettingsStore,
    ) -> None:
        # Tolerates a stand-in window from monkeypatch-heavy composition
        # tests, which is not a QObject and cannot be a Qt parent.
        super().__init__(window if isinstance(window, QObject) else None)
        self._window = window
        self._service = service
        self._settings = settings
        self._result_ready.connect(self._apply_result)

        QTimer.singleShot(_LAUNCH_DELAY_MS, self.check_automatically)
        self._recheck_timer = QTimer(self)
        self._recheck_timer.setInterval(_RECHECK_INTERVAL_MS)
        self._recheck_timer.timeout.connect(self.check_automatically)
        self._recheck_timer.start()

    def check_automatically(self) -> None:
        """The launch or periodic check: silent on every non-offer outcome."""

        self._start_check(self._settings.load_skipped_version(), manual=False)

    def check_manually(self) -> None:
        """The Help-menu check: reports every outcome and ignores the skip."""

        self._start_check(None, manual=True)

    def _start_check(self, skipped_version: str | None, manual: bool) -> None:
        def _run() -> None:
            try:
                status = self._service.check(skipped_version)
            except Exception:  # noqa: BLE001 (any error reads as unreachable)
                status = None
            self._result_ready.emit(status, manual)

        threading.Thread(
            target=_run, daemon=True, name="latencylab-update-check"
        ).start()

    @Slot(object, bool)
    def _apply_result(self, status: UpdateStatus | None, manual: bool) -> None:
        if status is None:
            if manual:
                self._report(
                    QMessageBox.Icon.Warning,
                    "The update check could not reach GitHub. "
                    "Please try again later.",
                )
            return
        if status.update_available:
            self._offer(status)
            return
        if manual:
            self._report(
                QMessageBox.Icon.Information,
                "You are running the latest version.",
            )

    def _offer(self, status: UpdateStatus) -> None:
        dialog = UpdatePromptDialog(self._window, status.latest, status.current)
        url = status.download_url or status.page_url or ""
        dialog.download_chosen.connect(lambda: self._open_download(url))
        dialog.skip_chosen.connect(
            lambda: self._settings.save_skipped_version(status.latest)
        )
        # Held on the window so the dialog is not garbage-collected on show,
        # the same pattern the Help dialogs use.
        self._window._update_prompt = dialog
        dialog.open()

    def _open_download(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _report(self, icon: QMessageBox.Icon, message: str) -> None:
        box = QMessageBox(
            icon, _TITLE, message, QMessageBox.StandardButton.Ok, self._window
        )
        # Held on the window so the box is not garbage-collected on show.
        self._window._update_report = box
        box.open()

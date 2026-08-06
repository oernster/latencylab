"""The setup window: three pages, one worker, one sequence.

The window owns the order of events. The pages own their controls and the
deployer owns the filesystem, so this file is about nothing except what happens
next and which thread it happens on.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon, QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from installer.constants import (
    APP_NAME,
    CONTENT_MARGIN,
    CONTENT_SPACING,
    ICON_ICO_NAME,
    LICENCE_INSTALLER_NAME,
    LICENCE_MODEL_NAME,
    LICENCE_UI_NAME,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    install_dir,
)
from installer.deploy import InstallOptions
from installer.licence_view import LicenceDialog
from installer.pages import (
    ConfirmUninstallPage,
    DonePage,
    ProgressPage,
    WelcomePage,
)
from installer.paths import payload_asset, payload_file, payload_version
from installer.worker import JOIN_TIMEOUT_MS, InstallWorker

# A zero-size focus holder, so the window opens with nothing highlighted and
# the first Tab enters the real controls rather than resuming mid-ring.
_NEUTRAL_SIZE = 0


class _NeutralStart(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(_NEUTRAL_SIZE, _NEUTRAL_SIZE)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def focusOutEvent(self, event) -> None:
        # Drop out of the tab ring once left, so the cycle holds only real
        # controls from then on.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        super().focusOutEvent(event)


class InstallerWindow(QWidget):
    def __init__(self, *, uninstalling: bool) -> None:
        super().__init__()

        self._uninstalling = uninstalling
        self._worker: InstallWorker | None = None
        self._started = False

        version = payload_version()
        target = str(install_dir())

        self.setWindowTitle(f"{APP_NAME} Setup")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        icon = payload_asset(ICON_ICO_NAME)
        if icon is not None:
            self.setWindowIcon(QIcon(str(icon)))

        root = QVBoxLayout(self)
        root.setContentsMargins(
            CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN
        )
        root.setSpacing(CONTENT_SPACING)

        self._neutral = _NeutralStart(self)

        self._stack = QStackedWidget()
        self._first_page: QWidget = (
            ConfirmUninstallPage(version=version, install_path=target)
            if uninstalling
            else WelcomePage(version=version, install_path=target)
        )
        self._progress_page = ProgressPage()
        self._done_page = DonePage()
        for page in (self._first_page, self._progress_page, self._done_page):
            self._stack.addWidget(page)
        root.addWidget(self._stack, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._secondary = QPushButton("Cancel")
        self._primary = QPushButton("Remove" if uninstalling else "Install")
        self._primary.setObjectName("primary")
        self._primary.setDefault(True)
        buttons.addWidget(self._secondary)
        buttons.addWidget(self._primary)
        root.addLayout(buttons)

        self._primary.clicked.connect(self._on_primary_clicked)
        self._secondary.clicked.connect(self.close)

        if not uninstalling:
            self._wire_licence_buttons()

    def _wire_licence_buttons(self) -> None:
        page = self._first_page
        assert isinstance(page, WelcomePage)
        page.model_licence_button.clicked.connect(self._show_model_licence)
        page.ui_licence_button.clicked.connect(self._show_ui_licence)
        page.installer_licence_button.clicked.connect(self._show_installer_licence)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._started:
            self._started = True
            self._neutral.setFocus(Qt.FocusReason.OtherFocusReason)

    # Licence viewers -----------------------------------------------------

    def _show_licence(self, title: str, name: str) -> None:
        LicenceDialog(self, title=title, path=payload_file(name)).exec()

    def _show_model_licence(self) -> None:
        self._show_licence("Model licence (GPL-3.0)", LICENCE_MODEL_NAME)

    def _show_ui_licence(self) -> None:
        self._show_licence("UI licence (LGPL-3.0)", LICENCE_UI_NAME)

    def _show_installer_licence(self) -> None:
        self._show_licence("Installer notice", LICENCE_INSTALLER_NAME)

    # The sequence --------------------------------------------------------

    def _on_primary_clicked(self) -> None:
        if self._worker is not None:
            # The primary button is the Close button once the work is done.
            self.close()
            return
        self._start()

    def _options(self) -> InstallOptions | None:
        if self._uninstalling:
            return None
        page = self._first_page
        assert isinstance(page, WelcomePage)
        return InstallOptions(
            desktop_shortcut=page.desktop_shortcut.isChecked(),
            start_menu_shortcut=page.start_menu_shortcut.isChecked(),
        )

    def _start(self) -> None:
        self._stack.setCurrentWidget(self._progress_page)
        self._primary.setEnabled(False)
        self._secondary.setEnabled(False)

        worker = InstallWorker(self._options())
        # Bound methods of this window, which lives on the interface thread.
        # A bare callable here would run in the worker's thread and retiring
        # the worker from inside it would deadlock. See installer/worker.py.
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self._progress_page.report(percent, message)

    def _finish(self) -> None:
        self._stack.setCurrentWidget(self._done_page)
        self._primary.setText("Close")
        self._primary.setEnabled(True)
        self._secondary.setEnabled(False)
        self._secondary.setVisible(False)

    def _on_succeeded(self, target: str) -> None:
        if self._uninstalling:
            self._done_page.show_success(
                f"{APP_NAME} has been removed",
                "The last few files are cleared up a moment after this window "
                "closes.",
            )
        else:
            self._done_page.show_success(
                f"{APP_NAME} is installed",
                f"It is in {target}. Open it from the Start Menu or the "
                "Desktop shortcut.",
            )
        self._finish()

    def _on_failed(self, message: str) -> None:
        self._done_page.show_failure(message)
        self._finish()

    def closeEvent(self, event: QCloseEvent) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Bounded, always. An unbounded wait turns a close into a hang.
            worker.wait(JOIN_TIMEOUT_MS)
        super().closeEvent(event)

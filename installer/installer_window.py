"""The installer window: a themed, state-aware lifecycle screen.

One window, whose caption and visible actions follow the install state detected
at construction: a fresh machine sees Install, an existing one sees Upgrade,
Reinstall or Reinstall (older) alongside Repair and Uninstall. Every action is
guarded by a check that the application is not running, because replacing a
running executable is how an install ends up half applied.

The work is done on this thread, with the status line repainted between steps.
There is deliberately no worker thread: a Qt signal connected to a bare callable
runs in the sender's thread; retiring a worker from inside its own finished
handler is a thread waiting on itself. That has hung two installers in this
portfolio already; an install measured in seconds does not need one.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import installer_bundle as bundle
import installer_header as header
import installer_lifecycle as lifecycle
import installer_logic as logic
import installer_ops as ops
import installer_theme as theme
from installer_widgets import AppRunningDialog, NeutralStart, UninstallDialog

APP_DISPLAY_NAME = logic.APP_DISPLAY_NAME
AppState = logic.AppState


class InstallerWindow(QWidget):
    """The installer window: a themed, state-aware lifecycle screen."""

    def __init__(self) -> None:
        super().__init__()
        self._state = lifecycle.detect_state()
        self.setWindowTitle(theme.WINDOW_TITLE)
        self.setWindowIcon(bundle.app_icon())
        self.resize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self.setStyleSheet(theme.STYLESHEET)

        self._desktop = QCheckBox("Create a desktop shortcut")
        self._start_menu = QCheckBox("Create a Start Menu shortcut")
        self._launch_on_finish = QCheckBox(f"Launch {APP_DISPLAY_NAME} when finished")
        self._status = QLabel("")
        self._status.setObjectName("StatusLine")
        self._status.setWordWrap(True)

        self._primary = QPushButton(lifecycle.primary_label(self._state))
        self._primary.setObjectName("PrimaryAction")
        self._repair = QPushButton("Repair")
        self._repair.setObjectName("SecondaryAction")
        self._uninstall = QPushButton("Uninstall")
        self._uninstall.setObjectName("DangerAction")

        self._shown = False
        # Launch is neutral, exactly like the application's main window: nothing
        # wears a ring until the keyboard or the mouse asks for one.
        self._start = NeutralStart(self)
        self._build_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            self._start.setFocus()

    def keyPressEvent(self, event) -> None:
        # A plain QWidget window has no dialog default-button mechanism, so
        # Enter would otherwise do nothing on a focused button or checkbox.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            target = self.focusWidget()
            if isinstance(target, QAbstractButton) and target.isEnabled():
                target.click()
                return
        super().keyPressEvent(event)

    # ----------------------------------------------------------------- layout

    def _build_ui(self) -> None:
        """Assemble the themed installer layout in one top-to-bottom column."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.MARGIN_SIDE, theme.MARGIN_TOP, theme.MARGIN_SIDE, theme.MARGIN_BOTTOM
        )
        layout.setSpacing(theme.SECTION_SPACING)

        layout.addLayout(header.build_header(self))

        subtitle = QLabel(logic.subtitle_text(self._state))
        subtitle.setObjectName("SubTitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle)

        tagline = QLabel(logic.APP_TAGLINE)
        tagline.setObjectName("Tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(theme.DIVIDER_PX)
        layout.addWidget(divider)

        path_label = QLabel(f"Install location: {ops.install_target()}")
        path_label.setObjectName("InstallPath")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        no_admin = QLabel(
            "No administrator rights are needed. Nothing outside your own user "
            "profile is changed."
        )
        no_admin.setObjectName("InstallPath")
        no_admin.setWordWrap(True)
        layout.addWidget(no_admin)

        self._desktop.setChecked(True)
        layout.addWidget(self._desktop)
        self._start_menu.setChecked(True)
        layout.addWidget(self._start_menu)
        self._launch_on_finish.setChecked(True)
        layout.addWidget(self._launch_on_finish)
        layout.addWidget(self._status)

        layout.addStretch()
        layout.addLayout(self._build_buttons())

    def _build_buttons(self) -> QHBoxLayout:
        """Build the action row: Uninstall, Repair, the primary action, Close."""

        self._primary.clicked.connect(self._on_primary)
        self._repair.clicked.connect(self._on_repair)
        self._uninstall.clicked.connect(self._on_uninstall)
        close_button = QPushButton("Close")
        close_button.setObjectName("SecondaryAction")
        close_button.clicked.connect(self.close)

        installed = self._state != AppState.NOT_INSTALLED
        self._repair.setVisible(installed)
        self._uninstall.setVisible(installed)

        buttons = QHBoxLayout()
        buttons.setSpacing(theme.BUTTON_GAP)
        buttons.addWidget(self._uninstall)
        buttons.addStretch()
        buttons.addWidget(self._repair)
        buttons.addWidget(self._primary)
        buttons.addWidget(close_button)
        return buttons

    # ---------------------------------------------------------------- actions

    def _guard_not_running(self, action: str) -> bool:
        """True when the app is not running; otherwise ask the user to close it."""

        if not ops.is_app_running():
            return True
        if AppRunningDialog(action, self).exec() == QDialog.DialogCode.Accepted:
            return True
        self._status.setText(
            f"{APP_DISPLAY_NAME} is still running, so the {action} was cancelled."
        )
        return False

    def _on_primary(self) -> None:
        """Install, upgrade or reinstall, then optionally launch the app."""

        if not self._guard_not_running("installation"):
            return
        self._set_busy("Installing...")
        try:
            exe_path = lifecycle.install(
                ops.install_target(),
                desktop=self._desktop.isChecked(),
                start_menu=self._start_menu.isChecked(),
            )
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Installation failed: {error}")
            return
        # Refresh BEFORE launching. The window must read as an installed machine
        # whatever the launch then does, because the launch is the step most
        # likely to go wrong and a window frozen mid-install is the worst thing
        # to leave behind when it does.
        self._refresh_after_change()
        self._status.setText(f"Installed to {exe_path.parent}.")
        if self._launch_on_finish.isChecked():
            self._launch_and_front(exe_path)

    def _launch_and_front(self, exe_path: Path) -> None:
        """Launch the app, wait for its window, front it, then close.

        A window that arrives after the installer has gone is denied focus by
        Windows and only flashes on the taskbar, so the fronting happens while
        the installer still owns the foreground.

        Nothing here closes the installer except a window that actually
        appeared. A launch that fails, or one whose window never arrives, leaves
        the installer open and says so: closing on failure is indistinguishable
        from success and hides the only evidence the user has.
        """

        process = ops.launch(exe_path)
        if process is None:
            self._status.setText(
                f"Installed, but {APP_DISPLAY_NAME} could not be started from "
                f"{exe_path}."
            )
            return
        self._status.setText(f"Launching {APP_DISPLAY_NAME}...")
        self._front_pid = process.pid
        self._front_deadline = time.monotonic() + ops.FOREGROUND_WAIT_S
        self._front_timer = QTimer(self)
        self._front_timer.timeout.connect(self._front_launched_app)
        self._front_timer.start(ops.FOREGROUND_POLL_MS)

    def _front_launched_app(self) -> None:
        if ops.bring_process_window_to_front(self._front_pid):
            self._front_timer.stop()
            self.close()
            return
        if time.monotonic() > self._front_deadline:
            self._front_timer.stop()
            self._status.setText(
                f"Installed. {APP_DISPLAY_NAME} was started but showed no window "
                f"within {int(ops.FOREGROUND_WAIT_S)} seconds."
            )

    def _on_repair(self) -> None:
        """Re-deploy the application files over the existing install."""

        if not self._guard_not_running("repair"):
            return
        _, location = ops.read_installed()
        self._set_busy("Repairing...")
        try:
            lifecycle.repair(location or ops.install_target())
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Repair failed: {error}")
            return
        self._status.setText("Repair complete.")
        self._refresh_after_change()

    def _on_uninstall(self) -> None:
        """Confirm, then remove the application, shortcuts and registration."""

        if not self._guard_not_running("uninstall"):
            return
        if UninstallDialog(self).exec() != QDialog.DialogCode.Accepted:
            return
        self._set_busy("Uninstalling...")
        try:
            lifecycle.uninstall()
        except Exception as error:  # noqa: BLE001 - surfaced as a status message
            self._finish_error(f"Uninstall failed: {error}")
            return
        self._status.setText(f"{APP_DISPLAY_NAME} has been uninstalled.")
        self._state = AppState.NOT_INSTALLED
        self._primary.setText(lifecycle.primary_label(self._state))
        self._repair.setVisible(False)
        self._uninstall.setVisible(False)
        self._primary.setEnabled(True)

    def _set_busy(self, message: str) -> None:
        """Show a status message and disable the action buttons during work."""

        self._status.setText(message)
        self._primary.setEnabled(False)
        self._repair.setEnabled(False)
        self._uninstall.setEnabled(False)
        QApplication.processEvents()

    def _finish_error(self, message: str) -> None:
        """Show an error and restore the buttons to their accepted state."""

        self._status.setText(message)
        self._primary.setEnabled(True)
        self._repair.setEnabled(True)
        self._uninstall.setEnabled(True)

    def _refresh_after_change(self) -> None:
        """Re-detect state after an install or repair and relabel the buttons."""

        self._state = lifecycle.detect_state()
        self._primary.setText(lifecycle.primary_label(self._state))
        installed = self._state != AppState.NOT_INSTALLED
        self._repair.setVisible(installed)
        self._uninstall.setVisible(installed)
        self._uninstall.setEnabled(True)
        self._primary.setEnabled(True)
        self._repair.setEnabled(True)

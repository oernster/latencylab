"""Install, repair and uninstall, composed from the decisions and the effects.

Each function here is one complete action: it reads the payload, deploys or
removes files, writes or clears the registration and puts the shortcuts where
the user asked for them.
"""

from __future__ import annotations

from pathlib import Path

import installer_bundle as bundle
import installer_logic as logic
import installer_ops as ops
import installer_payload as payload


def detect_state() -> str:
    """Classify this machine against the version in the payload."""

    installed, location = ops.read_installed()
    return logic.detect_state(installed, location, bundle.app_version())


def primary_label(state: str) -> str:
    return logic.primary_label(state, bundle.app_version())


def install(target: Path, *, desktop: bool, start_menu: bool) -> Path:
    """Deploy the application, register it and create the chosen shortcuts."""

    exe_path = payload.deploy_files(
        payload.payload_archive(bundle.bundle_root()), target
    )

    uninstaller = logic.uninstaller_path(target)
    uninstaller.parent.mkdir(parents=True, exist_ok=True)
    _copy_installer(uninstaller)

    ops.write_uninstall_entry(
        logic.uninstall_entry_values(
            target,
            uninstaller,
            bundle.app_version() or logic.FALLBACK_VERSION,
            logic.dir_size_kb(target),
        )
    )

    icon = target / logic.ASSETS_DIR_NAME / logic.SHORTCUT_ICON_FILE_NAME
    resolved_icon = icon if icon.is_file() else None

    if desktop:
        ops.create_shortcut(ops.desktop_link(), exe_path, resolved_icon)
    else:
        ops.remove_shortcut(ops.desktop_link())

    start_menu_link = ops.start_menu_link()
    if start_menu and start_menu_link is not None:
        ops.create_shortcut(start_menu_link, exe_path, resolved_icon)
    elif start_menu_link is not None:
        ops.remove_shortcut(start_menu_link)

    return exe_path


def _copy_installer(destination: Path) -> None:
    """Keep a copy of this setup program so Apps and features can re-run it."""

    import shutil

    source = ops.running_installer_exe()
    if source.is_file() and source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def repair(location: Path) -> Path:
    """Re-deploy the application files over an existing install."""

    return install(location, desktop=False, start_menu=False)


def uninstall() -> None:
    """Remove the application, its shortcuts and its registration."""

    _, location = ops.read_installed()
    target = location or ops.install_target()

    ops.remove_shortcut(ops.desktop_link())
    ops.remove_shortcut(ops.start_menu_link())
    ops.delete_uninstall_entry()

    ops.remove_tree_except(target, logic.UNINSTALLER_SUBDIR)
    ops.schedule_self_delete(target)

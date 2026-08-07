from __future__ import annotations

import platform
from collections.abc import Callable
from pathlib import Path

import PySide6
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QWidget

from latencylab_ui import main_window_actions as actions
from latencylab_ui.about_dialog import AboutDialog, AboutDialogContent
from latencylab_ui.about_text import APP_NAME, about_html
from latencylab_ui.example_models import ExampleModel, list_examples
from latencylab_ui.how_to_read_dialog import HowToReadDialog

EXAMPLES_MENU_TITLE = "Examples"

MODEL_MENU_TITLE = "Model"

# The same two actions the tray carries. A menu item and a toolbar button that
# do the same thing are wired to the same callable rather than to two handlers
# that have to be kept in step.
COMPOSE_ITEM_TEXT = "Compose new model"
EDIT_ITEM_TEXT = "Edit loaded model"

# Shown in place of the models when none are bundled, so the menu explains
# itself rather than appearing broken. A disabled item is deliberate: the ring
# skips it, exactly as it skips every other disabled control.
NO_EXAMPLES_TEXT = "No examples bundled"


def build_menus(
    window: QMainWindow,
    *,
    on_open_model: Callable[[], None],
    on_open_example: Callable[[Path], None],
    on_compose_model: Callable[[], None],
    on_edit_model: Callable[[], None],
    on_exit: Callable[[], None],
    examples: tuple[ExampleModel, ...] | None = None,
) -> QAction:
    """Create the app menu bar, returning the Edit action.

    Menu titles are part of the focus-cycle traversal.

    Edit comes back because it is the one item here whose availability changes:
    there is nothing to edit until a model is loaded. The window owns that
    rule for every other control, so it owns this one too rather than the menu
    growing a second opinion about when editing is possible.
    """

    file_menu = add_menu(window, "File")
    open_action = file_menu.addAction("Open model…")
    open_action.triggered.connect(on_open_model)
    file_menu.addSeparator()
    exit_action = file_menu.addAction("Exit")
    exit_action.triggered.connect(on_exit)

    build_examples_menu(window, on_open_example=on_open_example, examples=examples)

    model_menu = add_menu(window, MODEL_MENU_TITLE)
    compose_action = model_menu.addAction(COMPOSE_ITEM_TEXT)
    compose_action.setToolTip(actions.COMPOSE_READY)
    compose_action.triggered.connect(on_compose_model)
    edit_action = model_menu.addAction(EDIT_ITEM_TEXT)
    edit_action.setToolTip(actions.EDIT_READY)
    edit_action.triggered.connect(on_edit_model)

    help_menu = add_menu(window, "Help")

    how_to_read_action = help_menu.addAction("How to Read LatencyLab Output")
    how_to_read_action.triggered.connect(lambda: show_how_to_read_dialog(window))

    about_action = help_menu.addAction("About…")
    about_action.triggered.connect(lambda: show_about_dialog(window))

    licence_action = help_menu.addAction("UI Licence…")
    licence_action.triggered.connect(lambda: show_licence_dialog(window))

    main_licence_action = help_menu.addAction("Main Licence…")
    main_licence_action.triggered.connect(lambda: show_main_licence_dialog(window))

    return edit_action


def add_menu(window: QMainWindow, title: str) -> QMenu:
    """A menu on the bar whose lifetime is the window's.

    `menuBar().addMenu(title)` looks equivalent and is not. The menu it builds
    is destroyed when the Python wrapper of its QAction is collected, which
    leaves the bar holding a deleted object, and anything that walks
    `menuBar().actions()` and discards the wrappers can trigger it: the focus
    ring rebuilds exactly that list on every keystroke. Constructing the menu
    with an explicit parent first makes the ownership C++'s, where it belongs.
    """

    menu = QMenu(title, window)
    window.menuBar().addMenu(menu)
    return menu


def build_examples_menu(
    window: QMainWindow,
    *,
    on_open_example: Callable[[Path], None],
    examples: tuple[ExampleModel, ...] | None = None,
) -> QMenu:
    """A top-level menu holding every model the application ships with.

    Top-level rather than a submenu under File on purpose. The focus ring claims
    Left and Right to step between stops, which is the same pair Qt uses to open
    and close a submenu, so a submenu would be the one part of the menu bar the
    keyboard could not reach the usual way. A title of its own costs nothing and
    is walked by the ring like any other.
    """

    if examples is None:
        examples = list_examples()

    menu = add_menu(window, EXAMPLES_MENU_TITLE)

    if not examples:
        empty = menu.addAction(NO_EXAMPLES_TEXT)
        empty.setEnabled(False)
        return menu

    for example in examples:
        action = menu.addAction(example.label)
        # `path` is bound as a default argument rather than captured, so every
        # action keeps its own model instead of all of them sharing the last.
        action.triggered.connect(
            lambda _checked=False, path=example.path: on_open_example(path)
        )

    return menu


def show_about_dialog(parent: QWidget) -> None:
    # IMPORTANT: do not use `exec()` (modal event loop). It can be fragile
    # under some test / CI environments and is unnecessary for an About dialog.
    dlg = AboutDialog(
        parent,
        content=AboutDialogContent(title=APP_NAME, body=_about_text()),
    )

    # Keep a reference on the parent so the dialog isn't garbage-collected
    # immediately after showing.
    setattr(parent, "_about_dialog", dlg)

    dlg.open()


def show_licence_dialog(parent: QWidget) -> None:
    from latencylab_ui.licence_dialog import LicenceDialog

    dlg = LicenceDialog(parent)
    setattr(parent, "_licence_dialog", dlg)
    dlg.open()


def show_main_licence_dialog(parent: QWidget) -> None:
    from latencylab_ui.main_licence_dialog import MainLicenceDialog

    dlg = MainLicenceDialog(parent)
    setattr(parent, "_main_licence_dialog", dlg)
    dlg.open()


def show_how_to_read_dialog(parent: QWidget) -> None:
    dlg = HowToReadDialog(parent)
    setattr(parent, "_how_to_read_dialog", dlg)
    dlg.open()


def _about_text() -> str:
    return about_html(
        python_version=platform.python_version(),
        pyside_version=getattr(PySide6, "__version__", "(unknown)"),
    )

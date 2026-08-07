from __future__ import annotations

from pathlib import Path


def _ensure_qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _menu_named(window, title: str):
    for action in window.menuBar().actions():
        if action.text() == title:
            return action.menu()
    return None


def test_every_bundled_example_gets_its_own_action() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.example_models import ExampleModel
    from latencylab_ui.main_window_menus import EXAMPLES_MENU_TITLE, build_examples_menu

    window = QMainWindow()
    opened: list[Path] = []
    examples = (
        ExampleModel(label="Alpha", path=Path("alpha.json")),
        ExampleModel(label="Beta", path=Path("beta.json")),
    )

    build_examples_menu(window, on_open_example=opened.append, examples=examples)

    menu = _menu_named(window, EXAMPLES_MENU_TITLE)
    assert menu is not None
    assert [a.text() for a in menu.actions()] == ["Alpha", "Beta"]

    window.deleteLater()


def test_each_action_opens_its_own_model_not_the_last_one() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.example_models import ExampleModel
    from latencylab_ui.main_window_menus import EXAMPLES_MENU_TITLE, build_examples_menu

    window = QMainWindow()
    opened: list[Path] = []
    examples = (
        ExampleModel(label="Alpha", path=Path("alpha.json")),
        ExampleModel(label="Beta", path=Path("beta.json")),
    )

    build_examples_menu(window, on_open_example=opened.append, examples=examples)

    menu = _menu_named(window, EXAMPLES_MENU_TITLE)
    assert menu is not None
    for action in menu.actions():
        action.trigger()

    # The late-binding closure bug would make both entries open beta.json.
    assert opened == [Path("alpha.json"), Path("beta.json")]

    window.deleteLater()


def test_an_empty_bundle_explains_itself_with_a_disabled_item() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.main_window_menus import (
        EXAMPLES_MENU_TITLE,
        NO_EXAMPLES_TEXT,
        build_examples_menu,
    )

    window = QMainWindow()
    opened: list[Path] = []

    build_examples_menu(window, on_open_example=opened.append, examples=())

    menu = _menu_named(window, EXAMPLES_MENU_TITLE)
    assert menu is not None
    actions = menu.actions()
    assert [a.text() for a in actions] == [NO_EXAMPLES_TEXT]
    # Disabled, so the focus ring skips it exactly as it skips every other
    # disabled control.
    assert actions[0].isEnabled() is False

    window.deleteLater()


def test_the_menu_falls_back_to_the_bundled_examples_on_disk() -> None:
    _ensure_qapp()

    from PySide6.QtWidgets import QMainWindow

    from latencylab_ui.main_window_menus import EXAMPLES_MENU_TITLE, build_examples_menu

    window = QMainWindow()
    opened: list[Path] = []

    build_examples_menu(window, on_open_example=opened.append)

    menu = _menu_named(window, EXAMPLES_MENU_TITLE)
    assert menu is not None
    assert "Checkout" in [a.text() for a in menu.actions()]

    window.deleteLater()


def test_the_main_window_loads_the_example_the_menu_asks_for() -> None:
    _ensure_qapp()

    from PySide6.QtCore import QObject, Signal

    from latencylab_ui.example_models import find_examples_dir
    from latencylab_ui.main_window import MainWindow
    from latencylab_ui.main_window_menus import EXAMPLES_MENU_TITLE

    class _Controller(QObject):
        started = Signal(int)
        succeeded = Signal(int, object)
        failed = Signal(int, str)
        cancelled = Signal(int, int)
        finished = Signal(int, float)

        def is_running(self) -> bool:
            return False

        def is_cancelled(self, run_token: int) -> bool:
            return False

        def active_token(self) -> int | None:
            return None

        def shutdown(self) -> None:
            return None

    window = MainWindow(run_controller=_Controller())

    menu = _menu_named(window, EXAMPLES_MENU_TITLE)
    assert menu is not None

    checkout = next(a for a in menu.actions() if a.text() == "Checkout")
    checkout.trigger()

    examples_dir = find_examples_dir()
    assert examples_dir is not None
    # The example loads through the ordinary load path, so the window ends up
    # holding a validated model rather than a load failure.
    assert window._loaded_model is not None
    assert window._loaded_model.path == examples_dir / "checkout.json"
    assert window._model_valid_label.text() == "OK"
    assert window._model_version_label.text() == "2"

    # Loading a model is the moment Run becomes the thing to press, so the
    # button says so. This is the same path the Open dialog takes, so proving
    # it here proves it for both.
    assert window._run_btn.isEnabled() is True
    assert window._run_flash.is_lit() is True

    window.close()
    window.deleteLater()

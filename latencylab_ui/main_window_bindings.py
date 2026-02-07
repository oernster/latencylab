from __future__ import annotations

from PySide6.QtCore import QObject

from latencylab_ui.focus_cycle import FocusCycleController
from latencylab_ui.theme_toggle import ThemeToggle


def connect_theme_toggle(
    *,
    theme_toggle: ThemeToggle,
    receiver: QObject,
    focus_cycle: FocusCycleController,
) -> None:
    """Connect ThemeToggle signals to MainWindow behaviors.

    `receiver` is the object that implements `_on_theme_changed(theme)`.
    """

    theme_toggle.theme_changed.connect(receiver._on_theme_changed)  # type: ignore[attr-defined]
    theme_toggle.focus_advance_requested.connect(
        lambda _btn: focus_cycle._advance(forward=True)  # noqa: SLF001
    )


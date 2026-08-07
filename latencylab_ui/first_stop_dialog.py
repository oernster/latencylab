from __future__ import annotations

"""The dialog base: opens already focused on its first usable control.

This is the deliberate OPPOSITE of the main window, which starts neutral with
nothing focused at all. A window is looked at before it is acted in, so lighting
a control up unasked there is noise. A dialog is not: it was opened on purpose,
to do the one thing it is for, so making the user press Tab before anything is
focused costs a keystroke and tells them nothing.

Escape and returning focus to the opener come free from QDialog and are not
re-implemented here; what Qt does not guarantee is which control the ring starts
on, which is all this adds.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget


class FirstStopDialog(QDialog):
    """A dialog whose first ring stop is focused the moment it is shown."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._first_stop_applied = False

    def first_stop(self) -> QWidget | None:
        """The control the first Tab press would have reached.

        Walked along the toolkit's OWN focus chain rather than over the child
        list, so the answer is exactly what Tab would have given rather than a
        second opinion about it. The seen-set is not optional: the chain is
        circular, so a dialog with nothing focusable would otherwise spin.

        Disabled, hidden and unfocusable controls are passed over, so a dialog
        whose leading control happens to be inert never opens focused on it.
        """

        widget = self.nextInFocusChain()
        seen: set[int] = set()
        while widget is not None and id(widget) not in seen:
            seen.add(id(widget))
            if (
                widget is not self
                and self.isAncestorOf(widget)
                and widget.isEnabled()
                and widget.isVisible()
                and bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
            ):
                return widget
            widget = widget.nextInFocusChain()
        return None

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._first_stop_applied:
            return
        self._first_stop_applied = True
        target = self.first_stop()
        if target is not None:
            # The tab focus reason, so it shows the same green ring a control
            # tabbed to would show rather than an unstyled one.
            target.setFocus(Qt.FocusReason.TabFocusReason)

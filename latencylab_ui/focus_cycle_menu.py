from __future__ import annotations

"""Menu-bar behaviour the toolkit does not provide.

Qt's menus answer Enter but not Space, and they answer the horizontal arrows by
walking between menu titles, which is the same thing the focus ring wants those
keys for. Every rule here is about resolving one of those two clashes, so they
are kept together and out of the traversal controller.
"""

from PySide6.QtWidgets import QApplication, QMainWindow, QMenu


def open_menu_under_title(window: QMainWindow) -> bool:
    """Space on a highlighted menu title: drop its menu.

    Qt gives a highlighted title nothing on Space at all, so without this the
    one key that activates everything else in the application silently does
    nothing on the menu bar.
    """

    bar = window.menuBar()
    action = bar.activeAction()
    if action is None:
        return False
    menu = action.menu()
    if menu is None:
        return False
    menu.popup(bar.mapToGlobal(bar.actionGeometry(action).bottomLeft()))
    return True


def trigger_highlighted_item(popup: QMenu) -> bool:
    """Space on a highlighted menu item: fire it.

    Qt's Windows styles leave `SH_Menu_SpaceActivatesItem` off, so Enter works
    here and Space does not. An item that opens a submenu is left alone: Space
    on it would close the menu without choosing anything.
    """

    action = popup.activeAction()
    if action is None or action.menu() is not None:
        return False
    popup.close()
    action.trigger()
    return True


def active_popup_menu() -> QMenu | None:
    """The open menu, if the active popup is one."""

    popup = QApplication.activePopupWidget()
    return popup if isinstance(popup, QMenu) else None


def should_yield_horizontal(popup: QMenu, *, forward: bool) -> bool:
    """Whether an open menu owns this horizontal arrow rather than the ring.

    Two cases, and only two. Right on an item that HAS a submenu opens it, and
    Left inside a submenu closes back to its parent item. Everywhere else the
    horizontal arrows keep their ring meaning and step between menu titles, so
    the ring is never trapped inside the menu bar.
    """

    if forward:
        action = popup.activeAction()
        return action is not None and action.menu() is not None
    return isinstance(popup.parentWidget(), QMenu)

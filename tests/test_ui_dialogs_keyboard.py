from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

from latencylab_ui.about_dialog import AboutDialog, AboutDialogContent
from latencylab_ui.about_text import CREDITED_DISTRIBUTIONS, about_html
from latencylab_ui.first_stop_dialog import FirstStopDialog
from latencylab_ui.how_to_read_dialog import HowToReadDialog
from latencylab_ui.licence_dialog import LicenceDialog
from latencylab_ui.main_licence_dialog import MainLicenceDialog

REPO_ROOT = Path(__file__).resolve().parents[1]

# A requirement line is `name>=1.2`, `name==1.2`, `name[extra]` or bare `name`.
_REQUIREMENT = re.compile(r"^([A-Za-z0-9._-]+)")

DIALOG_TYPES = (HowToReadDialog, LicenceDialog, MainLicenceDialog)


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def parent(app: QApplication) -> QWidget:
    widget = QWidget()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def _declared_distributions() -> set[str]:
    """Every third-party package this project asks pip to install."""

    found: set[str] = set()

    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (REPO_ROOT / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            match = _REQUIREMENT.match(line)
            if match:
                found.add(match.group(1).lower())

    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = pyproject["project"]
    groups = list(project.get("optional-dependencies", {}).values())
    for requirement in [*project.get("dependencies", []), *sum(groups, [])]:
        match = _REQUIREMENT.match(requirement.strip())
        if match:
            found.add(match.group(1).lower())
    return found


# ------------------------------------------------------------------- credits


def test_nothing_the_project_installs_goes_uncredited() -> None:
    """The credit list is pinned to the real dependency set, not to memory.

    Both licences LatencyLab ships under oblige it to say what it is built on,
    and a credits list that drifts from the truth is worse than none. Adding a
    dependency without a credit fails here rather than being noticed by nobody.
    """

    uncredited = _declared_distributions() - CREDITED_DISTRIBUTIONS
    assert not uncredited, f"add an About credit for: {sorted(uncredited)}"


def test_the_about_body_is_html_that_names_the_licences() -> None:
    body = about_html(python_version="3.13.0", pyside_version="6.7.0")

    assert body.startswith("<h2>")
    assert "GNU General Public License version 3" in body
    assert "GNU Lesser General Public License" in body
    assert "3.13.0" in body
    assert "6.7.0" in body


# --------------------------------------------------------------- first stop


@pytest.mark.parametrize("dialog_type", DIALOG_TYPES)
def test_a_dialog_opens_focused_on_its_first_stop(
    app: QApplication, parent: QWidget, dialog_type: type
) -> None:
    """The deliberate opposite of the main window, which starts neutral.

    The dialog was opened on purpose, to do the one thing it is for, so making
    the user press Tab before anything is focused costs a keystroke and tells
    them nothing.
    """

    dialog = dialog_type(parent)
    dialog.show()
    app.processEvents()

    focused = QApplication.focusWidget()
    assert focused is not None
    assert dialog.isAncestorOf(focused)
    assert focused is dialog.first_stop()

    dialog.close()
    app.processEvents()


def test_the_about_dialog_opens_focused_too(app: QApplication, parent: QWidget) -> None:
    dialog = AboutDialog(
        parent,
        content=AboutDialogContent(title="LatencyLab", body="<p>body</p>"),
    )
    dialog.show()
    app.processEvents()

    focused = QApplication.focusWidget()
    assert focused is not None
    assert dialog.isAncestorOf(focused)

    dialog.close()
    app.processEvents()


def test_the_first_stop_skips_a_leading_control_that_is_inert(
    app: QApplication, parent: QWidget
) -> None:
    """A dialog must never open focused on a control that cannot be used.

    Built rather than found: none of the shipped dialogs currently lead with a
    disabled control, and a rule only tested where it happens not to bite is a
    rule that has not been tested.
    """

    from PySide6.QtWidgets import QVBoxLayout

    dialog = FirstStopDialog(parent)
    layout = QVBoxLayout(dialog)

    dead = QPushButton("Disabled")
    dead.setEnabled(False)
    layout.addWidget(dead)

    live = QPushButton("Live")
    layout.addWidget(live)

    dialog.show()
    app.processEvents()

    assert dialog.first_stop() is live
    assert QApplication.focusWidget() is live

    dialog.close()
    app.processEvents()


def test_a_dialog_with_nothing_focusable_focuses_nothing(
    app: QApplication, parent: QWidget
) -> None:
    """It must not fail, and it must not pick something unusable either."""

    from PySide6.QtWidgets import QLabel, QVBoxLayout

    dialog = FirstStopDialog(parent)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("nothing to do here"))

    dialog.show()
    app.processEvents()

    assert dialog.first_stop() is None

    dialog.close()
    app.processEvents()


def test_showing_a_dialog_twice_does_not_re_grab_focus(
    app: QApplication, parent: QWidget
) -> None:
    """First-stop entry is about OPENING, not about every later show.

    Re-grabbing focus when a dialog is merely re-shown would yank the user off
    whatever they had tabbed to inside it.
    """

    from PySide6.QtWidgets import QVBoxLayout

    dialog = FirstStopDialog(parent)
    layout = QVBoxLayout(dialog)
    first = QPushButton("First")
    second = QPushButton("Second")
    layout.addWidget(first)
    layout.addWidget(second)

    dialog.show()
    app.processEvents()
    assert QApplication.focusWidget() is first

    second.setFocus()
    dialog.hide()
    dialog.show()
    app.processEvents()

    # What is asserted is that the base did not drag focus back to the first
    # stop. Where focus actually lands after a hide is Qt's business, and it
    # drops it entirely here, so "focus is still on second" is not available to
    # assert; "focus was not stolen back" is, and is the guarantee that matters.
    assert QApplication.focusWidget() is not first

    dialog.close()
    app.processEvents()


# ------------------------------------------------------------------- escape


@pytest.mark.parametrize("dialog_type", DIALOG_TYPES)
def test_escape_closes_every_dialog(
    app: QApplication, parent: QWidget, dialog_type: type
) -> None:
    from PySide6.QtTest import QTest

    dialog = dialog_type(parent)
    dialog.show()
    app.processEvents()
    assert dialog.isVisible()

    QTest.keyClick(dialog, Qt.Key_Escape, Qt.NoModifier)
    app.processEvents()

    assert not dialog.isVisible()
    assert dialog.result() == QDialog.DialogCode.Rejected

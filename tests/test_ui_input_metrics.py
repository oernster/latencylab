from __future__ import annotations

import json
from pathlib import Path

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.model_composer_dock import ModelComposerDock
from latencylab_ui.model_composer_load import load_raw_model
from latencylab_ui.theme import Theme, apply_theme

# Everything a person types or chooses in. They do the same job, so the
# stylesheet is the one place that decides how tall they stand.
INPUT_KINDS = (QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit)

THEMES = (Theme.DARK, Theme.LIGHT)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "checkout.json"

# Qt defers layout, and the offscreen platform does not propagate size hints,
# so geometry read straight after building a panel is whatever it was before
# the layout ran. Every measurement here is of the SETTLED state.
SETTLE_PASSES = 3


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _settle(app: QApplication, root: QWidget) -> None:
    for _ in range(SETTLE_PASSES):
        for widget in root.findChildren(QWidget):
            layout = widget.layout()
            if layout is not None:
                layout.activate()
        app.processEvents()


def _inputs(root: QWidget) -> list[QWidget]:
    found: list[QWidget] = []
    for kind in INPUT_KINDS:
        found.extend(root.findChildren(kind))
    return found


def _nested_in_an_input(widget: QWidget) -> bool:
    """An inner field of a spin box or an editable combo, not a field itself."""

    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, (QAbstractSpinBox, QComboBox)):
            return True
        parent = parent.parentWidget()
    return False


def _loaded_composer(app: QApplication) -> tuple[QMainWindow, ModelComposerDock]:
    window = QMainWindow()
    dock = ModelComposerDock(window)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    window.resize(1200, 900)
    window.show()
    with EXAMPLE.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    load_raw_model(dock, raw, model_name="checkout")
    _settle(app, dock)
    return window, dock


@pytest.mark.parametrize("theme", THEMES)
def test_no_input_is_drawn_smaller_than_it_asks_for(
    app: QApplication, theme: Theme
) -> None:
    """A control given less room than its own minimum has part of itself
    outside its own rectangle, which is how a spin box lost its DOWN button and
    the Params arrows came out squashed."""

    apply_theme(app, theme)
    window, dock = _loaded_composer(app)

    squeezed = [
        (type(w).__name__, w.height(), w.minimumSizeHint().height())
        for w in _inputs(dock)
        if w.isVisibleTo(dock)
        and not _nested_in_an_input(w)
        and w.height() < w.minimumSizeHint().height()
    ]

    assert squeezed == []

    window.close()
    window.deleteLater()


@pytest.mark.parametrize("theme", THEMES)
def test_the_input_rule_reaches_every_kind_of_input(
    app: QApplication, theme: Theme
) -> None:
    """A Qt type selector matches a class and its SUBCLASSES, and
    QDoubleSpinBox is a SIBLING of QSpinBox rather than a subclass, so a rule
    written for the one silently missed the other. QLineEdit was not named at
    all. Measured in the composer: 51px, 19px and 22px for three controls doing
    the same job.

    The reference is the combo box, which the rule always did reach. A spin box
    stands a few pixels taller because it carries two arrow buttons and Qt
    prices those in, so the two SPIN kinds are compared with each other and the
    plain fields with each other.
    """

    apply_theme(app, theme)

    holder = QWidget()
    layout = QVBoxLayout(holder)
    combo = QComboBox()
    line = QLineEdit()
    spin = QSpinBox()
    double = QDoubleSpinBox()
    for control in (combo, line, spin, double):
        layout.addWidget(control)
    holder.show()
    _settle(app, holder)

    assert double.height() == spin.height()
    assert line.height() == combo.height()
    assert spin.height() >= combo.height()

    holder.close()
    holder.deleteLater()


@pytest.mark.parametrize("theme", THEMES)
def test_the_field_inside_a_spin_box_is_not_a_field_of_its_own(
    app: QApplication, theme: Theme
) -> None:
    """The input rule reaches inside these controls, so without a reset the
    inner field would carry the outer control's border, padding and minimum on
    top of the outer control's own."""

    apply_theme(app, theme)

    spin = QSpinBox()
    spin.show()
    _settle(app, spin)

    inner = spin.findChild(QLineEdit)
    assert inner is not None
    assert inner.height() < spin.height()
    assert spin.height() == spin.minimumSizeHint().height()

    spin.close()
    spin.deleteLater()

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.model_composer_widgets import DurationDistEditor
from latencylab_ui.qt_style_helpers import harden_combobox_popup


class _TaskCard(QFrame):
    changed = Signal()
    remove_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Row 1: name + context + remove.
        row1 = QWidget(self)
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(0, 0, 0, 0)
        r1.setSpacing(8)

        r1.addWidget(QLabel("Task"))
        self.name_edit = QLineEdit(row1)
        r1.addWidget(self.name_edit, 2)

        r1.addWidget(QLabel("Context"))
        self.context_combo = QComboBox(row1)
        harden_combobox_popup(self.context_combo)
        r1.addWidget(self.context_combo, 1)

        rm_btn = QPushButton("Remove", row1)
        rm_btn.clicked.connect(self.remove_requested)
        r1.addWidget(rm_btn)

        root.addWidget(row1)

        # Row 2: duration dist editor.
        self.duration = DurationDistEditor(self)
        root.addWidget(self.duration)

        # Row 3: emits.
        row3 = QWidget(self)
        r3 = QHBoxLayout(row3)
        r3.setContentsMargins(0, 0, 0, 0)
        r3.setSpacing(8)
        r3.addWidget(QLabel("Emits"))
        self.emits_edit = QLineEdit(row3)
        self.emits_edit.setPlaceholderText("comma-separated events")
        r3.addWidget(self.emits_edit, 1)
        root.addWidget(row3)

        # v2-only: category.
        row4 = QWidget(self)
        r4 = QHBoxLayout(row4)
        r4.setContentsMargins(0, 0, 0, 0)
        r4.setSpacing(8)
        self._category_label = QLabel("Category (v2)")
        r4.addWidget(self._category_label)
        self.category_edit = QLineEdit(row4)
        r4.addWidget(self.category_edit, 1)
        root.addWidget(row4)

        # Wiring.
        self.name_edit.textChanged.connect(self.changed)
        self.context_combo.currentTextChanged.connect(self.changed)
        self.duration.changed.connect(self.changed)
        self.emits_edit.textChanged.connect(self.changed)
        self.category_edit.textChanged.connect(self.changed)

    def set_context_names(self, names: Sequence[str]) -> None:
        prev = self.context_combo.currentText()
        self.context_combo.blockSignals(True)
        self.context_combo.clear()
        self.context_combo.addItems(list(names))
        if prev and prev in names:
            self.context_combo.setCurrentText(prev)
        self.context_combo.blockSignals(False)

    def set_version(self, version: int) -> None:
        is_v1 = int(version) == 1
        self._category_label.setVisible(not is_v1)
        self.category_edit.setVisible(not is_v1)

    def to_task_obj(self, *, version: int) -> tuple[str, dict[str, object]] | None:
        name = self.name_edit.text().strip()
        if not name:
            return None

        ctx = self.context_combo.currentText().strip()
        duration = self.duration.to_obj()
        emits = [e.strip() for e in self.emits_edit.text().split(",") if e.strip()]

        obj: dict[str, object] = {
            "context": ctx,
            "duration_ms": duration,
            "emit": emits,
        }

        if int(version) >= 2:
            cat = self.category_edit.text().strip()
            if cat:
                obj["meta"] = {"category": cat, "tags": [], "labels": {}}

        return name, obj


class TasksEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._context_names: list[str] = ["ui"]
        self._version = 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._cards_col = QVBoxLayout()
        self._cards_col.setContentsMargins(0, 0, 0, 0)
        self._cards_col.setSpacing(10)
        layout.addLayout(self._cards_col, 1)

        btn_row = QWidget(self)
        btns = QHBoxLayout(btn_row)
        btns.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("Add task", btn_row)
        add_btn.clicked.connect(self._on_add)
        btns.addWidget(add_btn)
        btns.addStretch(1)
        layout.addWidget(btn_row)

    def set_context_names(self, names: Sequence[str]) -> None:
        self._context_names = list(names) or ["ui"]
        for c in self._iter_cards():
            c.set_context_names(self._context_names)

    def set_version(self, version: int) -> None:
        self._version = int(version)
        for c in self._iter_cards():
            c.set_version(self._version)

    def task_names(self) -> list[str]:
        names: list[str] = []
        for c in self._iter_cards():
            nm = c.name_edit.text().strip()
            if nm:
                names.append(nm)
        return names

    def to_tasks_dict(self, *, version: int) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for c in self._iter_cards():
            item = c.to_task_obj(version=version)
            if item is None:
                continue
            name, obj = item
            out[name] = obj
        return out

    def _iter_cards(self) -> list[_TaskCard]:
        cards: list[_TaskCard] = []
        for i in range(self._cards_col.count()):
            w = self._cards_col.itemAt(i).widget()
            if isinstance(w, _TaskCard):
                cards.append(w)
        return cards

    def _on_add(self) -> None:
        idx = len(self._iter_cards()) + 1
        card = _TaskCard(self)
        card.name_edit.setText(f"task_{idx}")
        card.set_context_names(self._context_names)
        card.set_version(self._version)
        card.changed.connect(self.changed)
        card.remove_requested.connect(lambda: self._remove_card(card))
        self._cards_col.addWidget(card)
        self.changed.emit()

    def _remove_card(self, card: _TaskCard) -> None:
        card.setParent(None)
        card.deleteLater()
        self.changed.emit()


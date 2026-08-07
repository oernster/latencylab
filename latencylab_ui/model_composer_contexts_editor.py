from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.qt_style_helpers import size_table_to_rows, stretch_table_columns

# The column that takes the slack. A context name has no natural width and is
# the part that was being clipped; a concurrency is a small number and needs
# only as much room as it prints in.
NAME_COLUMN = 0


class ContextsEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Name", "Concurrency"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        # The table is ONE ring stop, walked with the vertical arrows and left
        # in a single Tab. Qt's default is on, which spends a Tab press per CELL
        # and turns a two-column table into a row of dead stops.
        self.table.setTabKeyNavigation(False)

        # UX: Clicking the spinbox arrows (Concurrency) should not paint a loud
        # selection highlight across the whole row.
        #
        # We still keep row selection functional for Remove, but render it
        # visually neutral.
        self.table.setStyleSheet(
            "QTableView::item:selected { background: transparent; color: palette(text); }\n"
            "QTableView::item:focus { outline: none; }\n"
            "QTableView { selection-background-color: transparent; selection-color: palette(text); }"
        )
        stretch_table_columns(self.table, NAME_COLUMN)
        layout.addWidget(self.table)

        btn_row = QWidget(self)
        btns = QHBoxLayout(btn_row)
        btns.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("Add context", btn_row)
        rm_btn = QPushButton("Remove context", btn_row)
        add_btn.clicked.connect(self._on_add)
        rm_btn.clicked.connect(self._on_remove)
        btns.addWidget(add_btn)
        btns.addWidget(rm_btn)
        btns.addStretch(1)
        layout.addWidget(btn_row)

        # Bound to the model rather than called from each mutator. The height
        # is a fact about the row count, so it is derived from the row count
        # changing rather than from every caller remembering to say so.
        model = self.table.model()
        model.rowsInserted.connect(self._fit_to_rows)
        model.rowsRemoved.connect(self._fit_to_rows)
        model.modelReset.connect(self._fit_to_rows)

        self._ensure_default()
        self._fit_to_rows()

    def _fit_to_rows(self, *_args: object) -> None:
        size_table_to_rows(self.table)

    def _ensure_default(self) -> None:
        if self.table.rowCount() > 0:
            return
        self.table.insertRow(0)
        self.table.setItem(0, 0, QTableWidgetItem("ui"))
        sp = QSpinBox(self.table)
        sp.setRange(1, 1_000_000)
        sp.setValue(1)
        sp.valueChanged.connect(self.changed)
        self.table.setCellWidget(0, 1, sp)
        self.changed.emit()

    def _on_add(self) -> None:
        self._append_row(f"ctx_{self.table.rowCount() + 1}", 1)
        self.changed.emit()

    def _append_row(self, name: str, concurrency: int) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        sp = QSpinBox(self.table)
        sp.setRange(1, 1_000_000)
        sp.setValue(max(1, int(concurrency)))
        sp.valueChanged.connect(self.changed)
        self.table.setCellWidget(r, 1, sp)

    def set_contexts(self, contexts: dict[str, dict[str, object]]) -> None:
        """Replace the table with the contexts of a model being edited.

        Sorted by name, because a dict from parsed JSON carries the file's
        order and the table is the user's view of a set rather than a
        sequence: two loads of the same model must not present differently.
        """

        self.table.setRowCount(0)
        for name in sorted(contexts):
            raw = contexts.get(name) or {}
            self._append_row(name, int(raw.get("concurrency", 1) or 1))
        self._ensure_default()
        self.changed.emit()

    def _on_remove(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self.changed.emit()

    def context_names(self) -> list[str]:
        names = sorted(self.to_contexts_dict().keys())
        return names or ["ui"]

    def to_contexts_dict(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            name = (name_item.text() if name_item else "").strip()
            if not name:
                continue
            sp = self.table.cellWidget(r, 1)
            conc = int(sp.value()) if isinstance(sp, QSpinBox) else 1
            out[name] = {"concurrency": max(1, conc), "policy": "fifo"}
        return out

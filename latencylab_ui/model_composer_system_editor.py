from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QWidget

from latencylab_ui.qt_style_helpers import harden_combobox_popup


class SystemEditor(QWidget):
    changed = Signal()
    version_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.model_name_edit = QLineEdit(self)

        self.version_combo = QComboBox(self)
        self.version_combo.addItems(["1", "2"])
        harden_combobox_popup(self.version_combo)

        self.entry_event_edit = QLineEdit(self)

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Model name", self.model_name_edit)
        form.addRow("Schema version", self.version_combo)
        form.addRow("Entry event", self.entry_event_edit)

        self.model_name_edit.textChanged.connect(self.changed)
        self.entry_event_edit.textChanged.connect(self.changed)
        self.version_combo.currentTextChanged.connect(self._on_version_changed)

    def _on_version_changed(self, txt: str) -> None:
        try:
            v = int(txt)
        except Exception:  # noqa: BLE001
            v = 2
        self.version_changed.emit(v)
        self.changed.emit()

    def set_values(self, *, model_name: str, version: int, entry_event: str) -> None:
        self.model_name_edit.setText(model_name)
        self.version_combo.setCurrentText(str(int(version)))
        self.entry_event_edit.setText(entry_event)

    def get_model_name(self) -> str:
        return self.model_name_edit.text().strip() or "model"

    def get_version(self) -> int:
        try:
            return int(self.version_combo.currentText())
        except Exception:  # noqa: BLE001
            return 2

    def get_entry_event(self) -> str:
        return self.entry_event_edit.text().strip() or "start"


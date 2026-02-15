from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QStackedWidget,
    QWidget,
)

from latencylab_ui.qt_style_helpers import harden_combobox_popup


class DurationDistEditor(QWidget):
    """Small, reusable editor for DurationDist-like objects."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._dist = QComboBox(self)
        self._dist.addItems(["fixed", "normal", "lognormal"])
        self._dist.currentIndexChanged.connect(self.changed)
        harden_combobox_popup(self._dist)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_fixed())
        self._stack.addWidget(self._build_normal())
        self._stack.addWidget(self._build_lognormal())
        self._dist.currentTextChanged.connect(self._on_dist_changed)

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.addRow("Dist", self._dist)
        form.addRow("Params", self._stack)

        self._on_dist_changed(self._dist.currentText())

    def _on_dist_changed(self, dist: str) -> None:
        idx = {"fixed": 0, "normal": 1, "lognormal": 2}.get(dist, 0)
        self._stack.setCurrentIndex(idx)
        self.changed.emit()

    @staticmethod
    def _spin(parent: QWidget) -> QDoubleSpinBox:
        sp = QDoubleSpinBox(parent)
        sp.setDecimals(6)
        sp.setRange(-1e12, 1e12)
        sp.setSingleStep(1.0)
        return sp

    def _build_fixed(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._fixed_value = self._spin(w)
        self._fixed_value.setRange(0.0, 1e12)
        self._fixed_value.valueChanged.connect(self.changed)
        form.addRow("value", self._fixed_value)
        return w

    def _build_normal(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._normal_mean = self._spin(w)
        self._normal_std = self._spin(w)
        self._normal_std.setRange(0.0, 1e12)
        self._normal_mean.valueChanged.connect(self.changed)
        self._normal_std.valueChanged.connect(self.changed)
        form.addRow("mean", self._normal_mean)
        form.addRow("std", self._normal_std)
        return w

    def _build_lognormal(self) -> QWidget:
        w = QWidget(self)
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._log_mu = self._spin(w)
        self._log_sigma = self._spin(w)
        self._log_sigma.setRange(0.0, 1e12)
        self._log_mu.valueChanged.connect(self.changed)
        self._log_sigma.valueChanged.connect(self.changed)
        form.addRow("mu", self._log_mu)
        form.addRow("sigma", self._log_sigma)
        return w

    def to_obj(self) -> dict[str, float | str]:
        dist = self._dist.currentText()
        if dist == "fixed":
            return {"dist": "fixed", "value": float(self._fixed_value.value())}
        if dist == "normal":
            return {
                "dist": "normal",
                "mean": float(self._normal_mean.value()),
                "std": float(self._normal_std.value()),
            }
        return {
            "dist": "lognormal",
            "mu": float(self._log_mu.value()),
            "sigma": float(self._log_sigma.value()),
        }

    def set_from_obj(self, obj: dict) -> None:
        dist = str((obj or {}).get("dist", "fixed"))
        self._dist.setCurrentText(dist)
        if dist == "fixed":
            self._fixed_value.setValue(float((obj or {}).get("value", 0.0)))
        elif dist == "normal":
            self._normal_mean.setValue(float((obj or {}).get("mean", 0.0)))
            self._normal_std.setValue(float((obj or {}).get("std", 0.0)))
        elif dist == "lognormal":
            self._log_mu.setValue(float((obj or {}).get("mu", 0.0)))
            self._log_sigma.setValue(float((obj or {}).get("sigma", 1.0)))


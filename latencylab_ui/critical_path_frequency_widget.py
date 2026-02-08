from __future__ import annotations

"""Critical path frequency UI widget (scrollable, deterministic).

This replaces the earlier painted "all-in-one" histogram so long labels do not
collide with bars. The UI instead shows compact identifiers (Path #X) and relies
on tooltips for full path traceability.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.distributions_agg import CriticalPathBar


@dataclass(frozen=True)
class _RowModel:
    label_text: str
    tooltip_text: str
    count: int
    ratio: float


class CriticalPathFrequencyWidget(QWidget):
    """Scrollable list of Top-N critical paths + optional long-tail bucket."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("critical_path_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._content = QWidget(self._scroll)
        self._content.setObjectName("critical_path_scroll_content")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._scroll.setWidget(self._content)

        root_layout.addWidget(self._scroll, 1)

        # Exposed for tests (stable ordering).
        self._rows: list[_FrequencyRow] = []

    def set_data(self, bars: list[CriticalPathBar]) -> None:
        # Clear previous rows deterministically.
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        # Remove any leftover layout items.
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                # Layout-only items (eg stretches/spacers) need no explicit cleanup.
                continue

        if not bars:
            empty = QLabel("No critical-path data", self._content)
            empty.setObjectName("critical_path_empty")
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch(1)
            self.update()
            return

        max_count = max((b.count for b in bars), default=1)
        max_count = max(1, int(max_count))

        models: list[_RowModel] = []
        path_idx = 1
        for b in bars:
            if b.label_full == "Other (long tail)":
                label_text = "Other (long tail)"
                tooltip_text = f"Other (long tail): {b.count}"
            else:
                label_text = f"Path #{path_idx}"
                tooltip_text = f"{b.count}  {b.label_full}"
                path_idx += 1

            ratio = float(b.count) / float(max_count)
            ratio = max(0.0, min(1.0, ratio))
            models.append(
                _RowModel(
                    label_text=label_text,
                    tooltip_text=tooltip_text,
                    count=int(b.count),
                    ratio=ratio,
                )
            )

        for i, m in enumerate(models, start=1):
            row = _FrequencyRow(self._content, model=m)
            row.setObjectName(f"critical_path_row_{i:02d}")
            self._rows.append(row)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch(1)
        self.update()


class _FrequencyRow(QWidget):
    _ROW_H = 28

    def __init__(self, parent: QWidget, *, model: _RowModel) -> None:
        super().__init__(parent)
        self.setFixedHeight(self._ROW_H)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(model.label_text, self)
        label.setObjectName("critical_path_label")
        label.setToolTip(model.tooltip_text)
        label.setMinimumWidth(86)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label, 0)

        bar = _BarWidget(self, ratio=model.ratio)
        bar.setObjectName("critical_path_bar")
        bar.setToolTip(model.tooltip_text)
        layout.addWidget(bar, 1)

        count = QLabel(str(model.count), self)
        count.setObjectName("critical_path_count")
        count.setToolTip(model.tooltip_text)
        count.setMinimumWidth(40)
        count.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(count, 0)

        # Ensure hovering any part of the row gives the same answer.
        self.setToolTip(model.tooltip_text)


class _BarWidget(QWidget):
    def __init__(self, parent: QWidget, *, ratio: float) -> None:
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, float(ratio)))
        self.setMinimumHeight(_FrequencyRow._ROW_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)

        rect = self.rect()
        p.fillRect(rect, self.palette().base())

        fill_w = int(round(rect.width() * self._ratio))
        if fill_w <= 0:
            return

        bar_color = QColor(self.palette().text().color())
        bar_color.setAlpha(80)
        p.fillRect(rect.adjusted(0, 6, -(rect.width() - fill_w), -6), bar_color)


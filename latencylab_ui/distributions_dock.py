from __future__ import annotations

"""Distributions / Histogram dock (v1).

UI principles:
- Non-modal, dockable inspection panel.
- Deterministic rendering: no animation, no interpolation beyond binning.
- Values trace back to `RunOutputs` and `Summary.txt`.
"""

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QDockWidget,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from latencylab_ui.distributions_agg import (
    CriticalPathBar,
    HistogramBin,
    critical_path_frequency,
    freedman_diaconis_bins,
)
from latencylab_ui.run_controller import RunOutputs
from latencylab_ui.critical_path_frequency_widget import CriticalPathFrequencyWidget


@dataclass(frozen=True)
class _Marker:
    label: str
    value: float


class DistributionsDock(QDockWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("distributions_dock")
        self.setWindowTitle("Distributions")

        # Ensure enough horizontal space for marker labels and long critical-path
        # prefixes. Users can still resize the dock narrower if they want.
        self.setMinimumWidth(520)

        # Dockable + closeable by design.
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        makespan_box = QGroupBox("Makespan distribution")
        makespan_layout = QVBoxLayout(makespan_box)
        self._makespan_chart = _MakespanHistogramWidget(makespan_box)
        self._makespan_chart.setMinimumHeight(180)
        makespan_layout.addWidget(self._makespan_chart)

        makespan_note = QLabel(
            "Bin width uses the Freedman–Diaconis rule computed from observed makespan values."
        )
        makespan_note.setWordWrap(True)
        makespan_layout.addWidget(makespan_note)

        cp_box = QGroupBox("Critical path frequency")
        cp_layout = QVBoxLayout(cp_box)
        hint = QLabel("Hover a Path # label to identify the full path")
        hint.setWordWrap(True)
        cp_layout.addWidget(hint)

        self._cp_list = CriticalPathFrequencyWidget(cp_box)
        self._cp_list.setMinimumHeight(220)
        cp_layout.addWidget(self._cp_list, 1)

        hint_row = QWidget(cp_box)
        hint_layout = QHBoxLayout(hint_row)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        hint_layout.addWidget(QLabel("Top 10 paths shown; remaining paths are aggregated as long tail."))
        hint_layout.addStretch(1)
        cp_layout.addWidget(hint_row)

        root_layout.addWidget(makespan_box)
        root_layout.addWidget(cp_box, 1)

        self.setWidget(root)

    def render(self, outputs: RunOutputs) -> None:
        ok = [r for r in outputs.runs if not r.failed]
        makespans = [r.makespan_ms for r in ok]
        bins = freedman_diaconis_bins(makespans)

        p = (
            outputs.summary.get("latency_ms", {})
            .get("makespan", {})
        )

        markers: list[_Marker] = []
        for k in ("p50", "p90", "p95", "p99"):
            v = p.get(k)
            if isinstance(v, (int, float)):
                markers.append(_Marker(label=f"{k} = {v}", value=float(v)))

        self._makespan_chart.set_data(bins=bins, markers=markers)

        bars = critical_path_frequency(outputs.runs, top_n=10)
        self._cp_list.set_data(bars)


class _MakespanHistogramWidget(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._bins: list[HistogramBin] = []
        self._markers: list[_Marker] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, *, bins: list[HistogramBin], markers: list[_Marker]) -> None:
        self._bins = list(bins)
        self._markers = list(markers)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)

        rect = self.rect()
        p.fillRect(rect, self.palette().base())

        if not self._bins:
            self._draw_empty(p, rect, text="No makespan data")
            return

        fm = QFontMetrics(self.font())

        # Label/legend layout (deterministic):
        # - A numeric marker row (1..N) aligned under each percentile x-position.
        # - A vertical legend list mapping numbers to labels (e.g., "1) p50 = ...").
        num_row_h = fm.height() + 4
        legend_rows = max(1, len(self._markers))
        legend_h = (legend_rows * fm.height()) + 6
        label_band_h = num_row_h + legend_h

        plot = QRect(rect)
        plot.adjust(8, 8, -8, -(label_band_h + 8))

        max_count = max((b.count for b in self._bins), default=0)
        max_count = max(1, max_count)

        # Bars.
        bar_color = QColor(self.palette().text().color())
        bar_color.setAlpha(80)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bar_color)

        n = len(self._bins)
        bar_w = max(1, int(plot.width() / max(1, n)))
        for i, b in enumerate(self._bins):
            h = int(round((b.count / max_count) * plot.height()))
            x = plot.left() + i * bar_w
            y = plot.bottom() - h
            p.drawRect(QRect(x, y, bar_w - 1, h))

        # Marker lines.
        data_lo = self._bins[0].lo
        data_hi = self._bins[-1].hi
        span = max(1e-9, data_hi - data_lo)

        # Percentile marker pen: red, deterministic.
        marker_pen = QPen(QColor(220, 60, 60))
        marker_pen.setWidth(1)
        p.setPen(marker_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Marker lines and label layout.
        label_area = QRect(
            rect.left() + 8,
            plot.bottom() + 2,
            rect.width() - 16,
            label_band_h,
        )
        num_row = QRect(label_area.left(), label_area.top(), label_area.width(), num_row_h)
        legend_area = QRect(
            label_area.left(),
            num_row.bottom() + 1,
            label_area.width(),
            label_area.bottom() - num_row.bottom() - 1,
        )

        marker_xs: list[tuple[_Marker, int]] = []
        # Keep deterministic order: as provided (p50, p90, p95, p99).
        for m in self._markers:
            x = plot.left() + int(round(((m.value - data_lo) / span) * plot.width()))
            x = max(plot.left(), min(plot.right(), x))
            marker_xs.append((m, x))

        # Marker lines stay within the plot area.
        for _idx, (_m, x) in enumerate(marker_xs, start=1):
            p.drawLine(x, plot.top(), x, plot.bottom())

        # Numeric markers under the plot.
        p.setPen(marker_pen)
        for idx, (_m, x_center) in enumerate(marker_xs, start=1):
            txt = str(idx)
            w = fm.horizontalAdvance(txt)
            x_left = max(num_row.left(), min(num_row.right() - w, x_center - int(w / 2)))
            y = num_row.top() + 2 + fm.ascent()
            p.drawText(QPoint(x_left, y), txt)

        # Vertical legend list.
        p.setPen(QPen(self.palette().text().color()))
        for idx, (m, _x) in enumerate(marker_xs, start=1):
            line = f"{idx}) {m.label}"
            y = legend_area.top() + 2 + ((idx - 1) * fm.height()) + fm.ascent()
            p.drawText(QPoint(legend_area.left(), y), line)

    # Previous label-placement helper removed; replaced by numeric marker row + legend list.

    @staticmethod
    def _draw_empty(p: QPainter, rect: QRect, *, text: str) -> None:
        # NOTE: use a deterministic foreground color; avoid relying on QPaintDevice palette.
        p.setPen(QPen(Qt.GlobalColor.black))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


### NOTE: Critical path frequency rendering is implemented by
### [`latencylab_ui.critical_path_frequency_widget.CriticalPathFrequencyWidget`](latencylab_ui/critical_path_frequency_widget.py:39)


from __future__ import annotations

import pytest

from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
)

from latencylab_ui.model_composer_contexts_editor import NAME_COLUMN, ContextsEditor
from latencylab_ui.qt_style_helpers import (
    MAX_VISIBLE_TABLE_ROWS,
    fit_rows_to_contents,
    size_table_to_rows,
    stretch_table_columns,
)

# The themed inputs carry a min-height, padding and a border, which together
# come to more than Qt's default row height. This is that rule in miniature, so
# the test states the condition rather than depending on the whole stylesheet.
TALL_INPUT_QSS = "QSpinBox { min-height: 32px; padding: 6px 8px; border: 2px solid; }"

# A count comfortably past the cap, so the capped case is unambiguous.
OVER_THE_CAP = MAX_VISIBLE_TABLE_ROWS * 2


@pytest.fixture()
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _table(rows: int, columns: int = 2) -> QTableWidget:
    table = QTableWidget(rows, columns)
    for row in range(rows):
        table.setItem(row, 0, QTableWidgetItem(f"context_{row}"))
    table.show()
    return table


def _chrome(table: QTableWidget) -> int:
    return table.horizontalHeader().sizeHint().height() + 2 * table.frameWidth()


def test_a_table_is_exactly_as_tall_as_the_rows_it_holds(app: QApplication) -> None:
    """Qt's own hint is a constant that has never looked at the model, so a
    short table reserved the same space as a long one."""

    for rows in (1, 2, 4):
        table = _table(rows)
        size_table_to_rows(table)
        app.processEvents()

        expected = sum(table.rowHeight(r) for r in range(rows)) + _chrome(table)
        assert table.height() == expected

        table.close()
        table.deleteLater()


def test_a_long_table_stops_at_the_cap(app: QApplication) -> None:
    """Past the cap it would take the whole panel and push everything below it
    out of reach, which is worse than a short scroll inside the table."""

    table = _table(OVER_THE_CAP)
    size_table_to_rows(table)
    app.processEvents()

    capped = sum(table.rowHeight(r) for r in range(MAX_VISIBLE_TABLE_ROWS)) + _chrome(
        table
    )
    assert table.height() == capped
    assert table.verticalScrollBar().maximum() > 0

    table.close()
    table.deleteLater()


def test_an_empty_table_is_just_its_header(app: QApplication) -> None:
    table = _table(0)
    size_table_to_rows(table)

    assert table.height() == _chrome(table)

    table.close()
    table.deleteLater()


def test_the_named_column_takes_the_slack(app: QApplication) -> None:
    """A fixed column width clipped a long name inside its cell while the room
    it needed sat empty further along the same row."""

    table = _table(3)
    stretch_table_columns(table, NAME_COLUMN)
    table.resize(400, 200)
    app.processEvents()

    header = table.horizontalHeader()
    assert header.sectionResizeMode(NAME_COLUMN) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
    assert (
        sum(table.columnWidth(c) for c in range(table.columnCount()))
        == table.viewport().width()
    )

    table.close()
    table.deleteLater()


def _table_with_a_tall_control(rows: int) -> tuple[QTableWidget, list[QSpinBox]]:
    table = QTableWidget(rows, 2)
    spins = []
    for row in range(rows):
        table.setItem(row, 0, QTableWidgetItem(f"context_{row}"))
        spin = QSpinBox()
        spin.setStyleSheet(TALL_INPUT_QSS)
        table.setCellWidget(row, 1, spin)
        spins.append(spin)
    table.show()
    return table, spins


def test_a_row_is_as_tall_as_the_control_standing_in_it(app: QApplication) -> None:
    """The reported fault: a spin box asking for more than the default row
    height had its lower half, including the DOWN button, drawn outside the row
    and never painted, and its number then sat against the bottom of what was
    left, which is the same fault seen as bad alignment."""

    table, spins = _table_with_a_tall_control(3)
    app.processEvents()
    wanted = spins[0].minimumSizeHint().height()
    assert wanted > table.verticalHeader().defaultSectionSize()

    fit_rows_to_contents(table)
    size_table_to_rows(table)
    app.processEvents()

    for spin in spins:
        assert spin.height() >= wanted

    table.close()
    table.deleteLater()


def test_the_table_counts_the_height_a_row_will_take(app: QApplication) -> None:
    """A header on ResizeToContents recalculates lazily, so measuring the table
    straight after filling a row used to leave it short by whatever Qt had not
    got round to yet."""

    table, _spins = _table_with_a_tall_control(2)
    fit_rows_to_contents(table)
    size_table_to_rows(table)

    # Deliberately NOT flushed: the height has to be right before Qt catches up.
    expected = sum(table.sizeHintForRow(r) for r in range(2)) + _chrome(table)
    assert table.height() == expected

    app.processEvents()
    assert table.height() == expected

    table.close()
    table.deleteLater()


def test_the_contexts_table_follows_its_own_row_count(app: QApplication) -> None:
    """The height is a fact about the contents, so it is derived from the row
    count changing rather than from every caller remembering to say so."""

    editor = ContextsEditor()
    editor.show()
    app.processEvents()

    one_row = editor.table.height()

    editor._on_add()
    app.processEvents()
    two_rows = editor.table.height()
    assert two_rows > one_row

    editor.set_contexts({f"ctx_{i}": {"concurrency": 1} for i in range(OVER_THE_CAP)})
    app.processEvents()
    assert editor.table.rowCount() == OVER_THE_CAP
    capped = editor.table.height()
    assert capped < sum(
        editor.table.rowHeight(r) for r in range(OVER_THE_CAP)
    ) + _chrome(editor.table)

    editor.table.selectRow(0)
    editor._on_remove()
    app.processEvents()
    assert editor.table.height() == capped

    editor.set_contexts({"ui": {"concurrency": 1}})
    app.processEvents()
    assert editor.table.height() == one_row

    editor.close()
    editor.deleteLater()

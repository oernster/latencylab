from __future__ import annotations


def test_harden_combobox_popup_handles_missing_view_gracefully(monkeypatch) -> None:
    """Cover the `view is None` early-return branch."""

    from latencylab_ui.qt_style_helpers import harden_combobox_popup

    class _Combo:
        def setEditable(self, _b):
            return None

        def setInsertPolicy(self, _p):
            return None

        def setSizeAdjustPolicy(self, _p):
            return None

        def setMinimumHeight(self, _h):
            return None

        def view(self):
            return None

    harden_combobox_popup(_Combo())  # type: ignore[arg-type]


def test_apply_combo_model_roles_handles_model_none() -> None:
    """Cover the `model is None` early return."""

    import latencylab_ui.qt_style_helpers as qsh

    class _Combo:
        def model(self):
            return None

    qsh._apply_combo_model_roles(_Combo())  # type: ignore[arg-type]


def test_apply_combo_model_roles_handles_rowcount_exception(monkeypatch) -> None:
    """Cover the `rowCount()` exception branch."""

    import latencylab_ui.qt_style_helpers as qsh

    class _BadModel:
        def rowCount(self):
            raise RuntimeError("boom")

    class _Combo:
        def model(self):
            return _BadModel()

    qsh._apply_combo_model_roles(_Combo())  # type: ignore[arg-type]


def test_apply_combo_model_roles_handles_setdata_exception() -> None:
    """Cover the `setData()` exception branch."""

    import latencylab_ui.qt_style_helpers as qsh

    class _Model:
        def rowCount(self):
            return 1

        def index(self, *_a, **_k):
            return object()

        def setData(self, *_a, **_k):  # noqa: N802
            raise RuntimeError("nope")

    class _Combo:
        def model(self):
            return _Model()

        def palette(self):
            # Use a real palette from a real QComboBox.
            from PySide6.QtWidgets import QApplication, QComboBox

            _ = QApplication.instance() or QApplication([])
            return QComboBox().palette()

        def modelColumn(self):
            return 0

    qsh._apply_combo_model_roles(_Combo())  # type: ignore[arg-type]


def test_bind_combo_popup_palette_handles_missing_view_gracefully() -> None:
    """Cover the `view is None` branch."""

    import latencylab_ui.qt_style_helpers as qsh

    class _Combo:
        def view(self):
            return None

    qsh._bind_combo_popup_palette(_Combo())  # type: ignore[arg-type]


def test_combo_popup_hardener_filter_executes_show_path() -> None:
    """Cover `_ComboPopupHardenerFilter.eventFilter()` show branch."""

    from PySide6.QtWidgets import QApplication, QComboBox
    from PySide6.QtGui import QPalette
    from PySide6.QtCore import QEvent

    import latencylab_ui.qt_style_helpers as qsh

    _ = QApplication.instance() or QApplication([])

    combo = QComboBox()
    combo.addItems(["a", "b"])
    qsh.harden_combobox_popup(combo)

    # Grab the installed hardener.
    flt = combo.view()._ll_combo_popup_hardener_filter  # type: ignore[attr-defined]

    ev = QEvent(QEvent.Type.Show)
    assert flt.eventFilter(combo.view(), ev) is False

    # Palette should remain valid after show-time binding.
    pal = combo.view().palette()
    assert pal.color(QPalette.ColorRole.Text).isValid()


def test_harden_combobox_popup_hooks_model_signals_branch() -> None:
    """Cover the model-signal hooking branch (and the refresh closure)."""

    from PySide6.QtWidgets import QApplication, QComboBox

    import latencylab_ui.qt_style_helpers as qsh

    app = QApplication.instance() or QApplication([])
    _ = app

    combo = QComboBox()
    combo.addItems(["x"])
    qsh.harden_combobox_popup(combo)

    model = combo.model()
    assert model is not None
    # Trigger the hooked closure.
    model.modelReset.emit()


def test_harden_combobox_popup_model_signal_hook_try_except_branch(monkeypatch) -> None:
    """Cover the exception handler when connecting model signals fails.

    Use a real QComboBox to satisfy QObject parenting constraints.
    """

    from PySide6.QtWidgets import QApplication, QComboBox

    import latencylab_ui.qt_style_helpers as qsh

    _ = QApplication.instance() or QApplication([])

    combo = QComboBox()
    combo.addItems(["x"])

    model = combo.model()
    assert model is not None

    class _Sig:
        def connect(self, _fn):
            raise RuntimeError("no connect")

    # Monkeypatch Qt signals to throw when connect is attempted.
    monkeypatch.setattr(model, "modelReset", _Sig())
    monkeypatch.setattr(model, "rowsInserted", _Sig())
    monkeypatch.setattr(model, "dataChanged", _Sig())

    qsh.harden_combobox_popup(combo)


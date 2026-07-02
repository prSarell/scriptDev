"""
Eucalyptus Leaf Generator — UI
PySide6 interface for eucalyptusLeaves. Operates on curves from an
already-generated eucalyptusGen tree.

Workflow:
    1. Select tree curves in the viewport/outliner, click "Select Curves".
    2. Drag "Keep Last N CVs" to narrow the selection toward the tip.
    3. Click "Generate Leaves" — repeatable on the same or different curves.
"""

import importlib
import traceback

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

import eucalyptusLeaves


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class EucalyptusLeavesUI(QtWidgets.QDialog):

    TITLE = 'Eucalyptus Leaves'

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._active_curves = []
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        # --- Curve selection ---
        sel_box = QtWidgets.QGroupBox('Curve Selection')
        sel_lay = QtWidgets.QVBoxLayout(sel_box)

        self._select_curves_btn = QtWidgets.QPushButton('Select Curves')
        self._select_curves_btn.setToolTip(
            'Select tree curves first, then click this to switch to CV '
            'mode with every CV on them selected.')
        sel_lay.addWidget(self._select_curves_btn)

        slider_row = QtWidgets.QHBoxLayout()
        self._cv_label = QtWidgets.QLabel('Keep Last N CVs')
        self._cv_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._cv_slider.setRange(1, 1)
        self._cv_slider.setValue(1)
        self._cv_slider.setEnabled(False)
        self._cv_val = QtWidgets.QLabel('-')
        self._cv_val.setFixedWidth(28)
        slider_row.addWidget(self._cv_slider)
        slider_row.addWidget(self._cv_val)
        sel_lay.addWidget(self._cv_label)
        sel_lay.addLayout(slider_row)

        root.addWidget(sel_box)

        # --- Leaf parameters ---
        param_box = QtWidgets.QGroupBox('Leaf Parameters')
        param_lay = QtWidgets.QFormLayout(param_box)
        param_lay.setSpacing(6)

        count_row = QtWidgets.QHBoxLayout()
        self._min_count_spin = QtWidgets.QSpinBox()
        self._min_count_spin.setRange(0, 20)
        self._min_count_spin.setValue(1)
        self._max_count_spin = QtWidgets.QSpinBox()
        self._max_count_spin.setRange(0, 20)
        self._max_count_spin.setValue(3)
        count_row.addWidget(self._min_count_spin)
        count_row.addWidget(QtWidgets.QLabel('to'))
        count_row.addWidget(self._max_count_spin)
        param_lay.addRow('Leaves per CV', count_row)

        self._mode_combo = QtWidgets.QComboBox()
        self._mode_combo.addItem('Low-Poly (close camera)', 'poly')
        self._mode_combo.addItem('Alpha Card (background)', 'card')
        param_lay.addRow('Geometry', self._mode_combo)

        self._stems_check = QtWidgets.QCheckBox('Generate Stems')
        self._stems_check.setChecked(True)
        param_lay.addRow('', self._stems_check)

        self._scale_spin = QtWidgets.QDoubleSpinBox()
        self._scale_spin.setRange(0.01, 10.0)
        self._scale_spin.setValue(1.0)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setDecimals(2)
        self._scale_spin.setToolTip(
            'Match the Scale used to generate the tree.')
        param_lay.addRow('Scale', self._scale_spin)

        root.addWidget(param_box)

        # --- Generate ---
        self._generate_btn = QtWidgets.QPushButton('Generate Leaves')
        self._generate_btn.setEnabled(False)
        self._generate_btn.setStyleSheet(
            'background-color: #339933; color: white; padding: 8px;'
            'font-weight: bold;')
        root.addWidget(self._generate_btn)

        # --- Log ---
        log_box = QtWidgets.QGroupBox('Log')
        log_lay = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(100)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_lay.addWidget(self._log)
        root.addWidget(log_box)

    def _connect_signals(self):
        self._select_curves_btn.clicked.connect(self._on_select_curves)
        self._cv_slider.valueChanged.connect(self._on_slider_changed)
        self._generate_btn.clicked.connect(self._on_generate)

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _show_error(self, text):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Error')
        dlg.setMinimumSize(520, 260)
        lay = QtWidgets.QVBoxLayout(dlg)
        edit = QtWidgets.QPlainTextEdit(text)
        edit.setReadOnly(True)
        edit.setFont(QtGui.QFont('Courier New', 9))
        lay.addWidget(edit)
        close_btn = QtWidgets.QPushButton('Close')
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _on_select_curves(self):
        try:
            importlib.reload(eucalyptusLeaves)
            curves = eucalyptusLeaves.select_curves_and_cvs()
            self._active_curves = curves
            max_cvs = max(
                (eucalyptusLeaves._cv_count(c) for c in curves), default=1)
            self._cv_slider.blockSignals(True)
            self._cv_slider.setRange(1, max_cvs)
            self._cv_slider.setValue(max_cvs)
            self._cv_slider.setEnabled(True)
            self._cv_slider.blockSignals(False)
            self._cv_val.setText(str(max_cvs))
            self._generate_btn.setEnabled(True)
            self._log_msg('Selected {} curve(s), {} CVs max.'.format(
                len(curves), max_cvs))
        except Exception:
            tb = traceback.format_exc()
            self._log_msg(tb)
            self._show_error(tb)

    def _on_slider_changed(self, value):
        self._cv_val.setText(str(value))
        if not self._active_curves:
            return
        try:
            eucalyptusLeaves.reduce_selection_to_tip(
                self._active_curves, value)
        except Exception:
            tb = traceback.format_exc()
            self._log_msg(tb)
            self._show_error(tb)

    def _on_generate(self):
        min_count = self._min_count_spin.value()
        max_count = self._max_count_spin.value()
        mode = self._mode_combo.currentData()
        stems = self._stems_check.isChecked()
        scale = self._scale_spin.value()

        try:
            importlib.reload(eucalyptusLeaves)
            self._log_msg(
                'Generating leaves ({}, stems={}, {}-{} per CV)...'.format(
                    mode, stems, min_count, max_count))
            created = eucalyptusLeaves.generate_leaves(
                min_count=min_count, max_count=max_count,
                mode=mode, stems=stems, scale=scale)
            self._log_msg('Created {} node(s).'.format(len(created)))
        except Exception:
            tb = traceback.format_exc()
            self._log_msg(tb)
            self._show_error(tb)


_instance = None


def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
    _instance = EucalyptusLeavesUI()
    _instance.show()
    return _instance

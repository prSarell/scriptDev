"""
Eucalyptus Generator — UI
PySide6 interface for eucalyptusGen.
"""

import sys
import os
import random
import importlib
import traceback

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

import eucalyptusGen


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class EucalyptusGenUI(QtWidgets.QDialog):

    TITLE = 'Eucalyptus Generator'

    SPECIES = [
        ('citriodora',    'Lemon-Scented Gum'),
        ('pauciflora',    'Snow Gum'),
        ('regnans',       'Mountain Ash'),
        ('camaldulensis', 'River Red Gum'),
    ]

    AGES = ['sapling', 'young', 'mature', 'old_growth']

    DENSITIES = ['sparse', 'typical', 'dense']

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._build_ui()
        self._connect_signals()
        self._on_species_changed(0)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        # --- Species ---
        species_box = QtWidgets.QGroupBox('Species')
        species_lay = QtWidgets.QVBoxLayout(species_box)
        self._species_combo = QtWidgets.QComboBox()
        for key, label in self.SPECIES:
            self._species_combo.addItem(label, key)
        species_lay.addWidget(self._species_combo)
        root.addWidget(species_box)

        # --- Parameters ---
        param_box = QtWidgets.QGroupBox('Parameters')
        param_lay = QtWidgets.QFormLayout(param_box)
        param_lay.setSpacing(6)

        self._age_combo = QtWidgets.QComboBox()
        self._age_combo.addItems(self.AGES)
        self._age_combo.setCurrentIndex(2)
        param_lay.addRow('Age Stage', self._age_combo)

        self._density_combo = QtWidgets.QComboBox()
        self._density_combo.addItems(self.DENSITIES)
        self._density_combo.setCurrentIndex(1)  # typical
        param_lay.addRow('Density', self._density_combo)

        # Seed row — spinner + randomise button side by side
        seed_row = QtWidgets.QHBoxLayout()
        self._seed_spin = QtWidgets.QSpinBox()
        self._seed_spin.setRange(1, 9999)
        self._seed_spin.setValue(42)
        self._seed_random_btn = QtWidgets.QPushButton('↺')
        self._seed_random_btn.setFixedWidth(28)
        self._seed_random_btn.setToolTip('Pick a random seed')
        seed_row.addWidget(self._seed_spin)
        seed_row.addWidget(self._seed_random_btn)
        param_lay.addRow('Seed', seed_row)

        self._scale_spin = QtWidgets.QDoubleSpinBox()
        self._scale_spin.setRange(0.01, 10.0)
        self._scale_spin.setValue(1.0)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setDecimals(2)
        param_lay.addRow('Scale', self._scale_spin)

        # Exposure slider (pauciflora only)
        self._exposure_label = QtWidgets.QLabel('Exposure')
        self._exposure_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._exposure_slider.setRange(0, 100)
        self._exposure_slider.setValue(50)
        self._exposure_val = QtWidgets.QLabel('0.50')
        self._exposure_val.setFixedWidth(30)
        exposure_row = QtWidgets.QHBoxLayout()
        exposure_row.addWidget(self._exposure_slider)
        exposure_row.addWidget(self._exposure_val)
        param_lay.addRow(self._exposure_label, exposure_row)

        root.addWidget(param_box)

        # --- Generate / Reset ---
        btn_row = QtWidgets.QHBoxLayout()
        self._generate_btn = QtWidgets.QPushButton('Generate')
        self._generate_btn.setStyleSheet(
            'background-color: #339933; color: white; padding: 8px;'
            'font-weight: bold;')
        self._reset_btn = QtWidgets.QPushButton('Reset')
        self._reset_btn.setFixedWidth(64)
        btn_row.addWidget(self._generate_btn)
        btn_row.addWidget(self._reset_btn)
        root.addLayout(btn_row)

        # --- Log ---
        log_box = QtWidgets.QGroupBox('Log')
        log_lay = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_lay.addWidget(self._log)
        root.addWidget(log_box)

    def _connect_signals(self):
        self._species_combo.currentIndexChanged.connect(
            self._on_species_changed)
        self._exposure_slider.valueChanged.connect(self._on_exposure_changed)
        self._seed_random_btn.clicked.connect(self._on_random_seed)
        self._generate_btn.clicked.connect(self._on_generate)
        self._reset_btn.clicked.connect(self._on_reset)

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

    def _on_species_changed(self, idx):
        is_pauciflora = self._species_combo.currentData() == 'pauciflora'
        self._exposure_label.setVisible(is_pauciflora)
        self._exposure_slider.setVisible(is_pauciflora)
        self._exposure_val.setVisible(is_pauciflora)

    def _on_exposure_changed(self, val):
        self._exposure_val.setText('{:.2f}'.format(val / 100.0))

    def _on_random_seed(self):
        self._seed_spin.setValue(random.randint(1, 9999))

    def _on_reset(self):
        self._species_combo.setCurrentIndex(0)
        self._age_combo.setCurrentIndex(2)       # mature
        self._density_combo.setCurrentIndex(1)   # typical
        self._seed_spin.setValue(42)
        self._scale_spin.setValue(1.0)
        self._exposure_slider.setValue(50)

    def _on_generate(self):
        species  = self._species_combo.currentData()
        age      = self._age_combo.currentText()
        density  = self._density_combo.currentText()
        seed     = self._seed_spin.value()
        scale    = self._scale_spin.value()
        exposure = self._exposure_slider.value() / 100.0

        try:
            importlib.reload(eucalyptusGen)
            sp_name = eucalyptusGen.SPECIES[species].get('common_name', species)
            self._log_msg('Generating {} {} {} (seed={}, scale={})...'.format(
                sp_name, age, density, seed, scale))
            grp = eucalyptusGen.generate(
                species=species, age=age, seed=seed,
                scale=scale, exposure=exposure, density=density)
            cmds.select(grp)
            cmds.viewFit()
            self._log_msg('Created: {}'.format(grp))
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
    _instance = EucalyptusGenUI()
    _instance.show()
    return _instance

"""
Virtual Pancakes Shader UI
PySide6 interface for vp_shader_api.
"""

import os
import sys

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import vp_shader_api as api


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


class VpShaderUI(QtWidgets.QDialog):

    TITLE = 'VP Shader Assign'

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # Status
        self._status_label = QtWidgets.QLabel()
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        # Colour key
        key_box = QtWidgets.QGroupBox('Colour Key')
        key_layout = QtWidgets.QGridLayout(key_box)
        key_layout.setSpacing(6)
        key_layout.setColumnStretch(2, 1)
        for row, (label, hex_col, desc) in enumerate([
            ('Joint Boundary', '#ff6600',
             'Edge-loop boundary ring between adjacent VP regions — actual joint position'),
            ('VP Region',      '#bf9c7f',
             'Full body/face VP region fill — arms, legs, fingers, toes, face'),
            ('Structural',     '#3380cc',
             'Main combined body mesh, inner mouth'),
            ('Secondary',      '#666666',
             'Eyes, teeth, tongue, eyelashes'),
        ]):
            swatch = QtWidgets.QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                'background-color: {}; border: 1px solid #444;'.format(hex_col)
            )
            key_layout.addWidget(swatch, row, 0)
            key_layout.addWidget(QtWidgets.QLabel(label), row, 1)
            desc_lbl = QtWidgets.QLabel(desc)
            desc_lbl.setStyleSheet('color: #888888; font-size: 10px;')
            key_layout.addWidget(desc_lbl, row, 2)
        root.addWidget(key_box)

        # Apply button
        self._btn_apply = QtWidgets.QPushButton('Apply Shaders')
        self._btn_apply.setMinimumHeight(36)
        font = self._btn_apply.font()
        font.setBold(True)
        self._btn_apply.setFont(font)
        self._btn_apply.clicked.connect(self._apply)
        root.addWidget(self._btn_apply)

        # Remove button
        self._btn_remove = QtWidgets.QPushButton('Remove VP Shaders')
        self._btn_remove.setMinimumHeight(28)
        self._btn_remove.setStyleSheet(
            'QPushButton { color: #d9734a; }'
            'QPushButton:hover { color: #e8895e; }'
        )
        self._btn_remove.clicked.connect(self._remove)
        root.addWidget(self._btn_remove)

        # Log
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        root.addWidget(self._log)

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _refresh_status(self):
        sets = api.find_vp_sets()
        if sets:
            self._status_label.setText(
                'Found {} VP selection sets.'.format(len(sets))
            )
            self._status_label.setStyleSheet('color: #66aa66; font-size: 11px;')
        else:
            self._status_label.setText(
                'No VP selection sets found — import the VP combined mesh first.'
            )
            self._status_label.setStyleSheet('color: #d9734a; font-size: 11px;')

    def _apply(self):
        try:
            boundary_count, total = api.apply_shaders()
            self._log_msg(
                'Done — {} boundary sets created across {} VP sets.'.format(
                    boundary_count, total)
            )
            self._refresh_status()
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))

    def _remove(self):
        try:
            deleted = api.remove_shaders()
            self._log_msg(
                'Removed: {}'.format(', '.join(deleted)) if deleted
                else 'No VP shaders found in scene.'
            )
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

_instance = None


def show():
    global _instance
    if _instance and not shiboken6.isValid(_instance):
        _instance = None
    if _instance is None:
        _instance = VpShaderUI()
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()

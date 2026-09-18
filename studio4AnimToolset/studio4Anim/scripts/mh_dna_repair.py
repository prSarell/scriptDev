"""
mh_dna_repair.py — repairs a broken Metahuman DNA file path.
Finds the embeddedNodeRL4 node connected to head_lod0_mesh and lets the
student browse to the correct .dna file to restore the face rig.
"""

import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6


def _maya_main_window():
    return shiboken6.wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def find_rl4_node():
    """
    Return the embeddedNodeRL4 node name, or None.
    Looks in the history of head_lod0_mesh first, then falls back to ls(type=).
    """
    for mesh_name in ('head_lod0_mesh',):
        if cmds.objExists(mesh_name):
            history = cmds.listHistory(mesh_name, pruneDagObjects=True) or []
            for node in history:
                if cmds.nodeType(node) == 'embeddedNodeRL4':
                    return node

    # Fallback: any embeddedNodeRL4 in scene
    nodes = cmds.ls(type='embeddedNodeRL4') or []
    if nodes:
        return nodes[0]

    # Last resort: dnaFileNode
    nodes = cmds.ls(type='dnaFileNode') or []
    return nodes[0] if nodes else None


def get_dna_path(node):
    """Return (attr_name, current_path_string) for the DNA file path."""
    for attr in ('dnaFilePath', 'inputDna', 'dna', 'filePath'):
        try:
            val = cmds.getAttr('{}.{}'.format(node, attr))
            if val is not None:
                return attr, str(val)
        except Exception:
            pass
    return None, ''


def set_dna_path(node, attr, path):
    cmds.setAttr('{}.{}'.format(node, attr), path, type='string')


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class MhDnaRepairUI(QtWidgets.QDialog):

    TITLE = 'MH DNA Repair'

    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._node = None
        self._attr = None
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(10)

        # Node info
        info_box = QtWidgets.QGroupBox('Detected Node')
        info_layout = QtWidgets.QFormLayout(info_box)
        self._node_label = QtWidgets.QLabel('—')
        self._attr_label = QtWidgets.QLabel('—')
        info_layout.addRow('Node:', self._node_label)
        info_layout.addRow('Attribute:', self._attr_label)
        root.addWidget(info_box)

        # Path
        path_box = QtWidgets.QGroupBox('DNA File Path')
        path_layout = QtWidgets.QVBoxLayout(path_box)

        self._status_label = QtWidgets.QLabel()
        self._status_label.setWordWrap(True)
        font = self._status_label.font()
        font.setBold(True)
        self._status_label.setFont(font)
        path_layout.addWidget(self._status_label)

        path_row = QtWidgets.QHBoxLayout()
        self._path_field = QtWidgets.QLineEdit()
        self._path_field.setPlaceholderText('Path to .dna file...')
        browse_btn = QtWidgets.QPushButton('Browse...')
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_field)
        path_row.addWidget(browse_btn)
        path_layout.addLayout(path_row)

        root.addWidget(path_box)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self._apply_btn = QtWidgets.QPushButton('Apply')
        self._apply_btn.setMinimumHeight(32)
        self._apply_btn.clicked.connect(self._apply)
        close_btn = QtWidgets.QPushButton('Close')
        close_btn.setMinimumHeight(32)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _refresh(self):
        self._node = find_rl4_node()

        if not self._node:
            self._node_label.setText('Not found — is a Metahuman rig loaded?')
            self._attr_label.setText('—')
            self._status_label.setText('')
            self._path_field.setEnabled(False)
            self._apply_btn.setEnabled(False)
            return

        self._attr, current_path = get_dna_path(self._node)

        self._node_label.setText(self._node)
        self._attr_label.setText(self._attr or '—')
        self._path_field.setEnabled(True)
        self._apply_btn.setEnabled(bool(self._attr))

        if not self._attr:
            self._status_label.setText('Could not locate the DNA path attribute.')
            self._status_label.setStyleSheet('color: #cc4444;')
            return

        self._path_field.setText(current_path or '')

        if current_path and os.path.exists(current_path):
            self._status_label.setText('Status: OK — file found')
            self._status_label.setStyleSheet('color: #44aa44;')
        else:
            self._status_label.setText('Status: MISSING — file not found at current path')
            self._status_label.setStyleSheet('color: #cc4444;')

    def _browse(self):
        current = self._path_field.text().strip()
        start_dir = os.path.dirname(current) if current else ''
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Locate DNA File', start_dir, 'DNA Files (*.dna);;All Files (*)'
        )
        if path:
            self._path_field.setText(path)

    def _apply(self):
        path = self._path_field.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(self, self.TITLE, 'No path entered.')
            return
        if not os.path.exists(path):
            result = QtWidgets.QMessageBox.question(
                self, self.TITLE,
                'File not found at that path. Apply anyway?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if result != QtWidgets.QMessageBox.Yes:
                return
        try:
            set_dna_path(self._node, self._attr, path)
            self._refresh()
            cmds.inViewMessage(amg='<b>DNA path updated.</b>', pos='midCenter', fade=True)
            print('[mh_dna_repair] {}.{} = {}'.format(self._node, self._attr, path))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, self.TITLE, 'Failed to set path:\n{}'.format(e))


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

_instance = None


def show():
    global _instance
    if _instance and not shiboken6.isValid(_instance):
        _instance = None
    if _instance is None:
        _instance = MhDnaRepairUI()
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()

"""
Metahuman Rig Recycle — UI
PySide6 interface for mh_recycle_api.
"""

import sys
import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import mh_recycle_api as api


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class _ActionButton(QtWidgets.QFrame):
    """A large labelled button with a description line beneath it."""

    def __init__(self, label, description, danger=False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(10, 8, 10, 8)

        self.btn = QtWidgets.QPushButton(label)
        self.btn.setMinimumHeight(34)
        font = self.btn.font()
        font.setBold(True)
        self.btn.setFont(font)
        if danger:
            self.btn.setStyleSheet(
                'QPushButton { color: #d9734a; }'
                'QPushButton:hover { color: #e8895e; }'
            )
        layout.addWidget(self.btn)

        desc_label = QtWidgets.QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet('color: #888888; font-size: 11px;')
        layout.addWidget(desc_label)

    def clicked_connect(self, slot):
        self.btn.clicked.connect(slot)

    def set_label(self, text):
        self.btn.setText(text)

    def set_enabled(self, enabled):
        self.btn.setEnabled(enabled)


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

class MhRecycleUI(QtWidgets.QDialog):

    TITLE = 'MH Rig Recycle'

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(440)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(6)

        # --- Rig Setup ---
        setup_box = QtWidgets.QGroupBox('Rig Setup')
        setup_layout = QtWidgets.QFormLayout(setup_box)
        setup_layout.setSpacing(6)

        ns_row = QtWidgets.QHBoxLayout()
        self._ns_field = QtWidgets.QLineEdit(':')
        self._ns_field.setPlaceholderText(': for root namespace')
        ns_row.addWidget(self._ns_field)
        setup_layout.addRow('Namespace:', ns_row)

        mesh_row = QtWidgets.QHBoxLayout()
        self._mesh_field = QtWidgets.QLineEdit()
        self._mesh_field.setPlaceholderText('e.g. head_lod0_mesh')
        auto_btn = QtWidgets.QPushButton('Auto')
        auto_btn.setFixedWidth(42)
        auto_btn.clicked.connect(self._auto_detect_mesh)
        sel_btn = QtWidgets.QPushButton('From Sel')
        sel_btn.setFixedWidth(60)
        sel_btn.clicked.connect(self._mesh_from_selection)
        mesh_row.addWidget(self._mesh_field)
        mesh_row.addWidget(auto_btn)
        mesh_row.addWidget(sel_btn)
        setup_layout.addRow('Face Mesh:', mesh_row)

        root.addWidget(setup_box)

        # --- Action Buttons ---
        self._btn_compare = _ActionButton(
            'Preview Comparison',
            'Templates the original RL mesh to a grey wireframe so both rigs '
            'respond to the faceboard simultaneously. Press again to restore.',
        )
        self._btn_compare.clicked_connect(self._toggle_comparison)
        root.addWidget(self._btn_compare)

        self._btn_del_meshes = _ActionButton(
            'Delete Original Face Meshes',
            'Permanently deletes all RigLogic-driven face meshes — all head '
            'LODs, teeth, eyes, and any other meshes in the rig\'s deformer '
            'history — along with any associated display layers. Do this once '
            'the comparison looks good and you are committing to the '
            'blendshape rig.',
            danger=True,
        )
        self._btn_del_meshes.clicked_connect(self._delete_rl_meshes)
        root.addWidget(self._btn_del_meshes)

        self._btn_del_rl = _ActionButton(
            'Remove RigLogic Nodes',
            'Deletes the rigLogic, embeddedNodeRL4, and dnaFileNode plugin '
            'nodes. After this step the scene opens cleanly with no Metahuman '
            'plugin required.',
            danger=True,
        )
        self._btn_del_rl.clicked_connect(self._remove_rl_nodes)
        root.addWidget(self._btn_del_rl)

        self._btn_export = _ActionButton(
            'Export Standalone Scene',
            'Opens a save dialog and exports a new .ma file containing the '
            'current scene. The working scene is left untouched.',
        )
        self._btn_export.clicked_connect(self._export_standalone)
        root.addWidget(self._btn_export)

        self._btn_del_targets = _ActionButton(
            'Delete Bake Targets',
            'Removes mhBsTargets_GRP and all individual baked target meshes. '
            'Only do this if you are finished editing the blendshapes — these '
            'are your only way to sculpt corrections back into the rig. '
            'Once deleted, the shapes cannot be modified.',
            danger=True,
        )
        self._btn_del_targets.clicked_connect(self._delete_bake_targets)
        root.addWidget(self._btn_del_targets)

        # --- Log ---
        log_box = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_layout.addWidget(self._log)
        root.addWidget(log_box)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _get_namespace(self):
        ns = self._ns_field.text().strip()
        if ns and not ns.endswith(':'):
            ns += ':'
        return ns or ':'

    def _get_face_mesh(self):
        return self._mesh_field.text().strip()

    def _auto_detect_mesh(self):
        ns = self._get_namespace()
        mesh = api.find_face_mesh(ns)
        if mesh:
            self._mesh_field.setText(mesh)
            self._log_msg('Auto-detected: {}'.format(mesh))
        else:
            self._log_msg('Could not auto-detect face mesh.')

    def _mesh_from_selection(self):
        sel = cmds.ls(selection=True, transforms=True)
        if sel:
            self._mesh_field.setText(sel[0])
            self._log_msg('Set face mesh: {}'.format(sel[0]))
        else:
            self._log_msg('Nothing selected.')

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_comparison(self):
        face_mesh = self._get_face_mesh()
        if not face_mesh:
            self._log_msg('ERROR: No face mesh set.')
            return
        try:
            is_on = api.toggle_comparison(face_mesh)
            self._btn_compare.set_label(
                'Disable Comparison' if is_on else 'Preview Comparison'
            )
            self._log_msg('Comparison {}.'.format('ON' if is_on else 'OFF'))
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))

    def _delete_rl_meshes(self):
        try:
            mesh_count, layer_count = api.delete_rl_meshes()
            self._log_msg(
                'Deleted {} face mesh(es) and {} display layer(s).'.format(
                    mesh_count, layer_count
                )
            )
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))

    def _remove_rl_nodes(self):
        try:
            deleted = api.remove_rl_nodes()
            if deleted:
                self._log_msg('Removed: {}'.format(', '.join(deleted)))
            else:
                self._log_msg('No rigLogic nodes found in scene.')
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))

    def _export_standalone(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Export Standalone Scene',
            '',
            'Maya ASCII (*.ma)',
        )
        if not path:
            return
        if not path.endswith('.ma'):
            path += '.ma'
        try:
            api.export_standalone(path)
            self._log_msg('Exported: {}'.format(path))
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))

    def _delete_bake_targets(self):
        try:
            found = api.delete_bake_targets()
            if found:
                self._log_msg('Deleted mhBsTargets_GRP.')
            else:
                self._log_msg('mhBsTargets_GRP not found in scene.')
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
        _instance = MhRecycleUI()
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()

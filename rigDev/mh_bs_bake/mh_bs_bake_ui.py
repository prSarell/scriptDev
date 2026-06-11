"""
Metahuman Blendshape Baking Pipeline — UI
PySide6 interface for mh_bs_bake_api.
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

import mh_bs_bake_api as api


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class MhBsBakeUI(QtWidgets.QDialog):

    TITLE = 'MH Blendshape Baker'

    def __init__(self, parent=_maya_main_window()):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        self._phase1_result = None

        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        # --- Rig Setup ---
        setup_box = QtWidgets.QGroupBox('Rig Setup')
        setup_layout = QtWidgets.QFormLayout(setup_box)
        setup_layout.setSpacing(6)

        ns_row = QtWidgets.QHBoxLayout()
        self._ns_field = QtWidgets.QLineEdit(':')
        self._ns_field.setPlaceholderText(': for root namespace')
        ns_row.addWidget(self._ns_field)
        setup_layout.addRow('Namespace:', ns_row)

        def _mesh_row(placeholder, auto_slot, sel_slot):
            row = QtWidgets.QHBoxLayout()
            field = QtWidgets.QLineEdit()
            field.setPlaceholderText(placeholder)
            a_btn = QtWidgets.QPushButton('Auto')
            a_btn.setFixedWidth(42)
            a_btn.clicked.connect(auto_slot)
            s_btn = QtWidgets.QPushButton('From Sel')
            s_btn.setFixedWidth(60)
            s_btn.clicked.connect(sel_slot)
            row.addWidget(field)
            row.addWidget(a_btn)
            row.addWidget(s_btn)
            return field, row

        self._mesh_field, mesh_row = _mesh_row(
            'e.g. head_lod0_mesh', self._auto_detect_mesh, self._mesh_from_selection)
        setup_layout.addRow('Face Mesh:', mesh_row)

        self._teeth_field, teeth_row = _mesh_row(
            'e.g. teeth_lod0_mesh', self._auto_detect_teeth, self._teeth_from_selection)
        setup_layout.addRow('Teeth Mesh:', teeth_row)


        root.addWidget(setup_box)

        # --- Phase 1 ---
        p1_box = QtWidgets.QGroupBox('Phase 1 — Single Shapes')
        p1_layout = QtWidgets.QVBoxLayout(p1_box)
        p1_layout.setSpacing(6)

        p1_desc = QtWidgets.QLabel(
            'Poses each control channel to its extreme, captures blendshape\n'
            'targets, and wires weights back to the controls via SDK.'
        )
        p1_desc.setWordWrap(True)
        p1_layout.addWidget(p1_desc)

        self._p1_btn = QtWidgets.QPushButton('Bake Single Shapes')
        self._p1_btn.clicked.connect(self._run_phase1)
        p1_layout.addWidget(self._p1_btn)

        self._p1_progress = QtWidgets.QProgressBar()
        self._p1_progress.setVisible(False)
        p1_layout.addWidget(self._p1_progress)

        root.addWidget(p1_box)

        # --- Phase 2 ---
        p2_box = QtWidgets.QGroupBox('Phase 2 — Corrective Shapes')
        p2_layout = QtWidgets.QVBoxLayout(p2_box)
        p2_layout.setSpacing(6)

        p2_desc = QtWidgets.QLabel(
            'Searches all control-pair combinations, compares vertex positions\n'
            'against the original rig, and bakes residual correctives. Run\n'
            'Phase 1 first. Can be left running overnight (headless-safe).'
        )
        p2_desc.setWordWrap(True)
        p2_layout.addWidget(p2_desc)

        thresh_row = QtWidgets.QHBoxLayout()
        thresh_row.addWidget(QtWidgets.QLabel('Threshold (mm):'))
        self._threshold_spin = QtWidgets.QDoubleSpinBox()
        self._threshold_spin.setRange(0.01, 10.0)
        self._threshold_spin.setSingleStep(0.05)
        self._threshold_spin.setValue(0.1)
        self._threshold_spin.setDecimals(2)
        thresh_row.addWidget(self._threshold_spin)
        thresh_row.addStretch()
        p2_layout.addLayout(thresh_row)

        self._p2_btn = QtWidgets.QPushButton('Find && Apply Correctives')
        self._p2_btn.clicked.connect(self._run_phase2)
        p2_layout.addWidget(self._p2_btn)

        self._p2_progress = QtWidgets.QProgressBar()
        self._p2_progress.setVisible(False)
        p2_layout.addWidget(self._p2_progress)

        root.addWidget(p2_box)

        # --- Log ---
        log_box = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_layout.addWidget(self._log)
        root.addWidget(log_box)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _get_namespace(self):
        ns = self._ns_field.text().strip()
        if ns and not ns.endswith(':'):
            ns += ':'
        return ns or ':'

    def _auto_detect_mesh(self):
        ns = self._get_namespace()
        mesh = api.find_face_mesh(ns)
        if mesh:
            self._mesh_field.setText(mesh)
            self._log_msg('Auto-detected face mesh: {}'.format(mesh))
        else:
            self._log_msg('Could not auto-detect face mesh.')

    def _mesh_from_selection(self):
        sel = cmds.ls(selection=True, transforms=True)
        if sel:
            self._mesh_field.setText(sel[0])
            self._log_msg('Set face mesh: {}'.format(sel[0]))
        else:
            self._log_msg('Nothing selected.')

    def _auto_detect_teeth(self):
        ns = self._get_namespace()
        mesh = api.find_teeth_mesh(ns)
        if mesh:
            self._teeth_field.setText(mesh)
            self._log_msg('Auto-detected teeth mesh: {}'.format(mesh))
        else:
            self._log_msg('Could not auto-detect teeth mesh.')

    def _teeth_from_selection(self):
        sel = cmds.ls(selection=True, transforms=True)
        if sel:
            self._teeth_field.setText(sel[0])
            self._log_msg('Set teeth mesh: {}'.format(sel[0]))
        else:
            self._log_msg('Nothing selected.')


    def _make_progress_cb(self, bar):
        bar.setVisible(True)
        bar.setValue(0)

        def cb(current, total, label):
            bar.setMaximum(max(total, 1))
            bar.setValue(current)
            bar.setFormat('{} (%p%)'.format(label))
            QtWidgets.QApplication.processEvents()

        return cb

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_face_mesh(self):
        return self._mesh_field.text().strip()

    def _run_phase1(self):
        namespace = self._get_namespace()

        meshes = [
            (self._mesh_field.text().strip(),  'face'),
            (self._teeth_field.text().strip(), 'teeth'),
        ]
        meshes = [(m, label) for m, label in meshes if m]

        if not meshes:
            self._log_msg('ERROR: No meshes set. Use Auto or From Sel.')
            return
        for mesh, _ in meshes:
            if not cmds.objExists(mesh):
                self._log_msg('ERROR: "{}" does not exist in the scene.'.format(mesh))
                return

        self._log_msg('--- Phase 1 start ({} mesh(es)) ---'.format(len(meshes)))
        self._p1_btn.setEnabled(False)
        self._phase1_result = None
        cb = self._make_progress_cb(self._p1_progress)

        try:
            for mesh, label in meshes:
                self._log_msg('Baking {}...'.format(label))
                result = api.bake_single_shapes(mesh, namespace, cb)
                self._log_msg('{} done: {} targets, bs_node={}, bs_base={}'.format(
                    label,
                    len(result['extremes']),
                    result['bs_node'],
                    result['bs_base'],
                ))
                if label == 'face':
                    self._phase1_result = result
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))
        finally:
            self._p1_btn.setEnabled(True)
            self._p1_progress.setVisible(False)

    def _run_phase2(self):
        if self._phase1_result is None:
            self._log_msg('ERROR: Run Phase 1 first.')
            return

        face_mesh = self._get_face_mesh()
        namespace = self._get_namespace()
        threshold = self._threshold_spin.value()

        if not face_mesh or not cmds.objExists(face_mesh):
            self._log_msg('ERROR: Face mesh not found.')
            return

        self._log_msg('--- Phase 2 start (threshold={:.2f}mm) ---'.format(threshold))
        self._p2_btn.setEnabled(False)
        cb = self._make_progress_cb(self._p2_progress)

        try:
            count = api.find_and_apply_correctives(
                face_mesh, self._phase1_result, namespace, threshold, 2, cb
            )
            self._log_msg('Phase 2 complete: {} correctives added.'.format(count))
        except Exception as e:
            self._log_msg('ERROR: {}'.format(e))
        finally:
            self._p2_btn.setEnabled(True)
            self._p2_progress.setVisible(False)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

_instance = None

def show():
    global _instance
    if _instance and not shiboken6.isValid(_instance):
        _instance = None
    if _instance is None:
        _instance = MhBsBakeUI()
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()

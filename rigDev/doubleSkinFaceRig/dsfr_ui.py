"""
dsfr_ui.py — Double Skin Face Rig UI
Four-phase PySide6 interface for dsfr_api.
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

import dsfr_api as api


def _maya_main_window():
    return shiboken6.wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


# ── Phase section widget ──────────────────────────────────────────────────────

class _PhaseBox(QtWidgets.QGroupBox):
    """A numbered phase section with a coloured status badge."""

    def __init__(self, number, title, parent=None):
        super().__init__('{} — {}'.format(number, title), parent)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setSpacing(6)
        self._status = QtWidgets.QLabel('not built')
        self._status.setStyleSheet('color: #888888; font-size: 11px;')
        self._layout.addWidget(self._status)

    def add_row(self, widget):
        self._layout.addWidget(widget)

    def add_layout(self, layout):
        self._layout.addLayout(layout)

    def set_done(self, node_name):
        self._status.setText('✔  {}'.format(node_name))
        self._status.setStyleSheet('color: #55bb55; font-size: 11px; font-weight: bold;')

    def set_error(self, msg):
        self._status.setText('✖  {}'.format(msg))
        self._status.setStyleSheet('color: #cc4444; font-size: 11px;')

    def set_pending(self, msg='not built'):
        self._status.setText(msg)
        self._status.setStyleSheet('color: #888888; font-size: 11px;')


# ── Multi-item list widget ─────────────────────────────────────────────────────

class _SelectionList(QtWidgets.QWidget):
    """Read-only list + 'From Sel' button — stores Maya node names."""

    def __init__(self, placeholder='', parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._list.setMaximumHeight(72)
        self._list.setToolTip(placeholder)

        btn_col = QtWidgets.QVBoxLayout()
        self._btn_sel = QtWidgets.QPushButton('From\nSel')
        self._btn_sel.setFixedWidth(52)
        self._btn_clr = QtWidgets.QPushButton('Clear')
        self._btn_clr.setFixedWidth(52)
        btn_col.addWidget(self._btn_sel)
        btn_col.addWidget(self._btn_clr)
        btn_col.addStretch()

        layout.addWidget(self._list)
        layout.addLayout(btn_col)

        self._btn_sel.clicked.connect(self._from_selection)
        self._btn_clr.clicked.connect(self._list.clear)

    def _from_selection(self):
        items = cmds.ls(selection=True) or []
        self._list.clear()
        for item in items:
            self._list.addItem(item)

    def items(self):
        return [self._list.item(i).text() for i in range(self._list.count())]

    def set_items(self, names):
        self._list.clear()
        for n in names:
            self._list.addItem(n)


# ── Main dialog ───────────────────────────────────────────────────────────────

class DSFRDialog(QtWidgets.QDialog):

    TITLE = 'Double Skin Face Rig'

    def __init__(self, parent=None):
        super().__init__(parent or _maya_main_window())
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        # Cached node names set after each phase
        self._uvpin_node = None
        self._sk1_node   = None
        self._bs_node    = None
        self._sk2_node   = None

        self._build_ui()
        self._auto_detect_mesh()
        self._sync_from_scene()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)

        # ── Face mesh ──────────────────────────────────────────────────────────
        mesh_box = QtWidgets.QGroupBox('Face Mesh')
        mesh_layout = QtWidgets.QHBoxLayout(mesh_box)
        self._mesh_field = QtWidgets.QLineEdit()
        self._mesh_field.setPlaceholderText('e.g. head_mesh')
        auto_btn = QtWidgets.QPushButton('Auto')
        auto_btn.setFixedWidth(42)
        auto_btn.clicked.connect(self._auto_detect_mesh)
        sel_btn = QtWidgets.QPushButton('From Sel')
        sel_btn.setFixedWidth(60)
        sel_btn.clicked.connect(self._mesh_from_sel)
        mesh_layout.addWidget(self._mesh_field)
        mesh_layout.addWidget(auto_btn)
        mesh_layout.addWidget(sel_btn)
        root.addWidget(mesh_box)

        # ── Phase 1 — Surface joints ───────────────────────────────────────────
        self._p1_box = _PhaseBox('①', 'Surface Joints')

        self._p1_box.add_row(QtWidgets.QLabel(
            'Select locators placed on the face mesh, then click Create.'
        ))

        radius_row = QtWidgets.QHBoxLayout()
        radius_row.addWidget(QtWidgets.QLabel('Control radius:'))
        self._radius_spin = QtWidgets.QDoubleSpinBox()
        self._radius_spin.setRange(0.01, 100.0)
        self._radius_spin.setValue(0.5)
        self._radius_spin.setSingleStep(0.1)
        self._radius_spin.setDecimals(2)
        self._radius_spin.setFixedWidth(70)
        radius_row.addWidget(self._radius_spin)
        radius_row.addStretch()
        self._p1_box.add_layout(radius_row)

        self._p1_btn = QtWidgets.QPushButton('Create from Selected Locators')
        self._p1_btn.setMinimumHeight(30)
        self._p1_btn.clicked.connect(self._run_phase1)
        self._p1_box.add_row(self._p1_btn)
        root.addWidget(self._p1_box)

        # ── Phase 2 — Coarse bind ──────────────────────────────────────────────
        self._p2_box = _PhaseBox('②', 'Coarse Bind  (SkinCluster 1)')
        self._p2_box.add_row(QtWidgets.QLabel('Select skeleton joints (head, neck, jaw, etc.):'))
        self._p2_list = _SelectionList('Head/neck/jaw skeleton joints')
        self._p2_box.add_row(self._p2_list)

        self._p2_btn = QtWidgets.QPushButton('Bind')
        self._p2_btn.setMinimumHeight(30)
        self._p2_btn.clicked.connect(self._run_phase2)
        self._p2_box.add_row(self._p2_btn)
        root.addWidget(self._p2_box)

        # ── Phase 3 — BlendShape ───────────────────────────────────────────────
        self._p3_box = _PhaseBox('③', 'BlendShape Layer')
        self._p3_box.add_row(QtWidgets.QLabel('Select target meshes (one per shape):'))
        self._p3_list = _SelectionList('Sculpted target meshes')
        self._p3_box.add_row(self._p3_list)

        self._p3_btn = QtWidgets.QPushButton('Add BlendShape')
        self._p3_btn.setMinimumHeight(30)
        self._p3_btn.clicked.connect(self._run_phase3)
        self._p3_box.add_row(self._p3_btn)
        root.addWidget(self._p3_box)

        # ── Phase 4 — Fine bind ────────────────────────────────────────────────
        self._p4_box = _PhaseBox('④', 'Fine Bind  (SkinCluster 2)')
        self._p4_box.add_row(QtWidgets.QLabel(
            'Binds all surface joints as SK2 and wires bindPreMatrix\n'
            'so only animator-driven offsets fire the cluster.'
        ))
        self._p4_btn = QtWidgets.QPushButton('Bind Surface Joints')
        self._p4_btn.setMinimumHeight(30)
        self._p4_btn.clicked.connect(self._run_phase4)
        self._p4_box.add_row(self._p4_btn)
        root.addWidget(self._p4_box)

        # ── Log ────────────────────────────────────────────────────────────────
        log_box = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(110)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_layout.addWidget(self._log)
        root.addWidget(log_box)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _face_mesh(self):
        return self._mesh_field.text().strip()

    def _auto_detect_mesh(self):
        mesh = api.find_face_mesh()
        if mesh:
            self._mesh_field.setText(mesh)

    def _mesh_from_sel(self):
        sel = cmds.ls(selection=True, transforms=True)
        if sel:
            self._mesh_field.setText(sel[0])

    def _sync_from_scene(self):
        """Populate status badges from any existing rig nodes on the face mesh."""
        mesh = self._face_mesh()
        if not mesh or not cmds.objExists(mesh):
            return
        nodes = api.get_rig_nodes(mesh)
        if nodes['uvpin']:
            self._uvpin_node = nodes['uvpin']
            n = len(api._collect_surface_joints(nodes['uvpin']))
            self._p1_box.set_done('{} ({} joints)'.format(nodes['uvpin'], n))
        if nodes['sk1']:
            self._sk1_node = nodes['sk1']
            self._p2_box.set_done(nodes['sk1'])
        if nodes['bs']:
            self._bs_node = nodes['bs']
            self._p3_box.set_done(nodes['bs'])
        if nodes['sk2']:
            self._sk2_node = nodes['sk2']
            self._p4_box.set_done(nodes['sk2'])

    # ── Phase actions ─────────────────────────────────────────────────────────

    def _run_phase1(self):
        mesh = self._face_mesh()
        if not mesh:
            self._p1_box.set_error('Set a face mesh first.')
            return
        locs = cmds.ls(selection=True) or []
        locs = [l for l in locs if cmds.objExists(l)]
        if not locs:
            self._p1_box.set_error('Select locators in the viewport first.')
            return

        self._p1_btn.setEnabled(False)
        try:
            top_grp, uvpin, results = api.create_surface_joints(
                mesh, locs, ctrl_radius=self._radius_spin.value()
            )
            self._uvpin_node = uvpin
            self._log_msg('Phase 1: {} joints created under {}'.format(len(results), top_grp))
            for pin_grp, ctl, jnt in results:
                self._log_msg('  {} → {} → {}'.format(pin_grp, ctl, jnt))
            self._p1_box.set_done('{} ({} joints)'.format(uvpin, len(results)))
        except Exception as e:
            self._p1_box.set_error(str(e))
            self._log_msg('ERROR phase 1: {}'.format(e))
        finally:
            self._p1_btn.setEnabled(True)

    def _run_phase2(self):
        mesh = self._face_mesh()
        if not mesh:
            self._p2_box.set_error('Set a face mesh first.')
            return
        joints = self._p2_list.items()
        if not joints:
            self._p2_box.set_error('Add skeleton joints to the list first.')
            return

        self._p2_btn.setEnabled(False)
        try:
            sk1 = api.bind_coarse(mesh, joints)
            self._sk1_node = sk1
            self._log_msg('Phase 2: {} created ({} influences)'.format(sk1, len(joints)))
            self._p2_box.set_done(sk1)
        except Exception as e:
            self._p2_box.set_error(str(e))
            self._log_msg('ERROR phase 2: {}'.format(e))
        finally:
            self._p2_btn.setEnabled(True)

    def _run_phase3(self):
        mesh = self._face_mesh()
        if not mesh:
            self._p3_box.set_error('Set a face mesh first.')
            return
        if not self._sk1_node:
            self._p3_box.set_error('Run Phase 2 (Coarse Bind) first.')
            return
        targets = self._p3_list.items()
        if not targets:
            self._p3_box.set_error('Add blendshape target meshes to the list first.')
            return

        self._p3_btn.setEnabled(False)
        try:
            bs = api.add_blendshape(mesh, targets, self._sk1_node)
            self._bs_node = bs
            self._log_msg('Phase 3: {} created ({} targets), reordered after {}'.format(
                bs, len(targets), self._sk1_node))
            self._p3_box.set_done(bs)
        except Exception as e:
            self._p3_box.set_error(str(e))
            self._log_msg('ERROR phase 3: {}'.format(e))
        finally:
            self._p3_btn.setEnabled(True)

    def _run_phase4(self):
        mesh = self._face_mesh()
        if not mesh:
            self._p4_box.set_error('Set a face mesh first.')
            return
        if not self._uvpin_node:
            self._p4_box.set_error('Run Phase 1 (Surface Joints) first.')
            return

        self._p4_btn.setEnabled(False)
        try:
            sk2 = api.bind_surface_joints(mesh, self._uvpin_node)
            self._sk2_node = sk2
            infs = cmds.skinCluster(sk2, query=True, influence=True) or []
            self._log_msg('Phase 4: {} created ({} influences), bindPreMatrix wired'.format(
                sk2, len(infs)))
            self._p4_box.set_done(sk2)
        except Exception as e:
            self._p4_box.set_error(str(e))
            self._log_msg('ERROR phase 4: {}'.format(e))
        finally:
            self._p4_btn.setEnabled(True)


# ── Launch ────────────────────────────────────────────────────────────────────

_instance = None


def show():
    global _instance
    if _instance and not shiboken6.isValid(_instance):
        _instance = None
    if _instance is None:
        _instance = DSFRDialog()
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()

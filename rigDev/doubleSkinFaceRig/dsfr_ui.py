"""
dsfr_ui.py — Double Skin Face Rig UI

Selection-driven 4-step workflow:
  1. Capture/Apply pose from shot file
  2. Prep My Rig (duplicate mesh, wrap blendShape, master group)
  3. Add follicle joints from component selection
  4. Build Rig (SK2 on duplicate mesh)
"""

import sys
import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import dsfr_api as api


def _maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


# ── Main window ──────────────────────────────────────────────────────────────

class DSFRWindow(QtWidgets.QWidget):

    DARK   = '#1e1e1e'
    MID    = '#2a2a2a'
    LIGHT  = '#3a3a3a'
    BORDER = '#4a4a4a'
    TEXT   = '#cccccc'
    DIM    = '#777777'
    ACCENT = '#7a6fa0'
    GREEN  = '#4a7a4a'
    RED    = '#7a3a3a'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Double Skin Face Rig')
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(420)
        self.setStyleSheet(self._stylesheet())

        self._setup = None

        self._build_ui()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._headerLabel('DOUBLE SKIN FACE RIG'))

        # ── Prep Rig ─────────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('PREP RIG'))
        root.addWidget(self._guideLabel(
            'Select the face mesh and click Prep My Rig. This '
            'duplicates the mesh, wraps it to the original, and '
            'sets up the two-mesh architecture needed for the '
            'second skin cluster.'))

        prep_row = QtWidgets.QHBoxLayout()
        prep_row.setContentsMargins(8, 4, 8, 2)
        self._btn_prep = QtWidgets.QPushButton('Prep My Rig')
        self._btn_prep.setMinimumHeight(28)
        self._btn_prep.clicked.connect(self._on_prep)
        prep_row.addWidget(self._btn_prep)
        root.addLayout(prep_row)

        self._prep_status = self._statusLabel()
        root.addWidget(self._prep_status)
        root.addWidget(self._divider())

        # ── Follicles ────────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('FOLLICLES'))
        root.addWidget(self._guideLabel(
            'Select faces, edges, or vertices on the face where you '
            'want fine control, then click Add Selected. Each '
            'component becomes a follicle-driven joint that tracks '
            'the mesh surface. You can add more at any time.'))

        add_row = QtWidgets.QHBoxLayout()
        add_row.setContentsMargins(8, 4, 8, 2)
        self._btn_add = QtWidgets.QPushButton('Add Selected')
        self._btn_add.setMinimumHeight(28)
        self._btn_add.clicked.connect(self._on_add)
        add_row.addWidget(self._btn_add)
        root.addLayout(add_row)

        self._fol_status = self._statusLabel()
        root.addWidget(self._fol_status)
        root.addWidget(self._divider())

        # ── Build ────────────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('BUILD'))
        root.addWidget(self._guideLabel(
            'Creates the second skin cluster on the duplicate mesh. '
            'On first build, joints get default weights. If adding '
            'joints to an existing rig, new joints start at zero '
            'weight so you can paint them in without affecting '
            'existing weights.'))

        build_row = QtWidgets.QHBoxLayout()
        build_row.setContentsMargins(8, 4, 8, 2)
        self._btn_build = QtWidgets.QPushButton('Build Rig')
        self._btn_build.setMinimumHeight(28)
        self._btn_build.setStyleSheet(self._green_btn_style())
        self._btn_build.clicked.connect(self._on_build)
        build_row.addWidget(self._btn_build)
        root.addLayout(build_row)

        self._build_status = self._statusLabel()
        root.addWidget(self._build_status)
        root.addWidget(self._divider())

        # ── Remove ───────────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('REMOVE'))
        root.addWidget(self._guideLabel(
            'Select any part of an existing control (CTL, joint, or '
            'follicle) in the viewport, then click Remove. The skin '
            'cluster is updated automatically if active.'))

        remove_row = QtWidgets.QHBoxLayout()
        remove_row.setContentsMargins(8, 4, 8, 2)
        self._btn_remove = QtWidgets.QPushButton('Remove Selected')
        self._btn_remove.setMinimumHeight(28)
        self._btn_remove.setStyleSheet(self._red_btn_style())
        self._btn_remove.clicked.connect(self._on_remove)
        remove_row.addWidget(self._btn_remove)
        root.addLayout(remove_row)

        self._remove_status = self._statusLabel()
        root.addWidget(self._remove_status)
        root.addWidget(self._divider())

        # ── Log ──────────────────────────────────────────────────────────
        log_header = QtWidgets.QHBoxLayout()
        log_header.setContentsMargins(8, 4, 8, 2)
        log_header.addWidget(self._sectionLabel('LOG'))
        log_header.addStretch()
        clr_btn = QtWidgets.QPushButton('Clear')
        clr_btn.setFixedWidth(42)
        clr_btn.clicked.connect(lambda: self._log.clear())
        log_header.addWidget(clr_btn)
        root.addLayout(log_header)

        self._log = QtWidgets.QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setStyleSheet(
            'QTextEdit { background: #1a1a1a; border: 1px solid %s;'
            'font-family: "Courier New"; font-size: 10px;'
            'color: %s; }' % (self.BORDER, self.TEXT))
        log_wrap = QtWidgets.QHBoxLayout()
        log_wrap.setContentsMargins(8, 0, 8, 8)
        log_wrap.addWidget(self._log)
        root.addLayout(log_wrap)

    # ── Prep Rig ─────────────────────────────────────────────────────────

    def _on_prep(self):
        sel = cmds.ls(selection=True, transforms=True)
        if not sel:
            self._log_msg('Select a face mesh first.', error=True)
            return

        mesh = sel[0]
        try:
            self._setup = api.prep_rig(mesh)
            if self._setup.get('sk2'):
                self._set_status(self._prep_status,
                                 'Existing setup found on {}'.format(mesh))
                self._log_msg('Detected existing DSFR setup on {}'.format(mesh))
            else:
                self._set_status(self._prep_status,
                                 'Prepped: {} → {}'.format(
                                     mesh, self._setup['duplicate']))
                self._log_msg('Prepped rig: duplicate={}, wrap={}'.format(
                    self._setup['duplicate'], self._setup['wrap_bs']))
        except Exception as e:
            self._log_msg('Error prepping rig: {}'.format(e), error=True)

    # ── Follicles ────────────────────────────────────────────────────────

    def _on_add(self):
        if not self._setup:
            self._log_msg('Run Prep My Rig first.', error=True)
            return

        sel = cmds.ls(selection=True, flatten=True) or []
        components = [s for s in sel if '.' in s]
        if not components:
            self._log_msg(
                'Select faces, edges, or vertices on the mesh.',
                error=True)
            return

        try:
            results = api.add_follicle_joint(
                self._setup['original'], components, self._setup)
            self._log_msg('Added {} follicle joints'.format(len(results)))
            for fol, grp, ctl, jnt in results:
                self._log_msg('  {} → {}'.format(ctl, jnt))
        except Exception as e:
            self._log_msg('Error adding joints: {}'.format(e), error=True)

    def _on_remove(self):
        if not self._setup:
            self._log_msg('Run Prep My Rig first.', error=True)
            return

        sel = cmds.ls(selection=True) or []
        if not sel:
            self._log_msg(
                'Select a control, joint, or follicle to remove.',
                error=True)
            return

        grps_to_remove = set()
        for node in sel:
            grp = api.resolve_to_grp(node)
            if grp:
                grps_to_remove.add(grp)

        if not grps_to_remove:
            self._log_msg(
                'Selection is not part of a DSFR follicle rig.',
                error=True)
            return

        for grp in grps_to_remove:
            try:
                api.remove_follicle_joint(self._setup, grp)
                self._log_msg('Removed {}'.format(grp))
            except Exception as e:
                self._log_msg('Error removing {}: {}'.format(grp, e),
                              error=True)

    # ── Build ────────────────────────────────────────────────────────────

    def _on_build(self):
        if not self._setup:
            self._log_msg('Run Prep My Rig first.', error=True)
            return

        try:
            sk2 = api.build_rig(self._setup)
            infs = cmds.skinCluster(sk2, query=True, influence=True) or []
            self._set_status(self._build_status,
                             '{} ({} influences)'.format(sk2, len(infs)))
            self._log_msg('SK2 created: {} ({} influences)'.format(
                sk2, len(infs)))
        except Exception as e:
            self._log_msg('Error building rig: {}'.format(e), error=True)

    # ── Logging ──────────────────────────────────────────────────────────

    def _log_msg(self, msg, error=False):
        color = '#d65f5f' if error else '#6fbf73'
        self._log.append(
            '<span style="color:{}">{}</span>'.format(
                color,
                msg.replace('&', '&amp;').replace('<', '&lt;').replace(
                    '>', '&gt;')))

    # ── UI helpers ───────────────────────────────────────────────────────

    def _set_status(self, label, text, success=True):
        color = '#6fbf73' if success else self.DIM
        label.setText(text)
        label.setStyleSheet(
            'color: %s; font-size: 10px; padding: 2px 8px 6px 8px;' % color)

    def _statusLabel(self):
        lbl = QtWidgets.QLabel('')
        lbl.setStyleSheet(
            'color: %s; font-size: 10px; padding: 2px 8px 6px 8px;' % self.DIM)
        lbl.setWordWrap(True)
        return lbl

    def _guideLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'color: %s; font-size: 10px; padding: 4px 8px 2px 8px;' % self.DIM)
        lbl.setWordWrap(True)
        return lbl

    def _headerLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'background: %s; color: %s; font-size: 11px; font-weight: bold;'
            'padding: 5px; letter-spacing: 1px;' % (self.LIGHT, self.TEXT))
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        return lbl

    def _sectionLabel(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            'background: %s; color: %s; font-size: 10px; font-weight: bold;'
            'padding: 3px 5px; letter-spacing: 1px;' % (self.MID, self.DIM))
        return lbl

    def _divider(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet('color: %s;' % self.BORDER)
        return line

    def _green_btn_style(self):
        return ('QPushButton { background: %s; border: 1px solid %s; }'
                'QPushButton:hover { background: %s; }' % (
                    self.GREEN, self.BORDER, self.ACCENT))

    def _red_btn_style(self):
        return ('QPushButton { background: %s; border: 1px solid %s; }'
                'QPushButton:hover { background: %s; }' % (
                    self.RED, self.BORDER, self.ACCENT))

    def _stylesheet(self):
        return '''
            QWidget {
                background: %(DARK)s;
                color: %(TEXT)s;
                font-family: Arial;
                font-size: 11px;
            }
            QLineEdit {
                background: %(MID)s;
                border: 1px solid %(BORDER)s;
                padding: 3px 5px;
                color: %(TEXT)s;
            }
            QLineEdit:focus {
                border: 1px solid %(ACCENT)s;
            }
            QPushButton {
                background: %(LIGHT)s;
                border: 1px solid %(BORDER)s;
                padding: 4px 10px;
                color: %(TEXT)s;
            }
            QPushButton:hover {
                background: %(ACCENT)s;
            }
            QListWidget {
                background: %(MID)s;
                border: 1px solid %(BORDER)s;
                color: %(TEXT)s;
            }
            QLabel {
                color: %(TEXT)s;
            }
        ''' % {
            'DARK': self.DARK, 'MID': self.MID, 'LIGHT': self.LIGHT,
            'BORDER': self.BORDER, 'TEXT': self.TEXT, 'ACCENT': self.ACCENT,
        }


# ── Launch ───────────────────────────────────────────────────────────────────

_instance = None


def show():
    global _instance
    try:
        _instance.close()
        _instance.deleteLater()
    except Exception:
        pass
    _instance = DSFRWindow(parent=_maya_main_window())
    _instance.show()

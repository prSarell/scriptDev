"""
tlmCorrectiveBS_ui.py — Corrective Blendshape Tool UI

Selection-driven workflow:
  1. Select mesh, pose rig, click Capture
  2. Sculpt the duplicate
  3. Select sculpt mesh, click Bake
  4. Repeat for more shapes
  5. Publish to clean up working meshes
"""

import sys
import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore
    from shiboken2 import wrapInstance

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

import tlmCorrectiveBS_api as api


def _maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


def _is_sculpt_mesh(node):
    if not cmds.objExists(node):
        return False
    return cmds.attributeQuery('correctiveSourceMesh', node=node, exists=True)


def _get_source_mesh(sculpt_mesh):
    if not _is_sculpt_mesh(sculpt_mesh):
        return None
    src = cmds.getAttr(sculpt_mesh + '.correctiveSourceMesh')
    if src and cmds.objExists(src):
        return src
    return None


def _find_sculpt_meshes_for(mesh):
    results = []
    for node in cmds.ls(type='transform'):
        if _is_sculpt_mesh(node):
            src = cmds.getAttr(node + '.correctiveSourceMesh')
            if src == mesh:
                results.append(node)
    return results


def _target_name_from_sculpt(sculpt_mesh):
    name = sculpt_mesh.split('|')[-1].split(':')[-1]
    if name.endswith('_sculpt'):
        return name[:-7]
    return name


# ── Main window ──────────────────────────────────────────────────────────────

class CorrectiveBSWindow(QtWidgets.QWidget):

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
        self.setWindowTitle('Corrective Blendshape Tool')
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setMinimumWidth(420)
        self.setStyleSheet(self._stylesheet())

        self._script_job = None
        self._build_ui()
        self._install_selection_callback()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._headerLabel('CORRECTIVE BLENDSHAPE TOOL'))

        # ── Selection Info ───────────────────────────────────────────────
        root.addWidget(self._sectionLabel('SELECTION'))
        self._sel_mesh_lbl = QtWidgets.QLabel('  Mesh: —')
        self._sel_mesh_lbl.setStyleSheet(
            'color: %s; font-size: 10px; padding: 2px 8px;' % self.TEXT)
        self._sel_sculpt_lbl = QtWidgets.QLabel('  Sculpt: —')
        self._sel_sculpt_lbl.setStyleSheet(
            'color: %s; font-size: 10px; padding: 2px 8px;' % self.TEXT)
        root.addWidget(self._sel_mesh_lbl)
        root.addWidget(self._sel_sculpt_lbl)
        root.addWidget(self._divider())

        # ── Capture Pose ─────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('CAPTURE POSE'))
        root.addWidget(self._guideLabel(
            'Select the mesh, pose the rig to the problem '
            'position, then click Capture. A sculpt duplicate '
            'will be created for you to edit.'))

        cap_row = QtWidgets.QHBoxLayout()
        cap_row.setContentsMargins(8, 4, 8, 2)
        self._btn_capture = QtWidgets.QPushButton('Capture Pose')
        self._btn_capture.setMinimumHeight(28)
        self._btn_capture.clicked.connect(self._on_capture)
        cap_row.addWidget(self._btn_capture)
        root.addLayout(cap_row)

        self._capture_status = self._statusLabel()
        root.addWidget(self._capture_status)
        root.addWidget(self._divider())

        # ── Bake Correction ──────────────────────────────────────────────
        root.addWidget(self._sectionLabel('BAKE CORRECTION'))
        root.addWidget(self._guideLabel(
            'After sculpting, select the sculpt mesh and click '
            'Bake. The tool detects the original mesh and driver '
            'automatically.'))

        bake_row = QtWidgets.QHBoxLayout()
        bake_row.setContentsMargins(8, 4, 8, 2)
        self._btn_bake = QtWidgets.QPushButton('Bake Corrective')
        self._btn_bake.setMinimumHeight(28)
        self._btn_bake.setStyleSheet(self._green_btn_style())
        self._btn_bake.clicked.connect(self._on_bake)
        bake_row.addWidget(self._btn_bake)
        root.addLayout(bake_row)

        self._bake_status = self._statusLabel()
        root.addWidget(self._bake_status)
        root.addWidget(self._divider())

        # ── Targets on Mesh ──────────────────────────────────────────────
        root.addWidget(self._sectionLabel('TARGETS ON MESH'))
        root.addWidget(self._guideLabel(
            'Select a mesh to see its corrective targets. '
            'Select a target to update or delete it.'))

        refresh_row = QtWidgets.QHBoxLayout()
        refresh_row.setContentsMargins(8, 4, 8, 2)
        self._btn_refresh = QtWidgets.QPushButton('Refresh')
        self._btn_refresh.setMinimumHeight(28)
        self._btn_refresh.clicked.connect(self._on_refresh)
        refresh_row.addWidget(self._btn_refresh)
        root.addLayout(refresh_row)

        list_wrap = QtWidgets.QHBoxLayout()
        list_wrap.setContentsMargins(8, 2, 8, 2)
        self._target_list = QtWidgets.QListWidget()
        self._target_list.setFixedHeight(100)
        self._target_list.setStyleSheet(
            'QListWidget { background: %s; border: 1px solid %s; }'
            'QListWidget::item:selected { background: %s; }' % (
                self.MID, self.BORDER, self.ACCENT))
        list_wrap.addWidget(self._target_list)
        root.addLayout(list_wrap)

        target_btn_row = QtWidgets.QHBoxLayout()
        target_btn_row.setContentsMargins(8, 2, 8, 2)
        self._btn_update = QtWidgets.QPushButton('Update Target')
        self._btn_update.setMinimumHeight(28)
        self._btn_update.clicked.connect(self._on_update)
        self._btn_delete = QtWidgets.QPushButton('Delete Target')
        self._btn_delete.setMinimumHeight(28)
        self._btn_delete.setStyleSheet(self._red_btn_style())
        self._btn_delete.clicked.connect(self._on_delete)
        target_btn_row.addWidget(self._btn_update)
        target_btn_row.addWidget(self._btn_delete)
        root.addLayout(target_btn_row)

        self._target_status = self._statusLabel()
        root.addWidget(self._target_status)
        root.addWidget(self._divider())

        # ── Publish ──────────────────────────────────────────────────────
        root.addWidget(self._sectionLabel('PUBLISH'))
        root.addWidget(self._guideLabel(
            'Delete all sculpt and poseRef meshes from the scene '
            'when you are done building correctives.'))

        pub_row = QtWidgets.QHBoxLayout()
        pub_row.setContentsMargins(8, 4, 8, 2)
        self._btn_publish = QtWidgets.QPushButton('Publish')
        self._btn_publish.setMinimumHeight(28)
        self._btn_publish.setStyleSheet(self._red_btn_style())
        self._btn_publish.clicked.connect(self._on_publish)
        pub_row.addWidget(self._btn_publish)
        root.addLayout(pub_row)

        self._publish_status = self._statusLabel()
        root.addWidget(self._publish_status)
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

    # ── Selection callback ───────────────────────────────────────────────

    def _install_selection_callback(self):
        self._script_job = cmds.scriptJob(
            event=['SelectionChanged', self._on_selection_changed])

    def _on_selection_changed(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._sel_mesh_lbl.setText('  Mesh: —')
            self._sel_sculpt_lbl.setText('  Sculpt: —')
            return

        node = sel[0]

        if _is_sculpt_mesh(node):
            src = _get_source_mesh(node)
            target = _target_name_from_sculpt(node)
            self._sel_sculpt_lbl.setText(
                '  Sculpt: %s  (%s)' % (node, target))
            if src:
                self._sel_mesh_lbl.setText('  Mesh: %s' % src)
                self._refresh_targets(src, select_name=target)
            else:
                self._sel_mesh_lbl.setText('  Mesh: — (source not found)')
        else:
            try:
                api.getMeshShape(node)
                sculpts = _find_sculpt_meshes_for(node)
                self._sel_mesh_lbl.setText('  Mesh: %s' % node)
                if sculpts:
                    self._sel_sculpt_lbl.setText(
                        '  Sculpts: %d active (%s)' % (
                            len(sculpts), ', '.join(sculpts)))
                else:
                    self._sel_sculpt_lbl.setText('  Sculpts: none')
                self._refresh_targets(node)
            except api.CorrectiveBSError:
                self._sel_mesh_lbl.setText('  Mesh: — (not a mesh)')
                self._sel_sculpt_lbl.setText('  Sculpt: —')

    def closeEvent(self, event):
        if self._script_job is not None:
            try:
                cmds.scriptJob(kill=self._script_job, force=True)
            except Exception:
                pass
            self._script_job = None
        super().closeEvent(event)

    # ── Capture ──────────────────────────────────────────────────────────

    def _on_capture(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._log_msg('Select a mesh first.', error=True)
            return

        mesh = sel[0]
        try:
            api.getMeshShape(mesh)
        except api.CorrectiveBSError as e:
            self._log_msg(str(e), error=True)
            return

        if _is_sculpt_mesh(mesh):
            self._log_msg(
                'That is a sculpt mesh. Select the original mesh.', error=True)
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, 'Target Name', 'Corrective target name:')
        if not ok or not name.strip():
            return
        name = name.strip()

        existing = api.listCorrectiveTargets(mesh)
        if name in existing:
            self._log_msg(
                'Target "%s" already exists on %s.' % (name, mesh), error=True)
            return

        try:
            dup_a, dup_b, _ = api.startCorrection(mesh, name)
            self._set_status(self._capture_status,
                             'Sculpt on: %s' % dup_a)
            self._log_msg('Captured pose for "%s" on %s' % (name, mesh))
            self._log_msg('  sculpt: %s' % dup_a)
            cmds.select(dup_a, r=True)
        except Exception as e:
            self._log_msg('Capture failed: %s' % e, error=True)

    # ── Bake ─────────────────────────────────────────────────────────────

    def _on_bake(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._log_msg('Select a sculpt mesh first.', error=True)
            return

        sculpt_mesh = sel[0]
        if not _is_sculpt_mesh(sculpt_mesh):
            self._log_msg(
                '%s is not a sculpt mesh. Select a sculpt mesh '
                'created by Capture.' % sculpt_mesh, error=True)
            return

        mesh = _get_source_mesh(sculpt_mesh)
        if not mesh:
            self._log_msg(
                'Source mesh not found for %s.' % sculpt_mesh, error=True)
            return

        target_name = _target_name_from_sculpt(sculpt_mesh)

        vtx_sculpt = cmds.polyEvaluate(sculpt_mesh, vertex=True)
        vtx_mesh = cmds.polyEvaluate(mesh, vertex=True)
        if vtx_sculpt != vtx_mesh:
            self._log_msg(
                'Vertex count mismatch: %s has %d, %s has %d' % (
                    mesh, vtx_mesh, sculpt_mesh, vtx_sculpt), error=True)
            return

        mode, data = api.detectDriverMode(mesh)
        bs_states = None
        custom_driver_attr = None
        custom_driver_value = None

        if mode == 'blendshape':
            bs_states = data
            self._log_msg('Driver: blendshape')
            for attr, val in data:
                self._log_msg('  %s = %.3f' % (attr, val))
        elif mode == 'joint':
            custom_driver_attr, custom_driver_value = data[0]
            self._log_msg('Driver: joint  %s = %.1f' % (
                custom_driver_attr, custom_driver_value))
        else:
            custom_driver_attr, custom_driver_value = self._prompt_driver()
            if custom_driver_attr is None:
                return

        try:
            existing = api.listCorrectiveTargets(mesh)
            if target_name in existing:
                reply = QtWidgets.QMessageBox.question(
                    self, 'Target Exists',
                    '"%s" already exists. Update it?' % target_name,
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if reply == QtWidgets.QMessageBox.Yes:
                    api.updateCorrectiveTarget(mesh, target_name, sculpt_mesh)
                    self._set_status(self._bake_status,
                                     'Updated "%s"' % target_name)
                    self._log_msg('Updated target "%s"' % target_name)
                return

            bs_node, idx = api.bakeCorrection(
                mesh, sculpt_mesh, target_name,
                bs_states=bs_states,
                custom_driver_attr=custom_driver_attr,
                custom_driver_value=custom_driver_value)

            self._set_status(self._bake_status,
                             'Baked "%s" → %s [%d]' % (target_name, bs_node, idx))
            self._log_msg('Baked "%s" → %s [%d]' % (target_name, bs_node, idx))
            self._refresh_targets(mesh, select_name=target_name)
        except Exception as e:
            self._log_msg('Bake failed: %s' % e, error=True)

    def _prompt_driver(self):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle('Driver Required')
        msg.setText(
            'No active blendShapes or joint rotations detected.\n\n'
            'Select a control and highlight an attribute in the\n'
            'Channel Box, then click OK.')
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        if msg.exec_() != QtWidgets.QMessageBox.Ok:
            return None, None

        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('No object selected.', error=True)
            return None, None
        attrs = cmds.channelBox(
            'mainChannelBox', query=True,
            selectedMainAttributes=True) or []
        if not attrs:
            self._log_msg('No attribute selected in Channel Box.', error=True)
            return None, None

        driver_attr = sel[0] + '.' + attrs[0]
        if not cmds.objExists(driver_attr):
            self._log_msg('Attribute not found: ' + driver_attr, error=True)
            return None, None

        driver_val = cmds.getAttr(driver_attr)
        if abs(driver_val) < 1e-4:
            driver_val = 1.0

        self._log_msg('Driver: custom  %s = %.3f' % (driver_attr, driver_val))
        return driver_attr, driver_val

    # ── Target Management ────────────────────────────────────────────────

    def _on_refresh(self):
        sel = cmds.ls(sl=True, transforms=True)
        if not sel:
            self._log_msg('Select a mesh first.', error=True)
            return

        mesh = sel[0]
        if _is_sculpt_mesh(mesh):
            mesh = _get_source_mesh(mesh)
            if not mesh:
                self._log_msg('Source mesh not found.', error=True)
                return

        self._refresh_targets(mesh)

    def _refresh_targets(self, mesh, select_name=None):
        self._target_list.clear()
        targets = api.listCorrectiveTargets(mesh)
        for name in targets:
            self._target_list.addItem(name)
        self._target_list.setProperty('mesh', mesh)
        if select_name:
            for i in range(self._target_list.count()):
                if self._target_list.item(i).text() == select_name:
                    self._target_list.setCurrentRow(i)
                    break

    def _on_update(self):
        items = self._target_list.selectedItems()
        sel = cmds.ls(sl=True, transforms=True)

        if not items and sel and _is_sculpt_mesh(sel[0]):
            target_name = _target_name_from_sculpt(sel[0])
            mesh = _get_source_mesh(sel[0])
            sculpt_mesh = sel[0]
            if not mesh:
                self._log_msg('Source mesh not found for %s.' % sculpt_mesh,
                              error=True)
                return
            self._refresh_targets(mesh, select_name=target_name)
        elif items:
            target_name = items[0].text()
            mesh = self._target_list.property('mesh')
            if not mesh or not cmds.objExists(mesh):
                self._log_msg('Refresh the target list first.', error=True)
                return
            sculpt_mesh = None
            if sel and _is_sculpt_mesh(sel[0]):
                sculpt_mesh = sel[0]
            else:
                fallback = target_name + '_sculpt'
                if cmds.objExists(fallback):
                    sculpt_mesh = fallback
            if not sculpt_mesh:
                self._log_msg(
                    'Select a sculpt mesh or ensure %s_sculpt exists.'
                    % target_name, error=True)
                return
        else:
            self._log_msg(
                'Select a target from the list, or select a sculpt mesh '
                'in the viewport.', error=True)
            return

        try:
            api.updateCorrectiveTarget(mesh, target_name, sculpt_mesh)
            self._set_status(self._target_status,
                             'Updated "%s"' % target_name)
            self._log_msg('Updated target "%s"' % target_name)
        except Exception as e:
            self._log_msg('Update failed: %s' % e, error=True)

    def _on_delete(self):
        items = self._target_list.selectedItems()
        sel = cmds.ls(sl=True, transforms=True)

        if not items and sel and _is_sculpt_mesh(sel[0]):
            target_name = _target_name_from_sculpt(sel[0])
            mesh = _get_source_mesh(sel[0])
            if not mesh:
                self._log_msg('Source mesh not found for %s.' % sel[0],
                              error=True)
                return
        elif items:
            target_name = items[0].text()
            mesh = self._target_list.property('mesh')
            if not mesh or not cmds.objExists(mesh):
                self._log_msg('Refresh the target list first.', error=True)
                return
        else:
            self._log_msg(
                'Select a target from the list, or select a sculpt mesh '
                'in the viewport.', error=True)
            return

        confirm = QtWidgets.QMessageBox.question(
            self, 'Delete Target',
            'Delete corrective target "%s"?' % target_name,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        try:
            api.removeCorrectiveTarget(mesh, target_name)
            for suffix in ('_sculpt', '_poseRef'):
                node = target_name + suffix
                if cmds.objExists(node):
                    cmds.delete(node)
            self._refresh_targets(mesh)
            if self._target_list.count():
                self._target_list.setCurrentRow(0)
            self._set_status(self._target_status,
                             'Deleted "%s"' % target_name)
            self._log_msg('Deleted target "%s"' % target_name)
        except Exception as e:
            self._log_msg('Delete failed: %s' % e, error=True)

    # ── Publish ──────────────────────────────────────────────────────────

    def _on_publish(self):
        sculpts = [n for n in cmds.ls(type='transform')
                   if _is_sculpt_mesh(n)]
        pose_refs = [n for n in cmds.ls(type='transform')
                     if n.endswith('_poseRef') and
                     cmds.attributeQuery('correctiveFrame', node=n, exists=True)]

        to_delete = sculpts + pose_refs
        if not to_delete:
            self._log_msg('No working meshes to clean up.')
            return

        confirm = QtWidgets.QMessageBox.question(
            self, 'Publish',
            'Delete %d working mesh(es)?\n\n%s' % (
                len(to_delete), '\n'.join(to_delete)),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        count = 0
        for node in to_delete:
            if cmds.objExists(node):
                cmds.delete(node)
                count += 1

        self._set_status(self._publish_status,
                         'Cleaned up %d mesh(es)' % count)
        self._log_msg('Published: deleted %d working meshes' % count)

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
    _instance = CorrectiveBSWindow(parent=_maya_main_window())
    _instance.show()

"""mh_body_clean_ui.py — PySide6 UI for Metahuman body scene cleanup."""
import os
import maya.cmds as cmds
import maya.OpenMayaUI as omui
import shiboken6
from PySide6 import QtWidgets, QtCore, QtGui
import mh_body_clean_api as api

WINDOW_TITLE = 'MH Body Clean'
WINDOW_OBJ   = 'mhBodyCleanUI'


def _maya_main_window():
    return shiboken6.wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


class MhBodyCleanUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(WINDOW_OBJ)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.Tool)
        self._tex_paths = {k: None for k in ('eyes', 'head', 'teeth', 'body')}
        self._build_ui()
        self._refresh_lods()
        self._auto_scan_maps()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(8, 8, 8, 8)

        # ── LODs ──────────────────────────────────────────────────────────────
        lod_box = QtWidgets.QGroupBox('Body LODs')
        lod_lay = QtWidgets.QVBoxLayout(lod_box)
        lod_lay.setSpacing(4)

        self._lod_checks = {}
        for i in range(5):
            cb = QtWidgets.QCheckBox('LOD {}{}'.format(
                i, '  —  keep (default)' if i == 0 else ''))
            cb.setChecked(i == 0)   # LOD 0 = keep by default, rest = delete
            self._lod_checks[i] = cb
            lod_lay.addWidget(cb)

        btn_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton('Refresh')
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._refresh_lods)
        self._del_lods_btn = QtWidgets.QPushButton('Delete Unchecked LODs')
        self._del_lods_btn.setMinimumHeight(28)
        self._del_lods_btn.clicked.connect(self._on_delete_lods)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(self._del_lods_btn)
        lod_lay.addLayout(btn_row)
        outer.addWidget(lod_box)

        # ── Lights ────────────────────────────────────────────────────────────
        lights_box = QtWidgets.QGroupBox('Unreal Lights')
        lights_lay = QtWidgets.QVBoxLayout(lights_box)
        del_lights_btn = QtWidgets.QPushButton('Delete Unreal Lights')
        del_lights_btn.setMinimumHeight(28)
        del_lights_btn.clicked.connect(self._on_delete_lights)
        lights_lay.addWidget(del_lights_btn)
        outer.addWidget(lights_box)

        # ── Textures ──────────────────────────────────────────────────────────
        tex_box = QtWidgets.QGroupBox('Textures')
        tex_lay = QtWidgets.QVBoxLayout(tex_box)
        tex_lay.setSpacing(6)

        # Maps folder row
        folder_row = QtWidgets.QHBoxLayout()
        self._maps_field = QtWidgets.QLineEdit()
        self._maps_field.setPlaceholderText('Path to maps folder...')
        browse_btn = QtWidgets.QPushButton('Browse...')
        browse_btn.setFixedWidth(72)
        browse_btn.clicked.connect(self._browse_maps)
        scan_btn = QtWidgets.QPushButton('Scan')
        scan_btn.setFixedWidth(50)
        scan_btn.clicked.connect(self._on_scan_textures)
        folder_row.addWidget(self._maps_field)
        folder_row.addWidget(browse_btn)
        folder_row.addWidget(scan_btn)
        tex_lay.addLayout(folder_row)

        # Texture status rows
        self._tex_labels = {}
        grid = QtWidgets.QFormLayout()
        grid.setSpacing(4)
        for key, label in (('eyes', 'Eyes:'), ('head', 'Head:'),
                            ('teeth', 'Teeth:'), ('body', 'Body:')):
            lbl = QtWidgets.QLabel('—')
            lbl.setWordWrap(True)
            self._tex_labels[key] = lbl
            grid.addRow(label, lbl)
        tex_lay.addLayout(grid)

        assign_btn = QtWidgets.QPushButton('Assign Textures')
        assign_btn.setMinimumHeight(28)
        assign_btn.clicked.connect(self._on_assign_textures)
        tex_lay.addWidget(assign_btn)
        outer.addWidget(tex_box)

        # ── log ───────────────────────────────────────────────────────────────
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(72)
        self._log.setPlaceholderText('Messages...')
        outer.addWidget(self._log)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)

    def _refresh_lods(self):
        lods = api.find_lods()
        for idx, cb in self._lod_checks.items():
            exists = lods.get(idx, False)
            cb.setEnabled(exists)
            if not exists:
                cb.setText('LOD {} — not in scene'.format(idx))
            else:
                cb.setText('LOD {}{}'.format(
                    idx, '  —  keep (default)' if idx == 0 else ''))

    def _auto_scan_maps(self):
        folder = api.auto_maps_folder()
        if folder:
            self._maps_field.setText(folder)
            self._on_scan_textures()

    def _update_tex_labels(self):
        for key, lbl in self._tex_labels.items():
            path = self._tex_paths.get(key)
            if path:
                lbl.setText(os.path.basename(path))
                lbl.setStyleSheet('color: #88cc88;')
            else:
                lbl.setText('not found')
                lbl.setStyleSheet('color: #cc8888;')

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_delete_lods(self):
        to_delete = [i for i, cb in self._lod_checks.items()
                     if cb.isEnabled() and not cb.isChecked()]
        if not to_delete:
            self._log_msg('LODs: nothing to delete.')
            return
        deleted = api.delete_lods(to_delete)
        for name in deleted:
            self._log_msg('Deleted: {}'.format(name))
        self._log_msg('LODs done — {} group(s) removed.'.format(len(deleted)))
        self._refresh_lods()

    def _on_delete_lights(self):
        found = api.delete_lights()
        if found:
            self._log_msg('Deleted Unreal Lights group.')
        else:
            self._log_msg('Lights: group "{}" not found in scene.'.format('Lights'))

    def _browse_maps(self):
        current = self._maps_field.text().strip()
        start   = current if os.path.isdir(current) else ''
        folder  = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select maps folder', start)
        if folder:
            self._maps_field.setText(folder)
            self._on_scan_textures()

    def _on_scan_textures(self):
        folder = self._maps_field.text().strip()
        if not folder:
            self._log_msg('Textures: enter or browse to a maps folder first.')
            return
        if not os.path.isdir(folder):
            self._log_msg('Textures: folder not found — {}'.format(folder))
            return
        self._tex_paths = api.scan_textures(folder)
        self._update_tex_labels()
        found  = sum(1 for v in self._tex_paths.values() if v)
        self._log_msg('Textures scanned: {}/4 found.'.format(found))

    def _on_assign_textures(self):
        if not any(self._tex_paths.values()):
            self._log_msg('Textures: scan a maps folder first.')
            return
        report = api.assign_textures(self._tex_paths)
        for key, info in report.items():
            meshes = info.get('meshes', [])
            self._log_msg('{}: shader "{}" → {} mesh(es).'.format(
                key, info.get('shader', '?'), len(meshes)))
            if not meshes:
                self._log_msg('  WARNING: no matching mesh found for {}.'.format(key))
        self._log_msg('Textures assigned.')


# ── show ──────────────────────────────────────────────────────────────────────

_instance = None


def show():
    global _instance
    parent = _maya_main_window()
    if _instance and not shiboken6.isValid(_instance):
        _instance = None
    if _instance is None:
        _instance = MhBodyCleanUI(parent)
    _instance.show()
    _instance.raise_()
    _instance.activateWindow()
    return _instance

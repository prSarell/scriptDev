import os
import json
import maya.cmds as cmds
from PySide6 import QtWidgets, QtCore
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui


_CONFIG_FILENAME = 'mpAnim_config.json'


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _config_file():
    prefs = cmds.internalVar(userPrefDir=True)
    return os.path.join(prefs, _CONFIG_FILENAME).replace('\\', '/')


def _load():
    path = _config_file()
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(config):
    path = _config_file()
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)


def get_save_path():
    """Return the configured save path. Shows setup dialog if not yet configured.
    Returns None if the user cancels."""
    config = _load()
    save_path = config.get('save_path', '').strip()
    if save_path:
        return save_path
    return show_settings()


def get_shot_cam():
    """Return the configured shot camera name, defaulting to 'camera1'."""
    return _load().get('shot_cam', 'camera1').strip() or 'camera1'


def set_shot_cam(name):
    config = _load()
    config['shot_cam'] = name.strip()
    _save(config)


def show_settings():
    """Open the path configuration dialog. Returns the saved path or None."""
    dlg = _ConfigDialog(_maya_main_window())
    if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        config = _load()
        config['save_path'] = dlg.chosen_path()
        config['shot_cam']  = dlg.chosen_cam()
        _save(config)
        os.makedirs(dlg.chosen_path(), exist_ok=True)
        return dlg.chosen_path()
    return None


class _ConfigDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('mpAnim — Save Location')
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

        cfg = _load()
        existing      = cfg.get('save_path', '').strip()
        existing_cam  = cfg.get('shot_cam', 'camera1').strip()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        info = QtWidgets.QLabel(
            'Choose a folder where mpAnim tools will save your data '
            '(hotkey presets, settings, etc.).\n\n'
            'RMIT students: navigate to your H: drive.'
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        path_row = QtWidgets.QHBoxLayout()
        path_row.setSpacing(6)
        self._path_field = QtWidgets.QLineEdit(existing)
        self._path_field.setPlaceholderText('e.g.  H:/maya/mpAnim')
        path_row.addWidget(self._path_field)

        browse_btn = QtWidgets.QPushButton('...')
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        cam_lbl = QtWidgets.QLabel('Shot camera name:')
        layout.addWidget(cam_lbl)
        self._cam_field = QtWidgets.QLineEdit(existing_cam)
        self._cam_field.setPlaceholderText('e.g.  camera1  or  shotCam')
        layout.addWidget(self._cam_field)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QtWidgets.QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QtWidgets.QPushButton('Save && Continue')
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        current = self._path_field.text().strip() or os.path.expanduser('~')
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Save Folder', current)
        if chosen:
            self._path_field.setText(chosen.replace('\\', '/'))

    def _on_save(self):
        if not self._path_field.text().strip():
            QtWidgets.QMessageBox.warning(self, 'mpAnim', 'Please enter a save path.')
            return
        self.accept()

    def chosen_path(self):
        return self._path_field.text().strip().replace('\\', '/')

    def chosen_cam(self):
        return self._cam_field.text().strip() or 'camera1'

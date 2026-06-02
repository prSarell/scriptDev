import os
import json
import maya.cmds as cmds
import maya.mel as mel
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui

import mpAnimConfig

WINDOW_NAME  = 'mpAnimShortCuts'
PRESETS_FILE = 'shortcuts_presets.json'

# ---------------------------------------------------------------------------
# Master hotkey definitions
# ---------------------------------------------------------------------------

HOTKEYS = [
    {
        'id':         'frame_back',
        'key':        'z',
        'label':      'Z',
        'desc':       'Step back one frame',
        'py_command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True) - 1)',
    },
    {
        'id':         'frame_forward',
        'key':        'x',
        'label':      'X',
        'desc':       'Step forward one frame',
        'py_command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True) + 1)',
    },
    {
        'id':      'spacebar_play',
        'key':     ' ',
        'label':   'Space',
        'desc':    'Toggle play',
        'special': True,
        'warn':    'Overrides panePopAt — tap plays, hold 10s shows hotbox',
    },
]

_DEFAULT_PRESET = {
    'name':    'ps_anim',
    'enabled': {h['id']: True for h in HOTKEYS},
}

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_BG      = '#282828'
_BG_SIDE = '#212121'
_BG_HEAD = '#1c1c1c'
_FG      = 'rgba(255,255,255,175)'
_FG_DIM  = 'rgba(255,255,255,80)'
_ACCENT  = '#4D90D4'
_ACCENT2 = '#3a6fa8'
_HOVER   = 'rgba(255,255,255,18)'
_SEL     = 'rgba(77,144,212,200)'
_BORDER  = 'rgba(255,255,255,12)'

STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_FG};
    font-size: 12px;
    border: none;
}}

/* Header */
#header {{
    background-color: {_BG_HEAD};
    border-bottom: 1px solid {_BORDER};
    min-height: 32px;
    max-height: 32px;
}}
#headerTitle {{
    color: rgba(255,255,255,200);
    font-size: 13px;
    font-weight: bold;
    background: transparent;
    padding-left: 10px;
}}
#headerSettings {{
    background: transparent;
    color: {_FG_DIM};
    font-size: 14px;
    padding: 0px 8px;
    min-width: 28px;
    max-width: 28px;
}}
#headerSettings:hover {{ color: {_FG}; background: {_HOVER}; }}

/* Sidebar */
#sidebar {{
    background-color: {_BG_SIDE};
    border-right: 1px solid {_BORDER};
    min-width: 120px;
    max-width: 120px;
}}

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px 0px;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 0px;
    color: {_FG};
}}
QListWidget::item:hover {{
    background-color: {_HOVER};
}}
QListWidget::item:selected {{
    background-color: {_SEL};
    color: white;
}}

/* Sidebar footer buttons */
#sidebarBtn {{
    background: transparent;
    color: {_FG_DIM};
    font-size: 16px;
    padding: 4px;
    min-width: 28px;
    max-width: 28px;
    min-height: 24px;
}}
#sidebarBtn:hover {{ color: {_FG}; background: {_HOVER}; }}

/* Content area */
#content {{
    background-color: {_BG};
    padding: 8px 12px;
}}

/* Hotkey rows */
#hotkeyRow {{
    background: transparent;
    min-height: 34px;
    max-height: 34px;
    border-bottom: 1px solid {_BORDER};
    padding: 0px 4px;
}}
QCheckBox {{
    background: transparent;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1px solid rgba(255,255,255,60);
    background: rgba(255,255,255,10);
}}
QCheckBox::indicator:checked {{
    background: {_ACCENT};
    border-color: {_ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {_ACCENT};
}}
#keyLabel {{
    color: white;
    font-weight: bold;
    font-size: 12px;
    min-width: 46px;
    max-width: 46px;
    background: rgba(255,255,255,12);
    border-radius: 3px;
    padding: 2px 6px;
}}
#descLabel {{
    color: {_FG};
}}
#warnLabel {{
    color: #CC9900;
    font-size: 13px;
}}

/* Footer */
#footer {{
    background-color: {_BG_HEAD};
    border-top: 1px solid {_BORDER};
    min-height: 42px;
    max-height: 42px;
    padding: 0px 8px;
}}
#applyBtn {{
    background-color: {_ACCENT};
    color: white;
    font-weight: bold;
    border-radius: 2px;
    padding: 4px 16px;
    min-height: 26px;
}}
#applyBtn:hover {{ background-color: {_ACCENT2}; }}
#resetBtn {{
    background-color: rgba(255,255,255,15);
    color: {_FG};
    border-radius: 2px;
    padding: 4px 16px;
    min-height: 26px;
}}
#resetBtn:hover {{ background-color: rgba(255,255,255,30); }}

QScrollBar:vertical {{
    width: 6px;
    background: transparent;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,30);
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255,255,255,60);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
"""

# ---------------------------------------------------------------------------
# Preset file I/O
# ---------------------------------------------------------------------------

def _presets_file():
    path = mpAnimConfig.get_save_path()
    if not path:
        return None
    folder = os.path.join(path, 'shortcuts')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, PRESETS_FILE)


def _load_data():
    f = _presets_file()
    if f and os.path.exists(f):
        try:
            with open(f, 'r') as fh:
                return json.load(fh)
        except Exception:
            pass
    return {
        'presets':           [dict(_DEFAULT_PRESET, enabled=dict(_DEFAULT_PRESET['enabled']))],
        'active':            _DEFAULT_PRESET['name'],
        'original_bindings': {},
    }


def _save_data(data):
    f = _presets_file()
    if f:
        with open(f, 'w') as fh:
            json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Hotkey apply / reset
# ---------------------------------------------------------------------------

def _key_slug(key):
    return 'space' if key == ' ' else key


def _save_original(key, data):
    slug = _key_slug(key)
    ob = data.setdefault('original_bindings', {})
    if slug in ob:
        return
    try:
        press   = cmds.hotkey(key=key, query=True, name=True)        or ''
        release = cmds.hotkey(key=key, query=True, releaseName=True) or ''
    except Exception:
        press, release = '', ''
    ob[slug] = {'press': press, 'release': release}


def _ensure_name_command(hk):
    rtc = 'mpAnim_' + hk['id']
    nc  = rtc + '_NC'

    # Create or update the runtime command (supports exists query and edit)
    if cmds.runTimeCommand(rtc, query=True, exists=True):
        cmds.runTimeCommand(rtc, edit=True,
                            annotation=hk['desc'],
                            command=hk['py_command'],
                            commandLanguage='python')
    else:
        cmds.runTimeCommand(rtc,
                            annotation=hk['desc'],
                            command=hk['py_command'],
                            commandLanguage='python')

    # nameCommand bridges the runtime command to a hotkey slot
    try:
        cmds.nameCommand(nc, annotation=hk['desc'], command=rtc)
    except Exception:
        pass  # Already exists — runtime command was updated above so it's current

    return nc


_space_filter = None
_HOLD_MS      = 400  # tap vs hold threshold in ms


class _SpacePlayFilter(QtCore.QObject):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed = False
        self._held    = False
        self._timer   = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(_HOLD_MS)
        self._timer.timeout.connect(self._on_hold)

    def _on_hold(self):
        self._held = True
        mel.eval('hotBox')

    def eventFilter(self, obj, event):
        t = event.type()
        if t not in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            return False
        if event.key() != QtCore.Qt.Key.Key_Space:
            return False
        if event.isAutoRepeat():
            return True
        if t == QtCore.QEvent.Type.KeyPress and not self._pressed:
            self._pressed = True
            self._held    = False
            self._timer.start()
            return True
        if t == QtCore.QEvent.Type.KeyRelease and self._pressed:
            self._pressed = False
            if self._held:
                self._held = False
                mel.eval('hotBox -release')
            else:
                self._timer.stop()
                mel.eval('togglePlayback')
            return True
        return False


def _bind_spacebar():
    global _space_filter
    _restore_spacebar()
    app = QtWidgets.QApplication.instance()
    _space_filter = _SpacePlayFilter(app)
    app.installEventFilter(_space_filter)


def _restore_spacebar():
    global _space_filter
    if _space_filter is not None:
        QtWidgets.QApplication.instance().removeEventFilter(_space_filter)
        _space_filter = None


def _set_key(key, press, release=''):
    try:
        cmds.hotkey(key=key, name=press, releaseName=release)
    except Exception as e:
        cmds.warning('shortCuts: could not bind "{}" — {}'.format(key, e))


def _restore_key(key, data):
    slug = _key_slug(key)
    ob   = data.get('original_bindings', {}).get(slug, {})
    _set_key(key, ob.get('press', ''), ob.get('release', ''))


def apply_preset(preset, data):
    for hk in HOTKEYS:
        enabled = preset['enabled'].get(hk['id'], False)
        if hk.get('special'):
            if hk['id'] == 'spacebar_play':
                _bind_spacebar() if enabled else _restore_spacebar()
        else:
            key = hk['key']
            _save_original(key, data)
            if enabled:
                _set_key(key, _ensure_name_command(hk))
            else:
                _restore_key(key, data)
    data['active'] = preset['name']
    _save_data(data)
    cmds.inViewMessage(
        amg='Preset <hl>{}</hl> applied.'.format(preset['name']),
        pos='midCenter', fade=True)


def reset_all(data):
    for hk in HOTKEYS:
        if hk.get('special'):
            if hk['id'] == 'spacebar_play':
                _restore_spacebar()
        else:
            _restore_key(hk['key'], data)
    _save_data(data)
    cmds.inViewMessage(amg='Hotkeys reset to Maya defaults.', pos='midCenter', fade=True)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class ShortCutsUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('shortCuts')
        self.setObjectName(WINDOW_NAME)
        self.setMinimumSize(400, 280)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window |
            QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(STYLESHEET)

        self._data       = _load_data()
        self._checkboxes = {}

        self._build_ui()
        self._refresh_list(select=self._data.get('active'))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._make_sidebar())
        body.addWidget(self._make_content(), 1)
        root.addLayout(body, 1)

        root.addWidget(self._make_footer())

    def _make_header(self):
        w = QtWidgets.QWidget()
        w.setObjectName('header')
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        title = QtWidgets.QLabel('shortCuts')
        title.setObjectName('headerTitle')
        row.addWidget(title, 1)

        gear = QtWidgets.QPushButton('⚙')
        gear.setObjectName('headerSettings')
        gear.setToolTip('Save location settings')
        gear.clicked.connect(mpAnimConfig.show_settings)
        row.addWidget(gear)
        return w

    def _make_sidebar(self):
        w = QtWidgets.QWidget()
        w.setObjectName('sidebar')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QtWidgets.QListWidget()
        self._list.currentTextChanged.connect(self._on_preset_changed)
        layout.addWidget(self._list, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(4, 4, 4, 4)
        btn_row.setSpacing(2)

        add_btn = QtWidgets.QPushButton('+')
        add_btn.setObjectName('sidebarBtn')
        add_btn.setToolTip('New preset (copies current)')
        add_btn.clicked.connect(self._new_preset)
        btn_row.addWidget(add_btn)

        del_btn = QtWidgets.QPushButton('✕')
        del_btn.setObjectName('sidebarBtn')
        del_btn.setToolTip('Delete preset')
        del_btn.clicked.connect(self._delete_preset)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _make_content(self):
        w = QtWidgets.QWidget()
        w.setObjectName('content')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        inner = QtWidgets.QWidget()
        inner_layout = QtWidgets.QVBoxLayout(inner)
        inner_layout.setContentsMargins(12, 8, 12, 8)
        inner_layout.setSpacing(0)

        for hk in HOTKEYS:
            inner_layout.addWidget(self._make_hotkey_row(hk))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return w

    def _make_hotkey_row(self, hk):
        row = QtWidgets.QWidget()
        row.setObjectName('hotkeyRow')
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(10)

        cb = QtWidgets.QCheckBox()
        self._checkboxes[hk['id']] = cb
        h.addWidget(cb)

        key_lbl = QtWidgets.QLabel(hk['label'])
        key_lbl.setObjectName('keyLabel')
        key_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        h.addWidget(key_lbl)

        desc_lbl = QtWidgets.QLabel(hk['desc'])
        desc_lbl.setObjectName('descLabel')
        h.addWidget(desc_lbl, 1)

        if 'warn' in hk:
            warn = QtWidgets.QLabel('⚠')
            warn.setObjectName('warnLabel')
            warn.setToolTip(hk['warn'])
            h.addWidget(warn)

        return row

    def _make_footer(self):
        w = QtWidgets.QWidget()
        w.setObjectName('footer')
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(8)
        row.addStretch()

        reset_btn = QtWidgets.QPushButton('Reset to Maya')
        reset_btn.setObjectName('resetBtn')
        reset_btn.clicked.connect(self._reset)
        row.addWidget(reset_btn)

        apply_btn = QtWidgets.QPushButton('Apply Preset')
        apply_btn.setObjectName('applyBtn')
        apply_btn.clicked.connect(self._apply)
        row.addWidget(apply_btn)
        return w

    # ------------------------------------------------------------------
    # Preset management
    # ------------------------------------------------------------------

    def _refresh_list(self, select=None):
        self._list.blockSignals(True)
        self._list.clear()
        for p in self._data['presets']:
            self._list.addItem(p['name'])
        target = select or (self._data['presets'][0]['name'] if self._data['presets'] else '')
        items = self._list.findItems(target, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            self._list.setCurrentItem(items[0])
        self._list.blockSignals(False)
        self._load_checkboxes()

    def _current_preset(self):
        item = self._list.currentItem()
        if not item:
            return None
        name = item.text()
        return next((p for p in self._data['presets'] if p['name'] == name), None)

    def _load_checkboxes(self):
        preset = self._current_preset()
        if not preset:
            return
        for hk in HOTKEYS:
            self._checkboxes[hk['id']].setChecked(
                preset['enabled'].get(hk['id'], False))

    def _sync_checkboxes(self):
        preset = self._current_preset()
        if preset:
            for hk in HOTKEYS:
                preset['enabled'][hk['id']] = self._checkboxes[hk['id']].isChecked()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_preset_changed(self, _name):
        self._load_checkboxes()

    def _apply(self):
        self._sync_checkboxes()
        preset = self._current_preset()
        if preset:
            apply_preset(preset, self._data)

    def _reset(self):
        reset_all(self._data)

    def _new_preset(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, 'New Preset', 'Preset name:', text='My Preset')
        if not ok or not name.strip():
            return
        name = name.strip()
        if any(p['name'] == name for p in self._data['presets']):
            QtWidgets.QMessageBox.warning(
                self, 'shortCuts', '"{}" already exists.'.format(name))
            return
        current  = self._current_preset()
        enabled  = dict(current['enabled']) if current else {h['id']: False for h in HOTKEYS}
        self._data['presets'].append({'name': name, 'enabled': enabled})
        _save_data(self._data)
        self._refresh_list(select=name)

    def _delete_preset(self):
        preset = self._current_preset()
        if not preset:
            return
        if len(self._data['presets']) <= 1:
            QtWidgets.QMessageBox.warning(self, 'shortCuts', 'Cannot delete the last preset.')
            return
        reply = QtWidgets.QMessageBox.question(
            self, 'Delete Preset', 'Delete "{}"?'.format(preset['name']),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._data['presets'].remove(preset)
        if self._data.get('active') == preset['name']:
            self._data['active'] = self._data['presets'][0]['name']
        _save_data(self._data)
        self._refresh_list(select=self._data['active'])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def show():
    parent = _maya_main_window()
    for child in parent.findChildren(QtWidgets.QDialog, WINDOW_NAME):
        child.close()
        child.deleteLater()
    ui = ShortCutsUI(parent)
    ui.show()

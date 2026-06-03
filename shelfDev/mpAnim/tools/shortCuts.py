import os
import json
import maya.cmds as cmds
import maya.mel as mel
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui
import mpAnimConfig

WINDOW_NAME  = 'mpAnimShortCuts'
DATA_FILE    = 'shortcuts_data.json'
_BUILTIN_SET = 'Maya_Default'
_HOLD_MS     = 400

# ---------------------------------------------------------------------------
# Keyboard layout  (display_label, maya keyShortcut value) | None = visual gap
# ---------------------------------------------------------------------------
_KB_FN = [
    ('F1','F1'),('F2','F2'),('F3','F3'),('F4','F4'), None,
    ('F5','F5'),('F6','F6'),('F7','F7'),('F8','F8'), None,
    ('F9','F9'),('F10','F10'),('F11','F11'),('F12','F12'),
]
_KB_NUM = [
    ('`','`'),('1','1'),('2','2'),('3','3'),('4','4'),('5','5'),
    ('6','6'),('7','7'),('8','8'),('9','9'),('0','0'),('-','-'),('=','='),
]
_KB_Q = [
    ('Q','q'),('W','w'),('E','e'),('R','r'),('T','t'),('Y','y'),
    ('U','u'),('I','i'),('O','o'),('P','p'),('[','['),(']',']'),('\\','\\'),
]
_KB_A = [
    ('A','a'),('S','s'),('D','d'),('F','f'),('G','g'),('H','h'),
    ('J','j'),('K','k'),('L','l'),(';',';'),("'","'"),
]
_KB_Z = [
    ('Z','z'),('X','x'),('C','c'),('V','v'),('B','b'),('N','n'),
    ('M','m'),(',',','),('.','.'),('/','/')
]

KB_ROWS  = [_KB_FN, _KB_NUM, _KB_Q, _KB_A, _KB_Z]
# Row pixel offsets to mimic keyboard stagger (applied as left margin)
KB_OFFSETS = [0, 0, 12, 18, 28]

ALL_KEYS = [e[1] for row in KB_ROWS for e in row if e is not None]

_SEED_HOTKEYS = [
    {
        'key': 'z', 'alt': False, 'ctrl': False, 'shift': False,
        'desc': 'Step back one frame',
        'command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True)-1)',
        'lang': 'python',
    },
    {
        'key': 'x', 'alt': False, 'ctrl': False, 'shift': False,
        'desc': 'Step forward one frame',
        'command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True)+1)',
        'lang': 'python',
    },
]

# ---------------------------------------------------------------------------
# Colours & Stylesheet
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

_K_FREE   = '#1e3d1e'; _K_FREE_H  = '#2a5a2a'
_K_MINE   = '#1a2d4a'; _K_MINE_H  = '#2a4a6a'
_K_MUTED  = '#3a2550'; _K_MUTED_H = '#50356a'
_K_DEF    = '#323232'; _K_DEF_H   = '#484848'
_K_SEL    = '#4D90D4'; _K_SEL_H   = '#5ca0e4'

STYLESHEET = f"""
QWidget {{
    background-color: {_BG};
    color: {_FG};
    font-size: 12px;
    border: none;
}}

/* ── Header ── */
#header {{
    background-color: {_BG_HEAD};
    border-bottom: 1px solid {_BORDER};
    min-height: 32px; max-height: 32px;
}}
#headerTitle {{
    color: rgba(255,255,255,200); font-size: 13px; font-weight: bold;
    background: transparent; padding-left: 10px;
}}
#headerSettings {{
    background: transparent; color: {_FG_DIM}; font-size: 14px;
    padding: 0px 8px; min-width: 28px; max-width: 28px;
}}
#headerSettings:hover {{ color: {_FG}; background: {_HOVER}; }}

/* ── Sidebar ── */
#sidebar {{
    background-color: {_BG_SIDE};
    border-right: 1px solid {_BORDER};
    min-width: 130px; max-width: 130px;
}}
QListWidget {{
    background-color: transparent; border: none; outline: none; padding: 4px 0px;
}}
QListWidget::item {{ padding: 6px 10px; color: {_FG}; }}
QListWidget::item:hover {{ background-color: {_HOVER}; }}
QListWidget::item:selected {{ background-color: {_SEL}; color: white; }}

#sidebarBtn {{
    background: transparent; color: {_FG_DIM}; font-size: 16px;
    padding: 4px; min-width: 28px; max-width: 28px; min-height: 24px;
}}
#sidebarBtn:hover {{ color: {_FG}; background: {_HOVER}; }}
#applyBtn {{
    background-color: {_ACCENT}; color: white; font-weight: bold;
    border-radius: 2px; padding: 3px 10px; min-height: 24px; margin: 4px;
}}
#applyBtn:hover {{ background-color: {_ACCENT2}; }}

/* ── Hotkey rows ── */
#hotkeyRow {{
    background: transparent; min-height: 32px; max-height: 32px;
    border-bottom: 1px solid {_BORDER};
}}
QCheckBox {{ background: transparent; spacing: 6px; }}
QCheckBox::indicator {{
    width: 13px; height: 13px; border-radius: 2px;
    border: 1px solid rgba(255,255,255,60); background: rgba(255,255,255,10);
}}
QCheckBox::indicator:checked  {{ background: {_ACCENT}; border-color: {_ACCENT}; }}
QCheckBox::indicator:hover    {{ border-color: {_ACCENT}; }}
#keyChip {{
    color: white; font-weight: bold; font-size: 11px;
    background: rgba(255,255,255,18); border-radius: 3px; padding: 1px 5px;
}}
#descLabel  {{ color: {_FG}; }}
#warnLabel  {{ color: #CC9900; font-size: 13px; }}
#deleteBtn {{
    background: transparent; color: {_FG_DIM}; font-size: 13px;
    padding: 2px 5px; min-width: 20px; max-width: 20px;
}}
#deleteBtn:hover {{ color: #e05555; background: {_HOVER}; }}

/* ── Key Binder panel ── */
#keyBinderPanel {{ background: {_BG_SIDE}; border-top: 1px solid {_BORDER}; }}
#binderTitle {{
    color: rgba(255,255,255,140); font-size: 11px; font-weight: bold;
    padding: 5px 8px 3px 8px; background: {_BG_HEAD};
    border-bottom: 1px solid {_BORDER};
}}
#modBtn {{
    background: rgba(255,255,255,12); color: {_FG}; font-weight: bold;
    border-radius: 3px; padding: 3px 10px; min-height: 22px;
}}
#modBtn:checked              {{ background: {_ACCENT}; color: white; }}
#modBtn:hover                {{ background: rgba(255,255,255,22); }}
#modBtn:checked:hover        {{ background: {_ACCENT2}; }}

#keyBtn {{
    color: rgba(255,255,255,210); border-radius: 3px; font-size: 10px;
    font-weight: bold; border: none;
    min-width: 30px; max-width: 30px; min-height: 26px; max-height: 26px;
}}
#fnBtn {{
    color: rgba(255,255,255,210); border-radius: 3px; font-size: 9px;
    font-weight: bold; border: none;
    min-width: 34px; max-width: 34px; min-height: 26px; max-height: 26px;
}}
#keyBtn[state="free"],    #fnBtn[state="free"]    {{ background: {_K_FREE};  }}
#keyBtn[state="free"]:hover, #fnBtn[state="free"]:hover {{ background: {_K_FREE_H}; }}
#keyBtn[state="mine"],    #fnBtn[state="mine"]    {{ background: {_K_MINE};  }}
#keyBtn[state="mine"]:hover, #fnBtn[state="mine"]:hover {{ background: {_K_MINE_H}; }}
#keyBtn[state="muted"],   #fnBtn[state="muted"]   {{ background: {_K_MUTED}; }}
#keyBtn[state="muted"]:hover, #fnBtn[state="muted"]:hover {{ background: {_K_MUTED_H}; }}
#keyBtn[state="default"], #fnBtn[state="default"] {{ background: {_K_DEF};   }}
#keyBtn[state="default"]:hover, #fnBtn[state="default"]:hover {{ background: {_K_DEF_H}; }}
#keyBtn[state="selected"],#fnBtn[state="selected"] {{ background: {_K_SEL};  }}
#keyBtn[state="selected"]:hover, #fnBtn[state="selected"]:hover {{ background: {_K_SEL_H}; }}

#assignSection {{ background: {_BG}; padding: 8px 10px; }}
#keyDisplayLbl {{
    color: rgba(255,255,255,200); font-size: 13px; font-weight: bold; padding: 2px 0px;
}}
#statusLbl   {{ color: #CC9900; font-size: 11px; padding: 2px 0px; }}
#disabledHint {{ color: {_FG_DIM}; font-size: 11px; padding: 4px 0px; }}

QLineEdit, QPlainTextEdit {{
    background: rgba(255,255,255,8); border: 1px solid {_BORDER};
    border-radius: 2px; padding: 3px 6px; color: {_FG};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {_ACCENT}; }}
QRadioButton {{ background: transparent; spacing: 6px; }}
QRadioButton::indicator {{
    width: 12px; height: 12px; border-radius: 6px;
    border: 1px solid rgba(255,255,255,60); background: rgba(255,255,255,10);
}}
QRadioButton::indicator:checked {{ background: {_ACCENT}; border-color: {_ACCENT}; }}
#assignBtn {{
    background-color: {_ACCENT}; color: white; font-weight: bold;
    border-radius: 2px; padding: 4px 16px; min-height: 26px;
}}
#assignBtn:hover    {{ background-color: {_ACCENT2}; }}
#assignBtn:disabled {{ background-color: rgba(77,144,212,70); color: rgba(255,255,255,70); }}
#clearBtn {{
    background: rgba(255,255,255,12); color: {_FG}; border-radius: 2px;
    padding: 4px 12px; min-height: 26px;
}}
#clearBtn:hover    {{ background: rgba(255,255,255,25); }}
#clearBtn:disabled {{ color: {_FG_DIM}; }}

/* ── Tabs ── */
QTabWidget::pane {{ border: none; background: {_BG}; }}
QTabBar::tab {{
    background: {_BG_SIDE}; color: {_FG_DIM};
    padding: 7px 16px; border: none;
    border-bottom: 2px solid transparent; font-size: 12px;
}}
QTabBar::tab:selected       {{ color: {_FG}; border-bottom-color: {_ACCENT}; background: {_BG}; }}
QTabBar::tab:hover:!selected {{ color: {_FG}; background: {_HOVER}; }}

/* ── Reference browser ── */
QTableWidget {{
    background: transparent; gridline-color: {_BORDER}; border: none; outline: none;
}}
QTableWidget::item          {{ padding: 4px 6px; border: none; }}
QTableWidget::item:selected {{ background: {_SEL}; color: white; }}
QHeaderView::section {{
    background: {_BG_HEAD}; color: {_FG_DIM}; font-size: 11px;
    padding: 4px 6px; border: none; border-bottom: 1px solid {_BORDER};
    border-right: 1px solid {_BORDER};
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    width: 6px; background: transparent; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,30); border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,60); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical,  QScrollBar::sub-page:vertical {{ background: none; }}

QSplitter::handle         {{ background: {_BORDER}; }}
QSplitter::handle:vertical {{ height: 1px; }}
"""

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _slug(key, alt=False, ctrl=False, shift=False):
    mods = [m for m, v in (('alt', alt), ('ctrl', ctrl), ('shift', shift)) if v]
    return '+'.join(mods + [key]) if mods else key


def _slug_to_mods(slug):
    parts = slug.split('+')
    key   = parts[-1]
    alt   = 'alt'   in parts
    ctrl  = 'ctrl'  in parts
    shift = 'shift' in parts
    return key, alt, ctrl, shift


def _rtc_id(set_name, slug):
    safe = (set_name + '_' + slug).replace('+', '_').replace(' ', '_').replace('-', '_')
    return 'mpSC_' + safe


def _nc_id(rtc):
    return rtc + '_NC'


def _mod_label(alt, ctrl, shift):
    parts = [m for m, v in (('Alt', alt), ('Ctrl', ctrl), ('Shift', shift)) if v]
    return '+'.join(parts) if parts else ''


def _key_display(key, alt, ctrl, shift):
    mods = _mod_label(alt, ctrl, shift)
    lbl  = key.upper() if len(key) == 1 else key
    return f'{mods}+{lbl}' if mods else lbl


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

def _data_file():
    path = mpAnimConfig.get_save_path()
    if not path:
        return None
    folder = os.path.join(path, 'shortcuts')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, DATA_FILE)


def _load_data():
    f = _data_file()
    if f and os.path.exists(f):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if 'sets' in data:
                return data
        except Exception:
            pass
    return {'sets': {}, 'active': None}


def _save_data(data):
    f = _data_file()
    if f:
        with open(f, 'w') as fh:
            json.dump(data, fh, indent=2)


# ---------------------------------------------------------------------------
# Maya Default bindings cache
# ---------------------------------------------------------------------------

_default_cache = None   # {slug: nc_name}
_default_ann   = {}     # {nc_name: annotation}


def _get_default_bindings():
    global _default_cache, _default_ann
    if _default_cache is not None:
        return _default_cache
    _default_cache = {}
    current = cmds.hotkeySet(q=True, current=True)
    try:
        if not cmds.hotkeySet(_BUILTIN_SET, q=True, exists=True):
            return _default_cache
        cmds.hotkeySet(_BUILTIN_SET, edit=True, current=True)
        combos = [
            (False, False, False), (True,  False, False),
            (False, True,  False), (False, False, True),
            (True,  True,  False), (True,  False, True),
            (False, True,  True),  (True,  True,  True),
        ]
        for key in ALL_KEYS:
            for alt, ctrl, shift in combos:
                try:
                    nc = cmds.hotkey(
                        keyShortcut=key, query=True, name=True,
                        altModifier=alt, ctrlModifier=ctrl, shiftModifier=shift,
                    ) or ''
                    if nc:
                        _default_cache[_slug(key, alt, ctrl, shift)] = nc
                except Exception:
                    pass
    finally:
        if current and cmds.hotkeySet(current, q=True, exists=True):
            cmds.hotkeySet(current, edit=True, current=True)

    # Resolve annotations for reference browser (best-effort)
    for slug, nc in _default_cache.items():
        try:
            rtc = cmds.nameCommand(nc, query=True, command=True) or ''
            if rtc and cmds.runTimeCommand(rtc, query=True, exists=True):
                ann = cmds.runTimeCommand(rtc, query=True, annotation=True) or nc
                cat = cmds.runTimeCommand(rtc, query=True, category=True)  or ''
                _default_ann[nc] = {'annotation': ann, 'category': cat}
        except Exception:
            pass

    return _default_cache


# ---------------------------------------------------------------------------
# hotkeySet backend
# ---------------------------------------------------------------------------

def _set_exists(name):
    return bool(cmds.hotkeySet(name, query=True, exists=True))


def _user_sets():
    all_sets = cmds.hotkeySet(query=True, hotkeySetArray=True) or []
    return [s for s in all_sets if s != _BUILTIN_SET]


def _with_set(name, fn):
    """Run fn while name is the active hotkeySet, then restore."""
    current   = cmds.hotkeySet(query=True, current=True)
    switched  = False
    if name != current and name != _BUILTIN_SET and _set_exists(name):
        cmds.hotkeySet(name, edit=True, current=True)
        switched = True
    try:
        fn()
    finally:
        if switched and current and _set_exists(current):
            cmds.hotkeySet(current, edit=True, current=True)


def _ensure_rtc(rtc, desc, command, lang):
    if cmds.runTimeCommand(rtc, query=True, exists=True):
        cmds.runTimeCommand(rtc, edit=True,
                            annotation=desc, command=command, commandLanguage=lang)
    else:
        cmds.runTimeCommand(rtc, annotation=desc, command=command,
                            commandLanguage=lang, category='User')


def _bind_key(key, alt, ctrl, shift, nc):
    try:
        cmds.hotkey(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl,
                    shiftModifier=shift, name=nc)
    except Exception as e:
        cmds.warning(f'shortCuts: could not bind "{key}" — {e}')


def _clear_key(key, alt, ctrl, shift):
    try:
        cmds.hotkey(keyShortcut=key, altModifier=alt, ctrlModifier=ctrl,
                    shiftModifier=shift, name='', releaseName='')
    except Exception:
        pass


def create_set(name, source=None, data=None):
    if _set_exists(name):
        return
    src = source or cmds.hotkeySet(query=True, current=True)
    cmds.hotkeySet(name, source=src)
    if data is not None:
        data['sets'].setdefault(name, {'hotkeys': {}, 'spacebar': False})
        _save_data(data)


def delete_set(name, data):
    if _set_exists(name):
        cmds.hotkeySet(name, edit=True, delete=True)
    data['sets'].pop(name, None)
    if data.get('active') == name:
        data['active'] = None
    _save_data(data)


def apply_set(name, data):
    if name == _BUILTIN_SET:
        if _set_exists(_BUILTIN_SET):
            cmds.hotkeySet(_BUILTIN_SET, edit=True, current=True)
        _restore_spacebar()
    elif _set_exists(name):
        cmds.hotkeySet(name, edit=True, current=True)
        set_data = data.get('sets', {}).get(name, {})
        if set_data.get('spacebar', False):
            _bind_spacebar()
        else:
            _restore_spacebar()
    data['active'] = name
    _save_data(data)
    cmds.inViewMessage(amg=f'Preset <hl>{name}</hl> applied.', pos='midCenter', fade=True)


def add_hotkey(set_name, key, alt, ctrl, shift, desc, command, lang, data):
    slug = _slug(key, alt, ctrl, shift)
    rtc  = _rtc_id(set_name, slug)
    nc   = _nc_id(rtc)

    def _do():
        _ensure_rtc(rtc, desc, command, lang)
        try:
            cmds.nameCommand(nc, annotation=desc, command=rtc)
        except Exception:
            pass
        _bind_key(key, alt, ctrl, shift, nc)

    _with_set(set_name, _do)

    s = data['sets'].setdefault(set_name, {'hotkeys': {}, 'spacebar': False})
    s['hotkeys'][slug] = {
        'key': key, 'alt': alt, 'ctrl': ctrl, 'shift': shift,
        'desc': desc, 'command': command, 'lang': lang,
        'muted': False, 'rtc': rtc, 'nc': nc,
    }
    _save_data(data)


def remove_hotkey(set_name, slug, data):
    hk = data.get('sets', {}).get(set_name, {}).get('hotkeys', {}).get(slug)
    if not hk:
        return

    def _do():
        _clear_key(hk['key'], hk['alt'], hk['ctrl'], hk['shift'])
        rtc = hk.get('rtc')
        if rtc:
            try:
                cmds.runTimeCommand(rtc, delete=True)
            except Exception:
                pass

    _with_set(set_name, _do)
    data['sets'][set_name]['hotkeys'].pop(slug, None)
    _save_data(data)


def set_muted(set_name, slug, muted, data):
    hk = data.get('sets', {}).get(set_name, {}).get('hotkeys', {}).get(slug)
    if not hk:
        return
    hk['muted'] = muted

    def _do():
        if muted:
            _clear_key(hk['key'], hk['alt'], hk['ctrl'], hk['shift'])
        else:
            _bind_key(hk['key'], hk['alt'], hk['ctrl'], hk['shift'], hk['nc'])

    _with_set(set_name, _do)
    _save_data(data)


def set_spacebar(set_name, enabled, data):
    s = data['sets'].setdefault(set_name, {'hotkeys': {}, 'spacebar': False})
    s['spacebar'] = enabled
    _save_data(data)
    if data.get('active') == set_name:
        _bind_spacebar() if enabled else _restore_spacebar()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def _init(data):
    if not _set_exists('ps_anim'):
        current = cmds.hotkeySet(query=True, current=True)
        cmds.hotkeySet('ps_anim', source=current)

    s = data['sets'].setdefault('ps_anim', {'hotkeys': {}, 'spacebar': True})
    if not s.get('hotkeys'):
        for seed in _SEED_HOTKEYS:
            add_hotkey(
                'ps_anim',
                seed['key'], seed['alt'], seed['ctrl'], seed['shift'],
                seed['desc'], seed['command'], seed['lang'],
                data,
            )


# ---------------------------------------------------------------------------
# Spacebar Qt event filter
# ---------------------------------------------------------------------------

_space_filter   = None
_saved_space_hk = None


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

        focus = QtWidgets.QApplication.focusWidget()
        if focus is not None:
            is_text = isinstance(focus, (QtWidgets.QTextEdit,
                                         QtWidgets.QPlainTextEdit,
                                         QtWidgets.QLineEdit))
            if not is_text:
                try:
                    is_text = bool(focus.inputMethodQuery(
                        QtCore.Qt.InputMethodQuery.ImEnabled))
                except Exception:
                    pass
            if is_text:
                if t == QtCore.QEvent.Type.KeyPress and not event.isAutoRepeat():
                    if hasattr(focus, 'insertPlainText'):
                        focus.insertPlainText(' ')
                    elif hasattr(focus, 'insert'):
                        focus.insert(' ')
                return True

        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
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
    global _space_filter, _saved_space_hk
    _restore_spacebar()
    try:
        _saved_space_hk = {
            'press':   cmds.hotkey(keyShortcut='space', query=True, name=True)        or '',
            'release': cmds.hotkey(keyShortcut='space', query=True, releaseName=True) or '',
        }
    except Exception:
        _saved_space_hk = {'press': '', 'release': ''}
    cmds.hotkey(keyShortcut='space', name='', releaseName='')
    app = QtWidgets.QApplication.instance()
    _space_filter = _SpacePlayFilter(app)
    app.installEventFilter(_space_filter)


def _restore_spacebar():
    global _space_filter, _saved_space_hk
    if _space_filter is not None:
        QtWidgets.QApplication.instance().removeEventFilter(_space_filter)
        _space_filter = None
    if _saved_space_hk is not None:
        cmds.hotkey(keyShortcut='space',
                    name=_saved_space_hk['press'],
                    releaseName=_saved_space_hk['release'])
        _saved_space_hk = None
    else:
        cmds.hotkey(keyShortcut='space', name='', releaseName='')


# ---------------------------------------------------------------------------
# KeyButton & KeyboardWidget
# ---------------------------------------------------------------------------

class _KeyButton(QtWidgets.QPushButton):
    clicked_key = QtCore.Signal(str)

    def __init__(self, label, key, fn_key=False, parent=None):
        super().__init__(label, parent)
        self.key = key
        self.setObjectName('fnBtn' if fn_key else 'keyBtn')
        self._state = ''
        self.set_state('free')
        self.clicked.connect(lambda: self.clicked_key.emit(self.key))

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        self.setProperty('state', state)
        self.style().unpolish(self)
        self.style().polish(self)


class KeyboardWidget(QtWidgets.QWidget):
    key_selected = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._btns     = {}   # key_value -> _KeyButton
        self._selected = None
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 6, 8, 6)

        for row_idx, row in enumerate(KB_ROWS):
            row_w  = QtWidgets.QWidget()
            row_l  = QtWidgets.QHBoxLayout(row_w)
            row_l.setSpacing(3)
            row_l.setContentsMargins(KB_OFFSETS[row_idx], 0, 0, 0)
            row_l.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

            is_fn = (row_idx == 0)
            for entry in row:
                if entry is None:
                    spacer = QtWidgets.QWidget()
                    spacer.setFixedWidth(8)
                    row_l.addWidget(spacer)
                else:
                    label, key = entry
                    btn = _KeyButton(label, key, fn_key=is_fn)
                    btn.clicked_key.connect(self._on_key_clicked)
                    self._btns[key] = btn
                    row_l.addWidget(btn)

            row_l.addStretch()
            layout.addWidget(row_w)

    def _on_key_clicked(self, key):
        if self._selected and self._selected in self._btns:
            # Will be refreshed by next update_states call; set temporarily
            self._btns[self._selected].set_state('free')
        self._selected = key
        self._btns[key].set_state('selected')
        self.key_selected.emit(key)

    def update_states(self, category_hotkeys, default_bindings, alt, ctrl, shift):
        for key, btn in self._btns.items():
            if key == self._selected:
                btn.set_state('selected')
                continue
            slug = _slug(key, alt, ctrl, shift)
            if slug in category_hotkeys:
                state = 'muted' if category_hotkeys[slug].get('muted') else 'mine'
            elif slug in default_bindings:
                state = 'default'
            else:
                state = 'free'
            btn.set_state(state)

    def clear_selection(self):
        self._selected = None

    def selected_key(self):
        return self._selected


# ---------------------------------------------------------------------------
# MainPanel — category sidebar + hotkey list
# ---------------------------------------------------------------------------

class _HotkeyRow(QtWidgets.QWidget):
    mute_toggled   = QtCore.Signal(str, bool)   # slug, muted
    delete_clicked = QtCore.Signal(str)          # slug

    def __init__(self, slug, hk_data, parent=None):
        super().__init__(parent)
        self.slug = slug
        self.setObjectName('hotkeyRow')

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(6, 0, 4, 0)
        h.setSpacing(8)

        cb = QtWidgets.QCheckBox()
        cb.setChecked(not hk_data.get('muted', False))
        cb.toggled.connect(lambda checked: self.mute_toggled.emit(slug, not checked))
        h.addWidget(cb)

        key, alt, ctrl, shift = _slug_to_mods(slug)
        chip = QtWidgets.QLabel(_key_display(key, alt, ctrl, shift))
        chip.setObjectName('keyChip')
        h.addWidget(chip)

        desc = QtWidgets.QLabel(hk_data.get('desc', ''))
        desc.setObjectName('descLabel')
        h.addWidget(desc, 1)

        del_btn = QtWidgets.QPushButton('✕')
        del_btn.setObjectName('deleteBtn')
        del_btn.setToolTip('Remove hotkey')
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(slug))
        h.addWidget(del_btn)


class _SpaceRow(QtWidgets.QWidget):
    toggled = QtCore.Signal(bool)

    def __init__(self, enabled, parent=None):
        super().__init__(parent)
        self.setObjectName('hotkeyRow')

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(6, 0, 4, 0)
        h.setSpacing(8)

        self._cb = QtWidgets.QCheckBox()
        self._cb.setChecked(enabled)
        self._cb.toggled.connect(self.toggled)
        h.addWidget(self._cb)

        chip = QtWidgets.QLabel('Space')
        chip.setObjectName('keyChip')
        h.addWidget(chip)

        desc = QtWidgets.QLabel('Toggle play / Hotbox (hold)')
        desc.setObjectName('descLabel')
        h.addWidget(desc, 1)

        warn = QtWidgets.QLabel('⚠')
        warn.setObjectName('warnLabel')
        warn.setToolTip('Tap = play/stop  |  Hold 400ms = hotbox')
        h.addWidget(warn)

    def set_checked(self, val):
        self._cb.blockSignals(True)
        self._cb.setChecked(val)
        self._cb.blockSignals(False)


class MainPanel(QtWidgets.QWidget):
    set_selected = QtCore.Signal(str)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._data = data
        self._build_ui()
        active = data.get('active') or 'ps_anim'
        self._refresh_list(select=active)

    # ── build ──────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._make_sidebar())
        body.addWidget(self._make_content(), 1)
        root.addLayout(body, 1)

        footer = QtWidgets.QWidget()
        footer.setObjectName('header')
        fl = QtWidgets.QHBoxLayout(footer)
        fl.setContentsMargins(8, 0, 8, 0)
        fl.addStretch()
        apply_btn = QtWidgets.QPushButton('Apply Category')
        apply_btn.setObjectName('applyBtn')
        apply_btn.clicked.connect(self._apply)
        fl.addWidget(apply_btn)
        root.addWidget(footer)

    def _make_sidebar(self):
        w = QtWidgets.QWidget()
        w.setObjectName('sidebar')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QtWidgets.QListWidget()
        self._list.currentTextChanged.connect(self._on_set_changed)
        layout.addWidget(self._list, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(4, 4, 4, 4)
        btn_row.setSpacing(2)

        add_btn = QtWidgets.QPushButton('+')
        add_btn.setObjectName('sidebarBtn')
        add_btn.setToolTip('New category (copies selected)')
        add_btn.clicked.connect(self._new_set)
        btn_row.addWidget(add_btn)

        self._del_btn = QtWidgets.QPushButton('✕')
        self._del_btn.setObjectName('sidebarBtn')
        self._del_btn.setToolTip('Delete category')
        self._del_btn.clicked.connect(self._delete_set)
        btn_row.addWidget(self._del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return w

    def _make_content(self):
        w = QtWidgets.QWidget()
        w.setObjectName('content')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QtWidgets.QStackedWidget()

        # Page 0: hotkey list (user sets)
        scroll_w = QtWidgets.QWidget()
        self._hotkey_layout = QtWidgets.QVBoxLayout(scroll_w)
        self._hotkey_layout.setContentsMargins(0, 0, 0, 0)
        self._hotkey_layout.setSpacing(0)
        self._hotkey_layout.addStretch()

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(scroll_w)
        self._stack.addWidget(scroll)

        # Page 1: Maya_Default info
        info_w = QtWidgets.QWidget()
        info_l = QtWidgets.QVBoxLayout(info_w)
        info_l.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl = QtWidgets.QLabel(
            'Maya\'s default hotkeys are read-only.\n'
            'Use the Reference tab to explore them.')
        lbl.setObjectName('disabledHint')
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        info_l.addWidget(lbl)
        self._stack.addWidget(info_w)

        layout.addWidget(self._stack, 1)
        return w

    # ── list management ────────────────────────────────────

    def _refresh_list(self, select=None):
        self._list.blockSignals(True)
        self._list.clear()
        # Built-in first
        self._list.addItem('Default (Maya)')
        for name in _user_sets():
            self._list.addItem(name)
        target = select or 'ps_anim'
        # Map display name back
        display = 'Default (Maya)' if target == _BUILTIN_SET else target
        items = self._list.findItems(display, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            self._list.setCurrentItem(items[0])
        self._list.blockSignals(False)
        self._load_hotkeys(self._display_to_set(display))

    def _display_to_set(self, display):
        return _BUILTIN_SET if display == 'Default (Maya)' else display

    def current_set(self):
        item = self._list.currentItem()
        return self._display_to_set(item.text()) if item else None

    # ── hotkey list ────────────────────────────────────────

    def _clear_hotkeys(self):
        layout = self._hotkey_layout
        while layout.count() > 1:   # keep the trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_hotkeys(self, set_name):
        self._clear_hotkeys()
        if set_name == _BUILTIN_SET:
            self._stack.setCurrentIndex(1)
            return
        self._stack.setCurrentIndex(0)

        s = self._data.get('sets', {}).get(set_name, {})

        # Spacebar row
        space_row = _SpaceRow(s.get('spacebar', False))
        space_row.toggled.connect(
            lambda enabled: self._on_spacebar_toggled(set_name, enabled))
        self._hotkey_layout.insertWidget(0, space_row)

        # Regular hotkeys
        hotkeys = s.get('hotkeys', {})
        for i, (slug, hk) in enumerate(hotkeys.items()):
            row = _HotkeyRow(slug, hk)
            row.mute_toggled.connect(
                lambda s_, m, sn=set_name: self._on_mute(sn, s_, m))
            row.delete_clicked.connect(
                lambda s_, sn=set_name: self._on_delete(sn, s_))
            self._hotkey_layout.insertWidget(i + 1, row)

    def refresh_hotkeys(self, set_name):
        display = 'Default (Maya)' if set_name == _BUILTIN_SET else set_name
        items   = self._list.findItems(display, QtCore.Qt.MatchFlag.MatchExactly)
        if items and items[0] == self._list.currentItem():
            self._load_hotkeys(set_name)

    # ── slots ──────────────────────────────────────────────

    def _on_set_changed(self, display):
        set_name = self._display_to_set(display)
        is_builtin = set_name == _BUILTIN_SET
        self._del_btn.setEnabled(not is_builtin and bool(display))
        self._load_hotkeys(set_name)
        self.set_selected.emit(set_name)

    def _on_spacebar_toggled(self, set_name, enabled):
        set_spacebar(set_name, enabled, self._data)

    def _on_mute(self, set_name, slug, muted):
        set_muted(set_name, slug, muted, self._data)

    def _on_delete(self, set_name, slug):
        reply = QtWidgets.QMessageBox.question(
            self, 'Delete Hotkey', 'Remove this hotkey from the category?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_hotkey(set_name, slug, self._data)
        self._load_hotkeys(set_name)

    def _apply(self):
        name = self.current_set()
        if name:
            apply_set(name, self._data)

    def _new_set(self):
        name, ok = QtWidgets.QInputDialog.getText(
            self, 'New Category', 'Category name:', text='My Preset')
        if not ok or not name.strip():
            return
        name = name.strip()
        if _set_exists(name):
            QtWidgets.QMessageBox.warning(self, 'shortCuts',
                                          f'"{name}" already exists.')
            return
        source = self.current_set()
        if source == _BUILTIN_SET:
            source = None
        create_set(name, source=source, data=self._data)
        # Copy hotkeys in JSON from source
        if source and source in self._data.get('sets', {}):
            import copy
            src_hks = self._data['sets'][source].get('hotkeys', {})
            self._data['sets'][name]['hotkeys'] = copy.deepcopy(src_hks)
            _save_data(self._data)
        self._refresh_list(select=name)

    def _delete_set(self):
        name = self.current_set()
        if not name or name == _BUILTIN_SET:
            return
        reply = QtWidgets.QMessageBox.question(
            self, 'Delete Category', f'Delete "{name}" and all its hotkeys?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        # Remove hotkey bindings from Maya before deleting
        hotkeys = self._data.get('sets', {}).get(name, {}).get('hotkeys', {})
        for slug, hk in hotkeys.items():
            def _do(h=hk):
                _clear_key(h['key'], h['alt'], h['ctrl'], h['shift'])
                rtc = h.get('rtc')
                if rtc:
                    try:
                        cmds.runTimeCommand(rtc, delete=True)
                    except Exception:
                        pass
            _with_set(name, _do)
        delete_set(name, self._data)
        self._refresh_list()


# ---------------------------------------------------------------------------
# KeyBinderPanel
# ---------------------------------------------------------------------------

class KeyBinderPanel(QtWidgets.QWidget):
    hotkey_assigned = QtCore.Signal(str)   # emits set_name

    def __init__(self, data, main_panel, parent=None):
        super().__init__(parent)
        self.setObjectName('keyBinderPanel')
        self._data       = data
        self._main       = main_panel
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QtWidgets.QLabel('KEY BINDER')
        title.setObjectName('binderTitle')
        root.addWidget(title)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(8, 6, 8, 6)
        body.setSpacing(12)

        # Left: modifier toggles + keyboard
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)

        mod_row = QtWidgets.QHBoxLayout()
        mod_row.setSpacing(6)
        self._alt   = QtWidgets.QPushButton('Alt')
        self._ctrl  = QtWidgets.QPushButton('Ctrl')
        self._shift = QtWidgets.QPushButton('Shift')
        for btn in (self._alt, self._ctrl, self._shift):
            btn.setObjectName('modBtn')
            btn.setCheckable(True)
            btn.toggled.connect(self._on_modifier_changed)
            mod_row.addWidget(btn)
        mod_row.addStretch()
        left.addLayout(mod_row)

        self._keyboard = KeyboardWidget()
        self._keyboard.key_selected.connect(self._on_key_selected)
        left.addWidget(self._keyboard)
        left.addStretch()

        # Right: assignment section
        right = self._make_assign_section()

        body.addLayout(left, 2)
        body.addWidget(right, 1)
        root.addLayout(body, 1)

    def _make_assign_section(self):
        w = QtWidgets.QWidget()
        w.setObjectName('assignSection')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._key_lbl    = QtWidgets.QLabel('Select a key')
        self._key_lbl.setObjectName('keyDisplayLbl')
        self._status_lbl = QtWidgets.QLabel('')
        self._status_lbl.setObjectName('statusLbl')
        self._status_lbl.setWordWrap(True)

        layout.addWidget(self._key_lbl)
        layout.addWidget(self._status_lbl)

        self._desc_edit = QtWidgets.QLineEdit()
        self._desc_edit.setPlaceholderText('Short description')
        layout.addWidget(self._desc_edit)

        lang_row = QtWidgets.QHBoxLayout()
        self._py_rb  = QtWidgets.QRadioButton('Python')
        self._mel_rb = QtWidgets.QRadioButton('MEL')
        self._py_rb.setChecked(True)
        lang_row.addWidget(self._py_rb)
        lang_row.addWidget(self._mel_rb)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        self._cmd_edit = QtWidgets.QPlainTextEdit()
        self._cmd_edit.setPlaceholderText('Paste command from Script Editor…')
        self._cmd_edit.setFixedHeight(72)
        layout.addWidget(self._cmd_edit)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        self._clear_btn = QtWidgets.QPushButton('Clear')
        self._clear_btn.setObjectName('clearBtn')
        self._clear_btn.setEnabled(False)
        self._clear_btn.setToolTip('Remove binding from this key')
        self._clear_btn.clicked.connect(self._clear_binding)
        btn_row.addWidget(self._clear_btn)

        self._assign_btn = QtWidgets.QPushButton('Assign')
        self._assign_btn.setObjectName('assignBtn')
        self._assign_btn.setEnabled(False)
        self._assign_btn.clicked.connect(self._assign)
        btn_row.addWidget(self._assign_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    # ── refresh ────────────────────────────────────────────

    def refresh(self, set_name=None):
        if set_name is None:
            set_name = self._main.current_set()
        is_builtin = set_name == _BUILTIN_SET
        self._assign_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._keyboard.clear_selection()
        if is_builtin:
            self._key_lbl.setText('Default set — read only')
            self._status_lbl.setText('')
        else:
            self._key_lbl.setText('Select a key')
            self._status_lbl.setText('')
        self._update_keyboard(set_name)

    def _update_keyboard(self, set_name=None):
        if set_name is None:
            set_name = self._main.current_set()
        hotkeys  = {} if set_name == _BUILTIN_SET else \
                   self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {})
        defaults = _get_default_bindings()
        alt, ctrl, shift = self._mods()
        self._keyboard.update_states(hotkeys, defaults, alt, ctrl, shift)

    def _mods(self):
        return self._alt.isChecked(), self._ctrl.isChecked(), self._shift.isChecked()

    # ── slots ──────────────────────────────────────────────

    def _on_modifier_changed(self):
        self._update_keyboard()
        # Re-evaluate selected key status
        key = self._keyboard.selected_key()
        if key:
            self._on_key_selected(key)

    def _on_key_selected(self, key):
        set_name = self._main.current_set()
        is_builtin = set_name == _BUILTIN_SET
        alt, ctrl, shift = self._mods()
        slug = _slug(key, alt, ctrl, shift)

        display = _key_display(key, alt, ctrl, shift)
        self._key_lbl.setText(f'Selected: {display}')

        hotkeys  = {} if is_builtin else \
                   self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {})
        defaults = _get_default_bindings()

        if is_builtin:
            self._assign_btn.setEnabled(False)
            self._clear_btn.setEnabled(False)
            self._status_lbl.setText('Default set is read-only.')
            return

        if slug in hotkeys:
            hk = hotkeys[slug]
            self._desc_edit.setText(hk.get('desc', ''))
            self._cmd_edit.setPlainText(hk.get('command', ''))
            (self._py_rb if hk.get('lang', 'python') == 'python' else self._mel_rb).setChecked(True)
            self._status_lbl.setText('Already bound — editing existing.')
            self._clear_btn.setEnabled(True)
        else:
            self._desc_edit.clear()
            self._cmd_edit.clear()
            self._clear_btn.setEnabled(False)
            if slug in defaults:
                nc  = defaults[slug]
                ann = _default_ann.get(nc, {}).get('annotation', nc)
                self._status_lbl.setText(f'⚠  Overrides Maya default: {ann}')
            else:
                self._status_lbl.setText('')

        self._assign_btn.setEnabled(True)

    def _assign(self):
        key = self._keyboard.selected_key()
        if not key:
            return
        set_name = self._main.current_set()
        if not set_name or set_name == _BUILTIN_SET:
            return
        alt, ctrl, shift = self._mods()
        desc = self._desc_edit.text().strip()
        cmd  = self._cmd_edit.toPlainText().strip()
        lang = 'python' if self._py_rb.isChecked() else 'mel'
        if not desc or not cmd:
            QtWidgets.QMessageBox.warning(self, 'Key Binder',
                                          'Description and command are both required.')
            return
        add_hotkey(set_name, key, alt, ctrl, shift, desc, cmd, lang, self._data)
        self._update_keyboard(set_name)
        self._clear_btn.setEnabled(True)
        self._status_lbl.setText('Assigned.')
        self.hotkey_assigned.emit(set_name)

    def _clear_binding(self):
        key = self._keyboard.selected_key()
        if not key:
            return
        set_name = self._main.current_set()
        if not set_name or set_name == _BUILTIN_SET:
            return
        alt, ctrl, shift = self._mods()
        slug = _slug(key, alt, ctrl, shift)
        hotkeys = self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {})
        if slug not in hotkeys:
            return
        reply = QtWidgets.QMessageBox.question(
            self, 'Clear Binding',
            f'Remove the binding for {_key_display(key, alt, ctrl, shift)}?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_hotkey(set_name, slug, self._data)
        self._desc_edit.clear()
        self._cmd_edit.clear()
        self._clear_btn.setEnabled(False)
        self._status_lbl.setText('')
        self._update_keyboard(set_name)
        self.hotkey_assigned.emit(set_name)


# ---------------------------------------------------------------------------
# ReferenceBrowser
# ---------------------------------------------------------------------------

class ReferenceBrowser(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items     = []
        self._populated = False
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText('Search by key, description or category…')
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(['Key', 'Modifier', 'Description', 'Category'])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 55)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(3, 140)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        layout.addWidget(self._table, 1)

    def populate(self):
        if self._populated:
            return
        self._populated = True
        defaults = _get_default_bindings()
        items    = []
        for slug, nc in defaults.items():
            key, alt, ctrl, shift = _slug_to_mods(slug)
            mods = _mod_label(alt, ctrl, shift)
            info = _default_ann.get(nc, {})
            ann  = info.get('annotation', nc)
            cat  = info.get('category', '')
            items.append((key.upper() if len(key) == 1 else key, mods, ann, cat, slug))
        items.sort(key=lambda x: (x[3].lower(), x[0].lower()))
        self._items = items
        self._populate_table(items)

    def _populate_table(self, items):
        self._table.setRowCount(0)
        for key_disp, mods, ann, cat, _ in items:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QtWidgets.QTableWidgetItem(key_disp))
            self._table.setItem(r, 1, QtWidgets.QTableWidgetItem(mods))
            self._table.setItem(r, 2, QtWidgets.QTableWidgetItem(ann))
            self._table.setItem(r, 3, QtWidgets.QTableWidgetItem(cat))
            self._table.setRowHeight(r, 24)

    def _filter(self, text):
        t = text.lower()
        if not t:
            self._populate_table(self._items)
            return
        filtered = [i for i in self._items
                    if t in i[0].lower() or t in i[2].lower() or t in i[3].lower()
                    or t in i[1].lower()]
        self._populate_table(filtered)


# ---------------------------------------------------------------------------
# ShortCutsUI  —  tabbed main window
# ---------------------------------------------------------------------------

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class ShortCutsUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('shortCuts')
        self.setObjectName(WINDOW_NAME)
        self.setMinimumSize(700, 660)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window |
            QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(STYLESHEET)

        self._data = _load_data()
        _init(self._data)

        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        tabs = QtWidgets.QTabWidget()

        # ── Tab 1: Main + Key Binder ──────────────────────
        tab1 = QtWidgets.QWidget()
        t1   = QtWidgets.QVBoxLayout(tab1)
        t1.setContentsMargins(0, 0, 0, 0)
        t1.setSpacing(0)

        self._main_panel = MainPanel(self._data)
        self._key_binder = KeyBinderPanel(self._data, self._main_panel)

        self._main_panel.set_selected.connect(self._key_binder.refresh)
        self._key_binder.hotkey_assigned.connect(self._main_panel.refresh_hotkeys)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self._main_panel)
        splitter.addWidget(self._key_binder)
        splitter.setSizes([220, 420])
        splitter.setChildrenCollapsible(False)
        t1.addWidget(splitter, 1)

        # ── Tab 2: Reference Browser ──────────────────────
        self._ref = ReferenceBrowser()

        tabs.addTab(tab1,      'Hotkeys')
        tabs.addTab(self._ref, 'Reference')
        tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(tabs, 1)

        # Trigger initial keyboard state
        QtCore.QTimer.singleShot(0, lambda: self._key_binder.refresh(
            self._main_panel.current_set()))

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

    def _on_tab_changed(self, index):
        if index == 1:
            self._ref.populate()


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

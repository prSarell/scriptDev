import os
import re
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
# Keyboard layout
# ---------------------------------------------------------------------------
# Entry dicts:
#   type='key'   → assignable; 'key' = Maya keyShortcut string
#   type='mod'   → modifier toggle; 'mod' = 'alt'|'ctrl'|'shift'
#   type='dead'  → visual-only, not assignable
#   type='space' → spacebar (assignable, wide)
# None entries = small visual gap

def _K(lbl, key, w=30):       return {'type': 'key',   'label': lbl, 'key': key,     'w': w}
def _FN(lbl, key):             return {'type': 'key',   'label': lbl, 'key': key,     'w': 34}
def _MOD(lbl, key, mod, w=44): return {'type': 'mod',   'label': lbl, 'key': key,     'w': w, 'mod': mod}
def _DEAD(lbl, w=34):          return {'type': 'dead',  'label': lbl, 'key': None,    'w': w}
def _SPACE():                  return {'type': 'space', 'label': 'Space', 'key': 'space', 'w': 150}

_KB_FN = [
    _K('Esc', 'Escape', 34), None,
    _FN('F1','F1'), _FN('F2','F2'), _FN('F3','F3'), _FN('F4','F4'), None,
    _FN('F5','F5'), _FN('F6','F6'), _FN('F7','F7'), _FN('F8','F8'), None,
    _FN('F9','F9'), _FN('F10','F10'), _FN('F11','F11'), _FN('F12','F12'),
]
_KB_NUM = [
    _K('`','`'), _K('1','1'), _K('2','2'), _K('3','3'), _K('4','4'), _K('5','5'),
    _K('6','6'), _K('7','7'), _K('8','8'), _K('9','9'), _K('0','0'),
    _K('-','-'), _K('=','='), _K('⌫', 'BackSpace', 52),
]
_KB_Q = [
    _K('Tab', 'Tab', 46),
    _K('Q','q'), _K('W','w'), _K('E','e'), _K('R','r'), _K('T','t'), _K('Y','y'),
    _K('U','u'), _K('I','i'), _K('O','o'), _K('P','p'),
    _K('[','['), _K(']',']'), _K('\\','\\'),
]
_KB_A = [
    _DEAD('Caps', 52),
    _K('A','a'), _K('S','s'), _K('D','d'), _K('F','f'), _K('G','g'), _K('H','h'),
    _K('J','j'), _K('K','k'), _K('L','l'), _K(';',';'), _K("'","'"),
    _K('Enter', 'Return', 52),
]
_KB_Z = [
    _MOD('Shift', 'LShift', 'shift', 62),
    _K('Z','z'), _K('X','x'), _K('C','c'), _K('V','v'), _K('B','b'), _K('N','n'),
    _K('M','m'), _K(',',','), _K('.','.'), _K('/','/',),
    _MOD('Shift', 'RShift', 'shift', 62),
]
_KB_BOTTOM_PC = [
    _MOD('Ctrl', 'LCtrl', 'ctrl', 44), _DEAD('Win', 36),
    _MOD('Alt',  'LAlt',  'alt',  40), _SPACE(),
    _MOD('Alt',  'RAlt',  'alt',  40), _DEAD('Win', 36),
    _DEAD('Menu', 36),                 _MOD('Ctrl', 'RCtrl', 'ctrl', 44),
]
_KB_BOTTOM_MAC = [
    _MOD('⌃', 'LCtrl', 'ctrl', 38), _MOD('⌥', 'LAlt', 'alt', 40),
    _DEAD('⌘', 44),                  _SPACE(),
    _DEAD('⌘', 44),                  _MOD('⌥', 'RAlt', 'alt', 40),
    _MOD('⌃', 'RCtrl', 'ctrl', 38),
]

KB_COMMON_ROWS = [_KB_FN, _KB_NUM, _KB_Q, _KB_A, _KB_Z]
KB_OFFSETS     = [0, 0, 12, 18, 28, 0]   # index 5 = bottom row

ALL_MAYA_KEYS = [
    e['key']
    for rows in [*KB_COMMON_ROWS, _KB_BOTTOM_PC]
    for e in rows
    if e is not None and e['type'] in ('key', 'space')
]

# Qt physical key → Maya keyShortcut string
# Uses getattr so any key name absent from this Qt build is silently skipped.
def _qt_key(name):
    return getattr(QtCore.Qt.Key, name, None)

_QT_TO_MAYA_KEY = {}
for _qt, _mk in [
    ('Key_Escape',       'Escape'),
    ('Key_Tab',          'Tab'),
    ('Key_Backspace',    'BackSpace'),
    ('Key_Return',       'Return'),
    ('Key_Enter',        'Return'),
    ('Key_Space',        'space'),
    ('Key_QuoteLeft',    '`'),      # backtick / grave
    ('Key_Minus',        '-'),
    ('Key_Equal',        '='),
    ('Key_BracketLeft',  '['),
    ('Key_BracketRight', ']'),
    ('Key_Backslash',    '\\'),
    ('Key_Semicolon',    ';'),
    ('Key_Apostrophe',   "'"),
    ('Key_Comma',        ','),
    ('Key_Period',       '.'),
    ('Key_Slash',        '/'),
]:
    k = _qt_key(_qt)
    if k is not None:
        _QT_TO_MAYA_KEY[k] = _mk
for _c in 'abcdefghijklmnopqrstuvwxyz':
    k = _qt_key(f'Key_{_c.upper()}')
    if k is not None:
        _QT_TO_MAYA_KEY[k] = _c
for _d in '0123456789':
    k = _qt_key(f'Key_{_d}')
    if k is not None:
        _QT_TO_MAYA_KEY[k] = _d
for _n in range(1, 13):
    k = _qt_key(f'Key_F{_n}')
    if k is not None:
        _QT_TO_MAYA_KEY[k] = f'F{_n}'
del _qt_key, _qt, _mk, _c, _d, _n, k

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

_K_FREE   = '#3a3a3a'; _K_FREE_H  = '#484848'   # unassigned — visible grey
_K_MINE   = '#1a4d7a'; _K_MINE_H  = '#2260a0'   # user assigned — blue
_K_MUTED  = '#0f2535'; _K_MUTED_H = '#162e42'   # user assigned muted — dim blue
_K_DEF    = '#6b4a00'; _K_DEF_H   = '#8a6000'   # Maya default — amber
_K_SEL    = '#4D90D4'; _K_SEL_H   = '#5ca0e4'   # selected — bright accent

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
    min-width: 100px;
}}
QListWidget {{
    background-color: transparent; border: none; outline: none; padding: 4px 0px;
}}
QListWidget::item {{ padding: 6px 10px; color: {_FG}; }}
QListWidget::item:hover {{ background-color: {_HOVER}; }}
QListWidget::item:selected {{ background-color: {_SEL}; color: white; }}

#sidebarBtn {{
    background: transparent; color: {_FG_DIM}; font-size: 18px;
    font-weight: bold; padding: 2px;
    min-width: 32px; max-width: 32px; min-height: 28px; max-height: 28px;
    border-radius: 3px;
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

#keyBtn, #fnBtn {{
    color: rgba(255,255,255,210); border-radius: 3px; font-size: 10px;
    font-weight: bold; border: none; min-height: 26px; max-height: 26px;
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

#modKeyBtn {{
    color: rgba(255,255,255,210); border-radius: 3px; font-size: 10px;
    font-weight: bold; border: none; min-height: 26px; max-height: 26px;
}}
#modKeyBtn[active="false"]       {{ background: rgba(255,255,255,12); }}
#modKeyBtn[active="false"]:hover {{ background: rgba(255,255,255,22); }}
#modKeyBtn[active="true"]        {{ background: {_ACCENT}; color: white; }}
#modKeyBtn[active="true"]:hover  {{ background: {_ACCENT2}; }}

#deadKeyBtn {{
    color: rgba(255,255,255,50); border-radius: 3px; font-size: 9px;
    font-weight: bold; background: rgba(255,255,255,5); border: none;
    min-height: 26px; max-height: 26px;
}}

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
    safe = re.sub(r'[^A-Za-z0-9_]', '_', set_name + '_' + slug)
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
    return {'sets': {}, 'active': None, 'keyboard': 'pc'}


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

        # assignCommand keyString format: [key, alt, ctrl, ?, ?, ?, shift]
        num = cmds.assignCommand(q=True, numElements=True) or 0
        for i in range(1, num + 1):
            try:
                ks = cmds.assignCommand(i, q=True, keyString=True)
                nc = cmds.assignCommand(i, q=True, name=True)
                if not ks or not nc or len(ks) < 7:
                    continue
                key   = ks[0].lower() if ks[0] else ''
                if not key:
                    continue
                if key == ' ':
                    key = 'space'
                alt   = ks[1] == '1'
                ctrl  = ks[2] == '1'
                shift = ks[6] == '1'
                _default_cache[_slug(key, alt, ctrl, shift)] = nc
                # Resolve annotation for reference browser
                try:
                    rtc = cmds.nameCommand(nc, query=True, command=True) or ''
                    if rtc and cmds.runTimeCommand(rtc, query=True, exists=True):
                        ann = cmds.runTimeCommand(rtc, query=True, annotation=True) or nc
                        cat = cmds.runTimeCommand(rtc, query=True, category=True)  or ''
                        _default_ann[nc] = {'annotation': ann, 'category': cat}
                except Exception:
                    pass
            except Exception:
                pass
    finally:
        if current and cmds.hotkeySet(current, q=True, exists=True):
            cmds.hotkeySet(current, edit=True, current=True)

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
        _restore_backtick()
    elif _set_exists(name):
        cmds.hotkeySet(name, edit=True, current=True)
        set_data = data.get('sets', {}).get(name, {})
        if set_data.get('spacebar', False):
            _bind_spacebar()
        else:
            _restore_spacebar()
        if set_data.get('shotcam_toggle', True):
            _bind_backtick()
        else:
            _restore_backtick()
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

def _restore_rtcs(set_name, set_data):
    """Rebuild RTCs, NCs and key bindings for all hotkeys in a set.
    Called on tool open so hotkeys added on another machine (or lost after
    a Maya prefs wipe) are re-registered without the user having to re-assign."""
    for slug, hk in set_data.get('hotkeys', {}).items():
        if hk.get('muted'):
            continue
        rtc = hk.get('rtc') or _rtc_id(set_name, slug)
        nc  = hk.get('nc')  or _nc_id(rtc)

        def _do(hk=hk, rtc=rtc, nc=nc):
            _ensure_rtc(rtc, hk.get('desc', ''), hk.get('command', ''),
                        hk.get('lang', 'python'))
            try:
                cmds.nameCommand(nc, annotation=hk.get('desc', ''), command=rtc)
            except Exception:
                pass
            _bind_key(hk['key'], hk['alt'], hk['ctrl'], hk['shift'], nc)

        _with_set(set_name, _do)


def _init(data):
    if not _set_exists('ps_anim'):
        current = cmds.hotkeySet(query=True, current=True)
        cmds.hotkeySet('ps_anim', source=current)

    s = data['sets'].setdefault('ps_anim', {'hotkeys': {}, 'spacebar': True})
    for seed in _SEED_HOTKEYS:
        slug = _slug(seed['key'], seed['alt'], seed['ctrl'], seed['shift'])
        if slug not in s.get('hotkeys', {}):
            add_hotkey(
                'ps_anim',
                seed['key'], seed['alt'], seed['ctrl'], seed['shift'],
                seed['desc'], seed['command'], seed['lang'],
                data,
            )

    for set_name, set_data in data.get('sets', {}).items():
        _restore_rtcs(set_name, set_data)

    active = data.get('active') or 'ps_anim'
    if active != _BUILTIN_SET and _set_exists(active):
        cmds.hotkeySet(active, edit=True, current=True)
        set_data = data.get('sets', {}).get(active, {})
        if set_data.get('spacebar', False):
            _bind_spacebar()
        if set_data.get('shotcam_toggle', True):
            _bind_backtick()


# ---------------------------------------------------------------------------
# Spacebar Qt event filter
# ---------------------------------------------------------------------------

_space_filter   = None
_saved_space_hk = None
_SPACE_PROP     = 'mpAnimSpaceFilterRef'   # key stored on QApplication across reloads


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
    app.setProperty(_SPACE_PROP, _space_filter)   # survive future reloads


def _restore_spacebar():
    global _space_filter, _saved_space_hk
    app = QtWidgets.QApplication.instance()
    # Retrieve any filter stored across reloads, even if _space_filter was reset
    stored = app.property(_SPACE_PROP)
    if stored is not None:
        app.removeEventFilter(stored)
        app.setProperty(_SPACE_PROP, None)
    if _space_filter is not None and _space_filter is not stored:
        app.removeEventFilter(_space_filter)
    _space_filter = None
    if _saved_space_hk is not None:
        cmds.hotkey(keyShortcut='space',
                    name=_saved_space_hk['press'],
                    releaseName=_saved_space_hk['release'])
        _saved_space_hk = None
    else:
        cmds.hotkey(keyShortcut='space', name='', releaseName='')


# ---------------------------------------------------------------------------
# Backtick (`) Qt event filter — toggle shot camera
# ---------------------------------------------------------------------------
# Maya's viewport intercepts the backtick key for tweak mode before the
# hotkey system fires, so cmds.hotkey cannot override it.  A Qt event
# filter catches the key at the application level instead.

_backtick_filter = None
_BACKTICK_PROP   = 'mpAnimBacktickFilterRef'


class _BacktickCamFilter(QtCore.QObject):

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.Type.KeyPress:
            return False
        if event.key() != QtCore.Qt.Key.Key_QuoteLeft:
            return False
        if event.isAutoRepeat():
            return False

        focus = QtWidgets.QApplication.focusWidget()
        if focus is not None:
            if isinstance(focus, (QtWidgets.QTextEdit,
                                  QtWidgets.QPlainTextEdit,
                                  QtWidgets.QLineEdit)):
                return False
            try:
                if bool(focus.inputMethodQuery(
                        QtCore.Qt.InputMethodQuery.ImEnabled)):
                    return False
            except Exception:
                pass

        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            return False

        try:
            import toggleShotCam
            toggleShotCam.toggle()
        except Exception as e:
            cmds.warning(f'shortCuts: toggleShotCam failed — {e}')
        return True


def _bind_backtick():
    global _backtick_filter
    _restore_backtick()
    app = QtWidgets.QApplication.instance()
    _backtick_filter = _BacktickCamFilter(app)
    app.installEventFilter(_backtick_filter)
    app.setProperty(_BACKTICK_PROP, _backtick_filter)


def _restore_backtick():
    global _backtick_filter
    app = QtWidgets.QApplication.instance()
    stored = app.property(_BACKTICK_PROP)
    if stored is not None:
        app.removeEventFilter(stored)
        app.setProperty(_BACKTICK_PROP, None)
    if _backtick_filter is not None and _backtick_filter is not stored:
        app.removeEventFilter(_backtick_filter)
    _backtick_filter = None


def set_shotcam_toggle(set_name, enabled, data):
    s = data['sets'].setdefault(set_name, {'hotkeys': {}, 'spacebar': False})
    s['shotcam_toggle'] = enabled
    _save_data(data)
    if data.get('active') == set_name:
        _bind_backtick() if enabled else _restore_backtick()


# ---------------------------------------------------------------------------
# Key buttons
# ---------------------------------------------------------------------------

class _KeyButton(QtWidgets.QPushButton):
    """Assignable key — colours reflect hotkey state."""
    clicked_key = QtCore.Signal(str)

    def __init__(self, entry, parent=None):
        super().__init__(entry['label'], parent)
        self.key = entry['key']
        self.setObjectName('keyBtn')
        self.setFixedSize(entry['w'], 26)
        self._state = ''
        self.set_state('free')
        self.clicked.connect(lambda: self.clicked_key.emit(self.key))

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        self.setProperty('state', state)


class _ModKeyButton(QtWidgets.QPushButton):
    """Modifier key (Shift/Ctrl/Alt) — sticky toggle."""

    def __init__(self, entry, parent=None):
        super().__init__(entry['label'], parent)
        self.key = entry['key']
        self.mod = entry['mod']
        self.setObjectName('modKeyBtn')
        self.setFixedSize(entry['w'], 26)
        self._active = False
        self._refresh()

    def set_active(self, active):
        if active == self._active:
            return
        self._active = active
        self._refresh()

    def _refresh(self):
        self.setProperty('active', 'true' if self._active else 'false')


class _DeadKeyButton(QtWidgets.QPushButton):
    """Non-assignable visual key (Win, Cmd, CapsLock, Menu)."""

    def __init__(self, entry, parent=None):
        super().__init__(entry['label'], parent)
        self.key = None
        self.setObjectName('deadKeyBtn')
        self.setFixedSize(entry['w'], 26)
        self.setEnabled(False)


# ---------------------------------------------------------------------------
# KeyboardWidget
# ---------------------------------------------------------------------------

class KeyboardWidget(QtWidgets.QWidget):
    key_selected      = QtCore.Signal(str)
    modifiers_changed = QtCore.Signal()

    def __init__(self, kb_type='pc', parent=None):
        super().__init__(parent)
        self._kb_type  = kb_type
        self._key_btns = {}                                     # maya_key -> _KeyButton
        self._mod_btns = {'alt': [], 'ctrl': [], 'shift': []}  # mod -> [_ModKeyButton]
        self._mods     = {'alt': False, 'ctrl': False, 'shift': False}
        self._selected = None
        self._root_layout = QtWidgets.QVBoxLayout(self)
        self._root_layout.setSpacing(2)
        self._root_layout.setContentsMargins(8, 4, 8, 4)
        self._build()

    def _build(self):
        while self._root_layout.count():
            item = self._root_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._key_btns.clear()
        for v in self._mod_btns.values():
            v.clear()
        self._selected = None

        bottom = _KB_BOTTOM_MAC if self._kb_type == 'mac' else _KB_BOTTOM_PC
        rows   = [*KB_COMMON_ROWS, bottom]

        for row_idx, row in enumerate(rows):
            row_w = QtWidgets.QWidget()
            row_l = QtWidgets.QHBoxLayout(row_w)
            row_l.setSpacing(3)
            offset = KB_OFFSETS[row_idx] if row_idx < len(KB_OFFSETS) else 0
            row_l.setContentsMargins(offset, 0, 0, 0)
            row_l.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

            for entry in row:
                if entry is None:
                    sp = QtWidgets.QWidget(); sp.setFixedWidth(8)
                    row_l.addWidget(sp)
                    continue
                t = entry['type']
                if t in ('key', 'space'):
                    btn = _KeyButton(entry)
                    btn.clicked_key.connect(self._on_key_clicked)
                    self._key_btns[entry['key']] = btn
                    row_l.addWidget(btn)
                elif t == 'mod':
                    btn = _ModKeyButton(entry)
                    btn.clicked.connect(
                        lambda _=False, m=entry['mod']: self.toggle_mod(m))
                    self._mod_btns[entry['mod']].append(btn)
                    row_l.addWidget(btn)
                elif t == 'dead':
                    row_l.addWidget(_DeadKeyButton(entry))

            row_l.addStretch()
            row_w.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Preferred,
                QtWidgets.QSizePolicy.Policy.Fixed)
            self._root_layout.addWidget(row_w)

        self._root_layout.addStretch()

    def switch_kb_type(self, kb_type):
        self._kb_type = kb_type
        self._build()
        for mod, active in self._mods.items():
            for btn in self._mod_btns[mod]:
                btn.set_active(active)

    # ── modifier state ──────────────────────────────────────

    def mods(self):
        return self._mods['alt'], self._mods['ctrl'], self._mods['shift']

    def set_mods(self, alt, ctrl, shift):
        for mod, active in (('alt', alt), ('ctrl', ctrl), ('shift', shift)):
            self._mods[mod] = active
            for btn in self._mod_btns[mod]:
                btn.set_active(active)
        self.modifiers_changed.emit()

    def set_mod(self, mod, active):
        if self._mods[mod] == active:
            return
        self._mods[mod] = active
        for btn in self._mod_btns[mod]:
            btn.set_active(active)
        self.modifiers_changed.emit()

    def toggle_mod(self, mod):
        self.set_mod(mod, not self._mods[mod])

    # ── key selection ───────────────────────────────────────

    def _on_key_clicked(self, key):
        self._selected = key
        self.key_selected.emit(key)

    def select_key(self, key):
        if key in self._key_btns:
            self._selected = key
            self.key_selected.emit(key)

    def clear_selection(self):
        self._selected = None

    def selected_key(self):
        return self._selected

    # ── visual update ───────────────────────────────────────

    def update_states(self, category_hotkeys=None, default_bindings=None):
        for key, btn in self._key_btns.items():
            btn.set_state('selected' if key == self._selected else 'free')


# ---------------------------------------------------------------------------
# MainPanel — category sidebar + hotkey list
# ---------------------------------------------------------------------------

class _HotkeyRow(QtWidgets.QWidget):
    mute_toggled   = QtCore.Signal(str, bool)   # slug, muted
    row_clicked    = QtCore.Signal(str)          # slug

    def __init__(self, slug, hk_data, parent=None):
        super().__init__(parent)
        self.slug = slug
        self.setObjectName('hotkeyRow')
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

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

    def mousePressEvent(self, event):
        self.row_clicked.emit(self.slug)
        super().mousePressEvent(event)



class MainPanel(QtWidgets.QWidget):
    set_selected    = QtCore.Signal(str)
    hotkey_clicked  = QtCore.Signal(str)   # slug

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._data = data
        self._selected_slug = None
        self._build_ui()
        active = data.get('active') or 'ps_anim'
        self._refresh_list(select=active)

    # ── build ──────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.addWidget(self._make_sidebar())
        body.addWidget(self._make_content())
        body.setSizes([180, 360])
        root.addWidget(body, 1)

    def _make_sidebar(self):
        w = QtWidgets.QWidget()
        w.setObjectName('sidebar')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(4, 4, 4, 4)
        btn_row.setSpacing(4)

        add_btn = QtWidgets.QPushButton('+')
        add_btn.setObjectName('sidebarBtn')
        add_btn.setToolTip('New category (copies selected)')
        add_btn.clicked.connect(self._new_set)
        btn_row.addWidget(add_btn)

        self._del_btn = QtWidgets.QPushButton('−')
        self._del_btn.setObjectName('sidebarBtn')
        self._del_btn.setToolTip('Delete category')
        self._del_btn.clicked.connect(self._delete_set)
        btn_row.addWidget(self._del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._list = QtWidgets.QListWidget()
        self._list.currentTextChanged.connect(self._on_set_changed)
        layout.addWidget(self._list, 1)

        apply_btn = QtWidgets.QPushButton('Apply Category')
        apply_btn.setObjectName('applyBtn')
        apply_btn.clicked.connect(self._apply)
        layout.addWidget(apply_btn)
        return w

    def _make_content(self):
        w = QtWidgets.QWidget()
        w.setObjectName('content')
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setContentsMargins(4, 4, 4, 4)
        btn_row.setSpacing(4)

        self._add_hk_btn = QtWidgets.QPushButton('+')
        self._add_hk_btn.setObjectName('sidebarBtn')
        self._add_hk_btn.setToolTip('Add hotkey — select a key in the Keyboard tab')
        self._add_hk_btn.clicked.connect(self._on_add_hotkey)
        btn_row.addWidget(self._add_hk_btn)

        self._del_hk_btn = QtWidgets.QPushButton('−')
        self._del_hk_btn.setObjectName('sidebarBtn')
        self._del_hk_btn.setToolTip('Remove selected hotkey')
        self._del_hk_btn.clicked.connect(self._on_delete_selected)
        btn_row.addWidget(self._del_hk_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

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
        managed = set(self._data.get('sets', {}).keys())
        for name in _user_sets():
            if name in managed:
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

        hotkeys = s.get('hotkeys', {})
        for i, (slug, hk) in enumerate(hotkeys.items()):
            row = _HotkeyRow(slug, hk)
            row.mute_toggled.connect(
                lambda s_, m, sn=set_name: self._on_mute(sn, s_, m))
            row.row_clicked.connect(self._on_row_selected)
            self._hotkey_layout.insertWidget(i, row)

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

    def _on_mute(self, set_name, slug, muted):
        set_muted(set_name, slug, muted, self._data)

    def _on_row_selected(self, slug):
        self._selected_slug = slug
        self.hotkey_clicked.emit(slug)

    def _on_add_hotkey(self):
        set_name = self.current_set()
        if not set_name or set_name == _BUILTIN_SET:
            return
        self.hotkey_clicked.emit('')

    def _on_delete_selected(self):
        set_name = self.current_set()
        if not set_name or set_name == _BUILTIN_SET or not self._selected_slug:
            return
        hotkeys = self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {})
        if self._selected_slug not in hotkeys:
            return
        reply = QtWidgets.QMessageBox.question(
            self, 'Delete Hotkey', 'Remove this hotkey from the category?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_hotkey(set_name, self._selected_slug, self._data)
        self._selected_slug = None
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

class KeyBinderPanel(QtCore.QObject):
    """Coordinator — owns the keyboard and assign widgets, wires them together.
    Call keyboard_widget() and assign_widget() to get the two tab contents."""
    hotkey_assigned = QtCore.Signal(str)

    def __init__(self, data, main_panel, kb_type='pc', parent=None):
        super().__init__(parent)
        self._data = data
        self._main = main_panel
        self._kb_widget    = self._build_keyboard_widget(kb_type)
        self._assign_widget = self._build_assign_widget()

    # ── public accessors ────────────────────────────────────

    def keyboard_widget(self):
        return self._kb_widget

    def assign_widget(self):
        return self._assign_widget

    # ── keyboard tab widget ─────────────────────────────────

    def _build_keyboard_widget(self, kb_type):
        w = QtWidgets.QWidget()
        w.setObjectName('keyBinderPanel')
        w.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        root = QtWidgets.QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header: PC/Mac toggle
        hdr = QtWidgets.QWidget()
        hdr.setObjectName('keyBinderPanel')
        hdr_l = QtWidgets.QHBoxLayout(hdr)
        hdr_l.setContentsMargins(8, 4, 8, 4)
        hdr_l.setSpacing(8)
        hdr_l.addStretch()

        self._pc_btn  = QtWidgets.QPushButton('PC')
        self._mac_btn = QtWidgets.QPushButton('Mac')
        for btn in (self._pc_btn, self._mac_btn):
            btn.setObjectName('modBtn')
            btn.setCheckable(True)
            btn.setFixedHeight(22)
        grp = QtWidgets.QButtonGroup(w)
        grp.addButton(self._pc_btn)
        grp.addButton(self._mac_btn)
        (self._mac_btn if kb_type == 'mac' else self._pc_btn).setChecked(True)
        self._pc_btn.toggled.connect(
            lambda checked: self._switch_kb('pc')  if checked else None)
        self._mac_btn.toggled.connect(
            lambda checked: self._switch_kb('mac') if checked else None)
        hdr_l.addWidget(self._pc_btn)
        hdr_l.addWidget(self._mac_btn)
        root.addWidget(hdr)

        # Keyboard fills space
        self._keyboard = KeyboardWidget(kb_type=kb_type)
        self._keyboard.key_selected.connect(self._on_key_selected)
        self._keyboard.modifiers_changed.connect(self._on_modifier_changed)
        root.addWidget(self._keyboard, 1)

        # Key display strip at bottom of keyboard tab
        strip = QtWidgets.QWidget()
        strip.setObjectName('assignSection')
        strip_l = QtWidgets.QHBoxLayout(strip)
        strip_l.setContentsMargins(10, 6, 10, 6)
        self._key_lbl = QtWidgets.QLabel('Select a key')
        self._key_lbl.setObjectName('keyDisplayLbl')
        self._status_lbl = QtWidgets.QLabel('')
        self._status_lbl.setObjectName('statusLbl')
        strip_l.addWidget(self._key_lbl)
        strip_l.addStretch()
        strip_l.addWidget(self._status_lbl)
        root.addWidget(strip)

        # Forward keyPressEvent from the keyboard tab widget
        w.keyPressEvent = self._key_press_event
        return w

    # ── runtime command tab widget ──────────────────────────

    def _build_assign_widget(self):
        w = QtWidgets.QWidget()
        w.setObjectName('assignSection')
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # Shared key display at top
        top = QtWidgets.QHBoxLayout()
        self._assign_key_lbl    = QtWidgets.QLabel('Select a key in the Keyboard tab')
        self._assign_key_lbl.setObjectName('keyDisplayLbl')
        self._assign_status_lbl = QtWidgets.QLabel('')
        self._assign_status_lbl.setObjectName('statusLbl')
        top.addWidget(self._assign_key_lbl)
        top.addStretch()
        top.addWidget(self._assign_status_lbl)
        lay.addLayout(top)

        # Description + lang + buttons
        mid = QtWidgets.QHBoxLayout()
        mid.setSpacing(6)
        self._desc_edit = QtWidgets.QLineEdit()
        self._desc_edit.setPlaceholderText('Short description')
        mid.addWidget(self._desc_edit, 2)
        self._py_rb  = QtWidgets.QRadioButton('Python')
        self._mel_rb = QtWidgets.QRadioButton('MEL')
        self._py_rb.setChecked(True)
        mid.addWidget(self._py_rb)
        mid.addWidget(self._mel_rb)
        self._clear_btn = QtWidgets.QPushButton('Clear')
        self._clear_btn.setObjectName('clearBtn')
        self._clear_btn.setEnabled(False)
        self._clear_btn.setToolTip('Remove binding from this key')
        self._clear_btn.clicked.connect(self._clear_binding)
        mid.addWidget(self._clear_btn)
        self._assign_btn = QtWidgets.QPushButton('Assign')
        self._assign_btn.setObjectName('assignBtn')
        self._assign_btn.setEnabled(False)
        self._assign_btn.clicked.connect(self._assign)
        mid.addWidget(self._assign_btn)
        lay.addLayout(mid)

        # Command area fills remaining space
        self._cmd_edit = QtWidgets.QPlainTextEdit()
        self._cmd_edit.setPlaceholderText('Paste command from Script Editor…')
        lay.addWidget(self._cmd_edit, 1)
        return w

    def _switch_kb(self, kb_type):
        self._keyboard.switch_kb_type(kb_type)
        self._data['keyboard'] = kb_type
        _save_data(self._data)
        self._update_keyboard()

    # ── refresh ────────────────────────────────────────────

    def refresh(self, set_name=None):
        if set_name is None:
            set_name = self._main.current_set()
        is_builtin = set_name == _BUILTIN_SET
        self._assign_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        self._keyboard.clear_selection()
        hint = 'Default set — read only' if is_builtin else 'Select a key'
        self._key_lbl.setText(hint)
        self._assign_key_lbl.setText(hint)
        self._status_lbl.setText('')
        self._assign_status_lbl.setText('')
        self._update_keyboard(set_name)

    def _update_keyboard(self, set_name=None):
        if set_name is None:
            set_name = self._main.current_set()
        hotkeys  = {} if set_name == _BUILTIN_SET else \
                   self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {})
        self._keyboard.update_states(hotkeys, _get_default_bindings())

    # ── slots ──────────────────────────────────────────────

    def _on_modifier_changed(self):
        self._update_keyboard()
        key = self._keyboard.selected_key()
        if key:
            self._on_key_selected(key)

    def select_slug(self, slug):
        key, alt, ctrl, shift = _slug_to_mods(slug)
        self._keyboard.set_mods(alt, ctrl, shift)
        self._keyboard.select_key(key)

    def _on_key_selected(self, key):
        set_name   = self._main.current_set()
        is_builtin = set_name == _BUILTIN_SET
        alt, ctrl, shift = self._keyboard.mods()
        slug    = _slug(key, alt, ctrl, shift)
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
            status = 'Already bound — editing existing.'
            self._clear_btn.setEnabled(True)
        else:
            self._desc_edit.clear()
            self._cmd_edit.clear()
            self._clear_btn.setEnabled(False)
            if slug in defaults:
                ann = _default_ann.get(defaults[slug], {}).get('annotation', defaults[slug])
                status = f'⚠  Overrides Maya default: {ann}'
            else:
                status = ''
        self._status_lbl.setText(status)
        self._assign_status_lbl.setText(status)
        self._assign_btn.setEnabled(True)
        self._update_keyboard()

    def _assign(self):
        key = self._keyboard.selected_key()
        if not key:
            return
        set_name = self._main.current_set()
        if not set_name or set_name == _BUILTIN_SET:
            return
        alt, ctrl, shift = self._keyboard.mods()
        desc = self._desc_edit.text().strip()
        cmd  = self._cmd_edit.toPlainText().strip()
        lang = 'python' if self._py_rb.isChecked() else 'mel'
        if not desc or not cmd:
            QtWidgets.QMessageBox.warning(
                self._assign_widget, 'Key Binder',
                'Description and command are both required.')
            return
        try:
            add_hotkey(set_name, key, alt, ctrl, shift, desc, cmd, lang, self._data)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self._assign_widget, 'Key Binder — Error',
                f'Failed to assign hotkey:\n\n{e}')
            return
        self._update_keyboard(set_name)
        self._clear_btn.setEnabled(True)
        self._status_lbl.setText('Assigned.')
        self._assign_status_lbl.setText('Assigned.')
        self.hotkey_assigned.emit(set_name)

    def _clear_binding(self):
        key = self._keyboard.selected_key()
        if not key:
            return
        set_name = self._main.current_set()
        if not set_name or set_name == _BUILTIN_SET:
            return
        alt, ctrl, shift = self._keyboard.mods()
        slug = _slug(key, alt, ctrl, shift)
        if slug not in self._data.get('sets', {}).get(set_name, {}).get('hotkeys', {}):
            return
        reply = QtWidgets.QMessageBox.question(
            self._assign_widget, 'Clear Binding',
            f'Remove the binding for {_key_display(key, alt, ctrl, shift)}?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        remove_hotkey(set_name, slug, self._data)
        self._desc_edit.clear()
        self._cmd_edit.clear()
        self._clear_btn.setEnabled(False)
        self._status_lbl.setText('')
        self._assign_status_lbl.setText('')
        self._update_keyboard(set_name)
        self.hotkey_assigned.emit(set_name)

    # ── physical keyboard input ─────────────────────────────

    def _key_press_event(self, event):
        focus = QtWidgets.QApplication.focusWidget()
        if isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit)):
            return
        key = event.key()
        if key == QtCore.Qt.Key.Key_Shift:
            self._keyboard.toggle_mod('shift'); return
        if key == QtCore.Qt.Key.Key_Control:
            self._keyboard.toggle_mod('ctrl');  return
        if key == QtCore.Qt.Key.Key_Alt:
            self._keyboard.toggle_mod('alt');   return
        maya_key = _QT_TO_MAYA_KEY.get(key)
        if maya_key:
            self._keyboard.select_key(maya_key)
            return
        super().keyPressEvent(event)


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


def _embed_rtc_editor():
    """Return Maya's native runtimeCommandEditor as a QWidget, or a fallback label."""
    try:
        tmp_win = cmds.window(visible=False)
        layout  = cmds.formLayout(parent=tmp_win)
        editor  = cmds.runtimeCommandEditor(parent=layout)
        cmds.showWindow(tmp_win)
        ptr = omui.MQtUtil.findControl(editor)
        if ptr:
            widget = wrapInstance(int(ptr), QtWidgets.QWidget)
            widget.setParent(None)   # detach from Maya window before we hide it
            cmds.window(tmp_win, edit=True, visible=False)
            return widget
        cmds.deleteUI(tmp_win)
    except Exception as e:
        cmds.warning(f'shortCuts: could not embed runtimeCommandEditor — {e}')

    fallback = QtWidgets.QLabel('Runtime Command Editor unavailable.')
    fallback.setObjectName('disabledHint')
    fallback.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    return fallback


class ShortCutsUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('shortCuts')
        self.setObjectName(WINDOW_NAME)
        self.setMinimumSize(900, 660)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window |
            QtCore.Qt.WindowType.WindowMinimizeButtonHint |
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

        # ── Outer horizontal splitter: left ~1/3, right ~2/3 ──
        self._main_panel = MainPanel(self._data)
        self._key_binder = KeyBinderPanel(
            self._data, self._main_panel,
            kb_type=self._data.get('keyboard', 'pc'))
        self._ref        = ReferenceBrowser()

        self._main_panel.set_selected.connect(self._key_binder.refresh)
        self._main_panel.hotkey_clicked.connect(self._key_binder.select_slug)
        self._key_binder.hotkey_assigned.connect(self._main_panel.refresh_hotkeys)

        # ── Right panel: 3-tab widget ──────────────────────
        self._right_tabs = QtWidgets.QTabWidget()

        self._right_tabs.addTab(self._key_binder.keyboard_widget(), 'Keyboard')
        self._right_tabs.addTab(self._key_binder.assign_widget(),   'Runtime Command')
        self._right_tabs.addTab(self._ref,                          'Reference')
        self._right_tabs.currentChanged.connect(self._on_right_tab_changed)

        # ── Horizontal splitter ────────────────────────────
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(self._main_panel)
        splitter.addWidget(self._right_tabs)
        splitter.setSizes([300, 600])
        splitter.setChildrenCollapsible(False)

        root.addWidget(splitter, 1)

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

    def _on_right_tab_changed(self, index):
        if index == 2:   # Reference tab
            self._ref.populate()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def init_hotkeys():
    if not mpAnimConfig.get_save_path_silent():
        return
    data = _load_data()
    if not data.get('sets'):
        return
    _init(data)


def show():
    parent = _maya_main_window()
    for child in parent.findChildren(QtWidgets.QDialog, WINDOW_NAME):
        child.close()
        child.deleteLater()
    ui = ShortCutsUI(parent)
    ui.show()

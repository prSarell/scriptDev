import maya.cmds as cmds

_APP_ATTR = '_wip_zxHotkeys_originals'

_KEYS = [
    {
        'id':         'frame_back',
        'key':        'z',
        'desc':       'Step back one frame',
        'py_command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True) - 1)',
    },
    {
        'id':         'frame_forward',
        'key':        'x',
        'desc':       'Step forward one frame',
        'py_command': 'import maya.cmds as cmds; cmds.currentTime(cmds.currentTime(q=True) + 1)',
    },
]


def _ensure_name_command(hk):
    rtc = 'mpAnim_' + hk['id']
    nc  = rtc + '_NC'
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
    try:
        cmds.nameCommand(nc, annotation=hk['desc'], command=rtc)
    except Exception:
        pass
    return nc


def bind_zx():
    reset_zx()
    originals = {}
    for hk in _KEYS:
        k = hk['key']
        try:
            originals[k] = {
                'press':   cmds.hotkey(keyShortcut=k, query=True, name=True)        or '',
                'release': cmds.hotkey(keyShortcut=k, query=True, releaseName=True) or '',
            }
        except Exception:
            originals[k] = {'press': '', 'release': ''}
        print('wip_zxHotkeys: saved original for "{}": {}'.format(k, originals[k]))

    app_obj = cmds.about(version=True)  # just a stable object to stash on; use module dict instead
    import sys
    sys.modules[__name__].__dict__[_APP_ATTR] = originals

    for hk in _KEYS:
        nc = _ensure_name_command(hk)
        try:
            cmds.hotkey(keyShortcut=hk['key'], name=nc, releaseName='')
            print('wip_zxHotkeys: bound "{}" -> {}'.format(hk['key'], nc))
        except Exception as e:
            print('wip_zxHotkeys: ERROR binding "{}": {}'.format(hk['key'], e))

    cmds.inViewMessage(amg='Z / X: <hl>frame step</hl> bound', pos='midCenter', fade=True)


def reset_zx():
    import sys
    originals = sys.modules[__name__].__dict__.pop(_APP_ATTR, None)
    for hk in _KEYS:
        k = hk['key']
        ob = (originals or {}).get(k, {})
        press   = ob.get('press',   '')
        release = ob.get('release', '')
        try:
            cmds.hotkey(keyShortcut=k, name=press, releaseName=release)
            print('wip_zxHotkeys: restored "{}" -> press="{}" release="{}"'.format(k, press, release))
        except Exception as e:
            print('wip_zxHotkeys: ERROR restoring "{}": {}'.format(k, e))
    cmds.inViewMessage(amg='Z / X: hotkeys <hl>reset</hl>', pos='midCenter', fade=True)


bind_zx()

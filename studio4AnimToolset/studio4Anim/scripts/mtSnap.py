import maya.cmds as cmds

_SHORT = {'translateX': 'tx', 'translateY': 'ty', 'translateZ': 'tz',
          'rotateX': 'rx', 'rotateY': 'ry', 'rotateZ': 'rz'}
_TRANS_ATTRS = ['translateX', 'translateY', 'translateZ']
_ROT_ATTRS = ['rotateX', 'rotateY', 'rotateZ']


def snap_to(which='transrot'):
    sel = cmds.ls(sl=True, long=True)
    if len(sel) < 2:
        cmds.inViewMessage(
            amg='<b>Snap:</b> Select objects to snap, then the target last.',
            pos='midCenter', fade=True)
        return

    master = sel[-1]
    cmds.undoInfo(openChunk=True)
    try:
        for slave in sel[:-1]:
            _snap_one(master, slave, which)
    finally:
        cmds.undoInfo(closeChunk=True)


def _snap_one(master, slave, which):
    trans_locked = [a for a in _TRANS_ATTRS if cmds.getAttr(slave + '.' + a, lock=True)]
    rot_locked   = [a for a in _ROT_ATTRS if cmds.getAttr(slave + '.' + a, lock=True)]

    if which == 'trans' and len(trans_locked) == 3:
        cmds.inViewMessage(
            amg='<b>Snap:</b> All translates locked on ' + slave.split('|')[-1],
            pos='midCenter', fade=True)
        return
    if which == 'rots' and len(rot_locked) == 3:
        cmds.inViewMessage(
            amg='<b>Snap:</b> All rotates locked on ' + slave.split('|')[-1],
            pos='midCenter', fade=True)
        return

    do_trans = which in ('transrot', 'trans')
    do_rot = which in ('transrot', 'rots')

    trans_skip = [a[-1].lower() for a in trans_locked] if do_trans else ['x', 'y', 'z']
    rot_skip   = [a[-1].lower() for a in rot_locked] if do_rot else ['x', 'y', 'z']

    # Constrain a throwaway duplicate rather than the slave itself: duplicate()
    # copies rotateOrder/jointOrient but drops incoming connections, so it's
    # freely constrainable even when the slave's channels are already keyed
    # (a constraint can't drive an attribute that has an animCurve connected
    # to it - it just silently fails to connect and nothing moves).
    dup = cmds.duplicate(slave, name='mtSnap_TEMP', parentOnly=True)[0]
    temp = cmds.parentConstraint(
        master, dup,
        skipTranslate=trans_skip, skipRotate=rot_skip,
        maintainOffset=False)
    cmds.delete(temp)

    attrs_to_apply = []
    if do_trans:
        attrs_to_apply += [a for a in _TRANS_ATTRS if a not in trans_locked]
    if do_rot:
        attrs_to_apply += [a for a in _ROT_ATTRS if a not in rot_locked]

    for full in attrs_to_apply:
        value = cmds.getAttr(dup + '.' + full)
        short = _SHORT[full]
        if cmds.keyframe(slave, attribute=short, query=True, name=True):
            cmds.setKeyframe(slave, attribute=short, value=value)
        else:
            cmds.setAttr(slave + '.' + full, value)

    cmds.delete(dup)
    cmds.select(slave)

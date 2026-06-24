import maya.cmds as cmds


def snap_to(which='transrot'):
    sel = cmds.ls(sl=True, long=True)
    if len(sel) < 2:
        cmds.inViewMessage(
            amg='<b>Snap:</b> Select objects to snap, then the target last.',
            pos='midCenter', fade=True)
        return
    master = sel[-1]
    for slave in sel[:-1]:
        _snap_one(master, slave, which)


def _snap_one(master, slave, which):
    trans_skip = [ax for ax, attr in zip(['x', 'y', 'z'],
                  ['.translateX', '.translateY', '.translateZ'])
                  if not cmds.getAttr(slave + attr, settable=True)]
    rot_skip   = [ax for ax, attr in zip(['x', 'y', 'z'],
                  ['.rotateX', '.rotateY', '.rotateZ'])
                  if not cmds.getAttr(slave + attr, settable=True)]

    if which == 'trans' and len(trans_skip) == 3:
        cmds.inViewMessage(
            amg='<b>Snap:</b> All translates locked on ' + slave.split('|')[-1],
            pos='midCenter', fade=True)
        return
    if which == 'rots' and len(rot_skip) == 3:
        cmds.inViewMessage(
            amg='<b>Snap:</b> All rotates locked on ' + slave.split('|')[-1],
            pos='midCenter', fade=True)
        return

    if which == 'transrot':
        temp = cmds.parentConstraint(
            master, slave,
            skipTranslate=trans_skip, skipRotate=rot_skip,
            maintainOffset=False)
    elif which == 'trans':
        temp = cmds.pointConstraint(master, slave, skip=trans_skip, maintainOffset=False)
    else:
        temp = cmds.orientConstraint(master, slave, skip=rot_skip, maintainOffset=False)

    for curve in (cmds.keyframe(slave, query=True, name=True) or []):
        for full, short in [('translateX', 'tx'), ('translateY', 'ty'), ('translateZ', 'tz'),
                             ('rotateX', 'rx'), ('rotateY', 'ry'), ('rotateZ', 'rz')]:
            if full in curve:
                cmds.setKeyframe(slave, attribute=short)

    cmds.delete(temp)
    cmds.select(slave)

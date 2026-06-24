import maya.cmds as cmds


def simple_constraint(cons_type, maintain_offset=True):
    """Last selected = driver, all others = driven. Ctrl = no offset (set in UI)."""
    sel = cmds.ls(sl=True)
    if len(sel) < 2:
        cmds.inViewMessage(
            amg='<b>Constrain:</b> Select driven objects, then driver last.',
            pos='midCenter', fade=True)
        return

    master = sel[-1:]
    slaves = sel[:-1]

    if cons_type == 'point':
        for ea in slaves:
            skip = [ax for ax, attr in zip(['x', 'y', 'z'],
                    ['.translateX', '.translateY', '.translateZ'])
                    if cmds.getAttr(ea + attr, lock=True)]
            cmds.pointConstraint(master, ea, maintainOffset=maintain_offset, skip=skip)

    elif cons_type == 'orient':
        for ea in slaves:
            skip = [ax for ax, attr in zip(['x', 'y', 'z'],
                    ['.rotateX', '.rotateY', '.rotateZ'])
                    if cmds.getAttr(ea + attr, lock=True)]
            cmds.orientConstraint(master, ea, maintainOffset=maintain_offset, skip=skip)

    elif cons_type == 'parent':
        for ea in slaves:
            cmds.parentConstraint(master, ea, maintainOffset=maintain_offset)

import maya.cmds as cmds
import maya.mel as mel


def _get_timeslider_range():
    tc = mel.eval("$tmpVar=$gPlayBackSlider")
    rng = cmds.timeControl(tc, q=True, rangeArray=True)
    # rangeArray end is exclusive — if spread is <=1 no range was drag-selected
    if (rng[1] - rng[0]) <= 1:
        start = int(cmds.playbackOptions(q=True, min=True))
        end   = int(cmds.playbackOptions(q=True, max=True))
    else:
        start = int(rng[0])
        end   = int(rng[1] - 1)
    return start, end


def bake_to_world():
    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.inViewMessage(
            amg='<b>WS Bake:</b> Select an object first.',
            pos='midCenter', fade=True)
        return
    if len(sel) > 1:
        cmds.inViewMessage(
            amg='<b>WS Bake:</b> Select one object only.',
            pos='midCenter', fade=True)
        return

    obj   = sel[0]
    short = obj.split('|')[-1].split(':')[-1]
    start, end = _get_timeslider_range()

    # Carrier group: constrain to object, bake, free
    grp     = cmds.group(empty=True, name=short + '_bakeGrp')
    tmp_con = cmds.parentConstraint(obj, grp, maintainOffset=False)[0]
    cmds.bakeResults(
        grp,
        time=(start, end),
        simulation=False,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    cmds.delete(tmp_con)

    # Locator parented under group, zeroed (sits at object world pos)
    loc = cmds.spaceLocator(name=short + '_bakeLoc')[0]
    cmds.parent(loc, grp)
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
        cmds.setAttr(loc + '.' + attr, 0)

    # Drive the original object from the locator
    cmds.parentConstraint(loc, obj, maintainOffset=False)

    cmds.select(grp)
    cmds.inViewMessage(
        amg='<b>WS Bake:</b> <hl>{}</hl> baked  ({}–{})'.format(short, start, end),
        pos='midCenter', fade=True)

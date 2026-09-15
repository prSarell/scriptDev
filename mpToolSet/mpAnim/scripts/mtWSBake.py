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

    start, end = _get_timeslider_range()

    # Single top group everything lands under. It never moves (identity
    # transform), so parenting the per-object carriers under it doesn't
    # affect the world-space values baked onto them.
    top_grp = cmds.group(empty=True, name='worldBake_grp')

    # Carrier groups: constrain each to its object first, then bake all
    # groups in a single bakeResults call (one scene evaluation per frame
    # instead of one per object per frame).
    carriers = []
    for obj in sel:
        short   = obj.split('|')[-1].split(':')[-1]
        grp     = cmds.group(empty=True, name=short + '_bakeGrp', parent=top_grp)
        tmp_con = cmds.parentConstraint(obj, grp, maintainOffset=False)[0]
        carriers.append((obj, short, grp, tmp_con))

    cmds.bakeResults(
        [c[2] for c in carriers],
        time=(start, end),
        simulation=False,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    cmds.delete([c[3] for c in carriers])

    for obj, short, grp, _ in carriers:
        # Locator parented under group, zeroed (sits at object world pos)
        loc = cmds.spaceLocator(name=short + '_bakeLoc')[0]
        cmds.parent(loc, grp)
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            cmds.setAttr(loc + '.' + attr, 0)

        # Drive the original object from the locator
        cmds.parentConstraint(loc, obj, maintainOffset=False)

    cmds.select(top_grp)
    if len(carriers) == 1:
        msg = '<b>WS Bake:</b> <hl>{}</hl> baked  ({}–{})'.format(
            carriers[0][1], start, end)
    else:
        msg = '<b>WS Bake:</b> <hl>{}</hl> objects baked  ({}–{})'.format(
            len(carriers), start, end)
    cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)

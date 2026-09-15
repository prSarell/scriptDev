import maya.cmds as cmds
import maya.mel as mel


def _get_timeslider_range():
    tc = mel.eval("$tmpVar=$gPlayBackSlider")
    rng = cmds.timeControl(tc, q=True, rangeArray=True)
    if (rng[1] - rng[0]) <= 1:
        start = int(cmds.playbackOptions(q=True, min=True))
        end   = int(cmds.playbackOptions(q=True, max=True))
    else:
        start = int(rng[0])
        end   = int(rng[1] - 1)
    return start, end


def bake_to_object():
    sel = cmds.ls(sl=True, long=True)
    if len(sel) < 2:
        cmds.inViewMessage(
            amg='<b>OS Bake:</b> Select driven object(s) first, then driver last.',
            pos='midCenter', fade=True)
        return

    driven_objs = sel[:-1]
    driver      = sel[-1]
    driver_short = driver.split('|')[-1].split(':')[-1]
    start, end = _get_timeslider_range()

    # Single top group under the driver everything lands under. It sits at
    # the driver's local origin (identity offset), so parenting the
    # per-driven carriers under it doesn't affect the values baked onto them.
    top_grp = cmds.group(empty=True, name='objectBake_grp')
    cmds.parent(top_grp, driver)
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
        cmds.setAttr(top_grp + '.' + attr, 0)

    # Carrier groups: constrain each to its driven object first, then bake
    # all groups in a single bakeResults call (one scene evaluation per
    # frame instead of one per object per frame).
    carriers = []
    for driven in driven_objs:
        short   = driven.split('|')[-1].split(':')[-1]
        grp     = cmds.group(empty=True, name=short + '_osBakeGrp', parent=top_grp)
        tmp_con = cmds.parentConstraint(driven, grp, maintainOffset=False)[0]
        carriers.append((driven, short, grp, tmp_con))

    cmds.bakeResults(
        [c[2] for c in carriers],
        time=(start, end),
        simulation=False,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    cmds.delete([c[3] for c in carriers])

    for driven, short, grp, _ in carriers:
        # Locator under group, zeroed
        loc = cmds.spaceLocator(name=short + '_osBakeLoc')[0]
        cmds.parent(loc, grp)
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            cmds.setAttr(loc + '.' + attr, 0)

        # Drive the original object from the locator
        cmds.parentConstraint(loc, driven, maintainOffset=False)

    cmds.select(top_grp)
    if len(carriers) == 1:
        msg = '<b>OS Bake:</b> <hl>{}</hl> → <hl>{}</hl>  ({}–{})'.format(
            carriers[0][1], driver_short, start, end)
    else:
        msg = '<b>OS Bake:</b> <hl>{}</hl> objects → <hl>{}</hl>  ({}–{})'.format(
            len(carriers), driver_short, start, end)
    cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)

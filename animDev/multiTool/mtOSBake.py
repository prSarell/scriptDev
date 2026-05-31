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
            amg='<b>OS Bake:</b> Select driven first, then driver last.',
            pos='midCenter', fade=True)
        return
    if len(sel) > 2:
        cmds.inViewMessage(
            amg='<b>OS Bake:</b> Select two objects only.',
            pos='midCenter', fade=True)
        return

    driven = sel[0]
    driver = sel[1]
    driven_short = driven.split('|')[-1].split(':')[-1]
    driver_short  = driver.split('|')[-1].split(':')[-1]
    start, end = _get_timeslider_range()

    # Carrier group parented under driver, constrained to driven, baked, freed
    grp = cmds.group(empty=True, name=driven_short + '_osBakeGrp')
    cmds.parent(grp, driver)
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
        cmds.setAttr(grp + '.' + attr, 0)

    tmp_con = cmds.parentConstraint(driven, grp, maintainOffset=False)[0]
    cmds.bakeResults(
        grp,
        time=(start, end),
        simulation=False,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    cmds.delete(tmp_con)

    # Locator under group, zeroed
    loc = cmds.spaceLocator(name=driven_short + '_osBakeLoc')[0]
    cmds.parent(loc, grp)
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
        cmds.setAttr(loc + '.' + attr, 0)

    # Drive the original object from the locator
    cmds.parentConstraint(loc, driven, maintainOffset=False)

    cmds.select(grp)
    cmds.inViewMessage(
        amg='<b>OS Bake:</b> <hl>{}</hl> → <hl>{}</hl>  ({}–{})'.format(
            driven_short, driver_short, start, end),
        pos='midCenter', fade=True)

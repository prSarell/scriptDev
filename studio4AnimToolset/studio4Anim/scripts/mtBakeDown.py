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


def _get_selected_anim_layer():
    for layer in cmds.ls(type='animLayer') or []:
        if layer == 'BaseAnimation':
            continue
        if cmds.animLayer(layer, q=True, selected=True):
            return layer
    return None


def _find_bake_rigs(obj):
    """Return top-level bake groups created by WS/OS bake for this object."""
    grps = []
    constraints = cmds.listRelatives(obj, children=True, type='parentConstraint') or []
    for con in constraints:
        drivers = cmds.parentConstraint(con, q=True, targetList=True) or []
        for driver in drivers:
            parents = cmds.listRelatives(driver, parent=True, fullPath=True) or []
            if parents:
                grps.append(parents[0])
    return grps


def bake_to_origin():
    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.inViewMessage(
            amg='<b>Bake Down:</b> Select one or more objects.',
            pos='midCenter', fade=True)
        return

    start, end = _get_timeslider_range()
    layer = _get_selected_anim_layer()

    bake_kwargs = dict(
        time=(start, end),
        simulation=False,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    if layer:
        bake_kwargs['destinationLayer'] = layer

    for obj in sel:
        # Collect bake rig roots before baking (constraint still live)
        bake_rigs = _find_bake_rigs(obj)

        cmds.bakeResults(obj, **bake_kwargs)

        constraints = cmds.listRelatives(obj, children=True, type='parentConstraint') or []
        if constraints:
            cmds.delete(constraints)

        for grp in bake_rigs:
            if cmds.objExists(grp):
                cmds.delete(grp)

    msg = '<b>Bake Down:</b> {} object(s) baked'.format(len(sel))
    if layer:
        msg += ' → layer <hl>{}</hl>'.format(layer)
    cmds.inViewMessage(
        amg=msg + '  ({}–{})'.format(start, end),
        pos='midCenter', fade=True)

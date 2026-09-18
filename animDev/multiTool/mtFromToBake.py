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


def bake_from_to():
    sel = cmds.ls(sl=True, long=True)
    if len(sel) < 2 or len(sel) % 2:
        cmds.inViewMessage(
            amg="<b>From/To Bake:</b> Select 'from'/'to' pairs — "
                "one 'from' then one 'to', repeated for each pair.",
            pos='midCenter', fade=True)
        return

    pairs = list(zip(sel[0::2], sel[1::2]))
    start, end = _get_timeslider_range()

    tmp_cons = [
        cmds.parentConstraint(frm, to, maintainOffset=False)[0]
        for frm, to in pairs
    ]

    # simulation=True: the 'from' side is typically driven by a running
    # dynamics sim (nCloth/nHair/nucleus), which needs every frame evaluated
    # in order -- a non-simulation bake is free to sample frames out of
    # sequence, which desyncs the sim from the constrained 'to' objects.
    cmds.bakeResults(
        [to for _, to in pairs],
        time=(start, end),
        simulation=True,
        sampleBy=1,
        attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'],
    )
    cmds.delete(tmp_cons)

    if len(pairs) == 1:
        frm, to = pairs[0]
        frm_short = frm.split('|')[-1].split(':')[-1]
        to_short  = to.split('|')[-1].split(':')[-1]
        msg = '<b>From/To Bake:</b> <hl>{}</hl> → <hl>{}</hl>  ({}–{})'.format(
            frm_short, to_short, start, end)
    else:
        msg = '<b>From/To Bake:</b> {} pair(s) baked  ({}–{})'.format(
            len(pairs), start, end)
    cmds.inViewMessage(amg=msg, pos='midCenter', fade=True)

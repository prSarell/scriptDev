import maya.cmds as cmds


def tile_keys(reps, direction):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.inViewMessage(
            amg='<b>Tile Keys:</b> Select objects and keys in the Graph Editor.',
            pos='midCenter', fade=True)
        return

    processed = 0
    for obj in sel:
        curves = cmds.keyframe(obj, query=True, name=True) or []
        for curve in curves:
            times = cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
            if len(times) < 2:
                continue

            t_min = min(times)
            t_max = max(times)
            cycle_len = t_max - t_min
            if cycle_len == 0:
                continue

            cmds.copyKey(curve, time=(t_min, t_max), option='keys')

            offsets = []
            if direction in ('forward', 'both'):
                offsets += [cycle_len * i for i in range(1, reps + 1)]
            if direction in ('backward', 'both'):
                offsets += [-cycle_len * i for i in range(1, reps + 1)]

            for offset in offsets:
                cmds.pasteKey(curve, timeOffset=offset, option='merge')

            processed += 1

    if not processed:
        cmds.inViewMessage(
            amg='<b>Tile Keys:</b> Select objects and keys in the Graph Editor.',
            pos='midCenter', fade=True)
        return

    cmds.inViewMessage(
        amg='<b>Tile Keys:</b> {} channel(s) — {} rep(s) tiled {}.'.format(processed, reps, direction),
        pos='midCenter', fade=True)

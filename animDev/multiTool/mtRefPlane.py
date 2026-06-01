import re
import maya.cmds as cmds

_TAG   = 'multiTool_refPlane'
_TZ    = -5.0
_TY    =  1.0
_TX    =  1.7
_SCALE =  0.268
_Y_STEP = 0.03   # nudge each additional plane down so they don't overlap


def _active_camera():
    # Outliner selection takes priority
    for node in (cmds.ls(selection=True, type='transform') or []):
        if cmds.listRelatives(node, shapes=True, type='camera'):
            return node

    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) != 'modelPanel':
        cmds.inViewMessage(
            amg='<b>Ref Plane:</b> Select a camera or click inside a viewport first.',
            pos='midCenter', fade=True)
        return None
    cam = cmds.modelEditor(panel, q=True, camera=True)
    if cmds.nodeType(cam) == 'camera':
        parents = cmds.listRelatives(cam, parent=True) or []
        cam = parents[0] if parents else cam
    return cam


def _cam_ref_planes(cam):
    """Return full DAG paths of tagged ref plane transforms parented under cam."""
    children = cmds.listRelatives(cam, children=True, type='transform',
                                   fullPath=True) or []
    return [c for c in children if _TAG in c.split('|')[-1]]


def add_ref_plane():
    cam = _active_camera()
    if not cam:
        return

    n = len(_cam_ref_planes(cam))

    result       = cmds.imagePlane(maintainRatio=False, name=_TAG + '#')
    ip_transform = result[0]
    ip_shape     = result[1]

    cmds.setAttr(ip_shape + '.displayMode', 3)  # RGBA

    cmds.parent(ip_transform, cam)
    for attr, val in [('.tx', _TX), ('.ty', _TY - n * _Y_STEP), ('.tz', _TZ),
                      ('.rx', 0),   ('.ry', 0),   ('.rz', 0),
                      ('.sx', _SCALE), ('.sy', _SCALE), ('.sz', _SCALE)]:
        cmds.setAttr(ip_transform + attr, val)

    cmds.select(ip_transform)
    cmds.inViewMessage(
        amg='<b>Ref Plane</b> added to <hl>' + cam + '</hl>.',
        pos='midCenter', fade=True)


def _find_seq_start(image_path):
    sep = '/' if '/' in image_path else '\\'
    folder = image_path[:image_path.rindex(sep) + 1]
    ext = '*' + image_path[image_path.rindex('.'):]
    files = cmds.getFileList(folder=folder, filespec=ext) or []
    numbers = []
    for f in files:
        matches = re.findall(r'\b\d+\b', f)
        if matches:
            numbers.append(int(matches[-1]))
    return min(numbers) if numbers else None


def sync_frame_offset():
    cam = _active_camera()
    if not cam:
        return

    transforms = _cam_ref_planes(cam)
    if not transforms:
        cmds.inViewMessage(
            amg='No ref planes found for <hl>' + cam + '</hl>.',
            pos='midCenter', fade=True)
        return

    scene_start = int(cmds.playbackOptions(q=True, minTime=True))
    synced = []

    for t in transforms:
        shapes = cmds.listRelatives(t, shapes=True, type='imagePlane') or []
        for s in shapes:
            image_path = cmds.getAttr(s + '.imageName')
            if not image_path:
                cmds.warning('mtRefPlane: no image loaded on {}.'.format(s))
                continue
            seq_start = _find_seq_start(image_path)
            if seq_start is None:
                cmds.warning('mtRefPlane: could not detect frame number from {}.'.format(image_path))
                continue
            # displayed_frame = current_time + frameOffset
            # at scene_start we want displayed_frame = seq_start
            frame_offset = seq_start - scene_start
            cmds.setAttr(s + '.frameOffset', frame_offset)
            synced.append((s, frame_offset))

    if synced:
        cmds.inViewMessage(
            amg='Frame offset auto-synced on <hl>{}</hl>.'.format(cam),
            pos='midCenter', fade=True)


def remove_ref_planes():
    cam = _active_camera()
    if not cam:
        return
    transforms = _cam_ref_planes(cam)
    if not transforms:
        cmds.inViewMessage(
            amg='No ref planes found for <hl>' + cam + '</hl>.',
            pos='midCenter', fade=True)
        return
    cmds.delete(transforms)
    cmds.inViewMessage(
        amg='<b>Ref Planes</b> removed from <hl>' + cam + '</hl>.',
        pos='midCenter', fade=True)

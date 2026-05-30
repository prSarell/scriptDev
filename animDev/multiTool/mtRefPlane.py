import maya.cmds as cmds

_TAG   = 'multiTool_refPlane'
_TZ    = -0.875
_TY    =  0.3
_TX    =  0.15
_SCALE =  0.025
_Y_STEP = 0.03   # nudge each additional plane down so they don't overlap


def _active_camera():
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) != 'modelPanel':
        cmds.inViewMessage(
            amg='<b>Ref Plane:</b> Click inside a viewport first.',
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

    result = cmds.promptDialog(
        title='Sync Frame Offset',
        message='Image sequence start frame:',
        text='1',
        button=['OK', 'Cancel'],
        defaultButton='OK',
        cancelButton='Cancel',
        dismissString='Cancel'
    )
    if result != 'OK':
        return

    try:
        seq_start = int(cmds.promptDialog(query=True, text=True))
    except ValueError:
        cmds.warning('mtRefPlane: invalid frame number.')
        return

    # displayed_frame = current_time + frameOffset
    # at scene_start we want displayed_frame = seq_start
    frame_offset = seq_start - scene_start

    for t in transforms:
        shapes = cmds.listRelatives(t, shapes=True, type='imagePlane') or []
        for s in shapes:
            cmds.setAttr(s + '.frameOffset', frame_offset)

    cmds.inViewMessage(
        amg='Frame offset set to <hl>{}</hl> on <hl>{}</hl>.'.format(
            frame_offset, cam),
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

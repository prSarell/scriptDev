import maya.cmds as cmds


def toggle(shot_cam=None, persp_cam='persp'):
    if shot_cam is None:
        try:
            import mpAnimConfig
            shot_cam = mpAnimConfig.get_shot_cam()
        except Exception:
            shot_cam = 'camera1'

    panel = cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
        panels = cmds.getPanel(type='modelPanel') or []
        panel = next((p for p in panels
                      if 'persp' in cmds.modelEditor(p, q=True, camera=True).lower()), None)
    if not panel:
        cmds.warning('toggleShotCam: no model panel found.')
        return

    if not cmds.objExists(shot_cam):
        cmds.warning('toggleShotCam: camera not found — ' + shot_cam)
        return

    current = cmds.modelEditor(panel, q=True, camera=True)
    current_cam = next((s for s in (cmds.listRelatives(current, shapes=True, path=True) or [current])
                        if cmds.nodeType(s) == 'camera'), current)
    shot_shape = next((s for s in (cmds.listRelatives(shot_cam, shapes=True, path=True) or [shot_cam])
                       if cmds.nodeType(s) == 'camera'), None)

    if not shot_shape:
        cmds.warning('toggleShotCam: no camera shape found under — ' + shot_cam)
        return

    if current_cam == shot_shape:
        cmds.modelEditor(panel, e=True, camera=persp_cam)
    else:
        cmds.modelEditor(panel, e=True, camera=shot_shape)

import maya.cmds as cmds

SHOT_CAM = 'camera1'  # ← change this to match your shot camera name

def _shape(cam):
    s = cmds.listRelatives(cam, shapes=True, path=True) or []
    return s[0] if s else cam

# Use focused panel if it's a viewport, otherwise find the persp panel
panel = cmds.getPanel(withFocus=True)
if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
    panel = next(
        (p for p in (cmds.getPanel(type='modelPanel') or [])
         if 'persp' in cmds.modelEditor(p, q=True, camera=True).lower()),
        None
    )

if not panel:
    cmds.warning('toggleShotCam: no model panel found.')
else:
    current = cmds.modelEditor(panel, q=True, camera=True)
    if _shape(current) == _shape(SHOT_CAM):
        cmds.modelEditor(panel, e=True, camera='persp')
    else:
        cmds.modelEditor(panel, e=True, camera=SHOT_CAM)

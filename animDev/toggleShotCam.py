import maya.cmds as cmds

SHOT_CAM = 'camera1'  # ← change this to match your shot camera name

panel = cmds.getPanel(withFocus=True)
if cmds.getPanel(typeOf=panel) != 'modelPanel':
    panel = cmds.getPanel(withLabel='Persp View') or panel

current = cmds.modelEditor(panel, query=True, camera=True)
current_shape = cmds.listRelatives(current, shapes=True) or [current]
shot_shape   = cmds.listRelatives(SHOT_CAM, shapes=True) or [SHOT_CAM]

if current_shape[0] == shot_shape[0]:
    cmds.modelEditor(panel, edit=True, camera='persp')
else:
    cmds.modelEditor(panel, edit=True, camera=SHOT_CAM)

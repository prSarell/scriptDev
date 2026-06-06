import maya.cmds as cmds
import maya.utils as mu


#Don't run if maya is launched with batch mode (so it doesn't break during renders)
if not cmds.about(batch=True):


	#Run wesAnimTools
	mu.executeDeferred('import wesAnimTools; wesAnimTools.UI();')


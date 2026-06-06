import maya.cmds as cmds
import maya.mel as mel
import imp


#Load in wesKeyEditor
import wesTools.wesKeyEditor
imp.reload(wesTools.wesKeyEditor)

#Load in wesScreenTracker
import wesTools.wesScreenTracker
imp.reload(wesTools.wesScreenTracker)


#Load in wesSceneSetup
import wesTools.wesSceneSetup
imp.reload(wesTools.wesSceneSetup)

#Load in finger select
#import wesTools.wesFingerSelect
#imp.reload(wesTools.wesFingerSelect)

#Load in wesOffsetAnim
import wesTools.wesOffsetAnim
imp.reload(wesTools.wesOffsetAnim)


#Load in wesRetime
import wesTools.wesRetime
imp.reload(wesTools.wesRetime)


#Load in wesImagePlanes
import wesTools.wesImagePlanes
imp.reload(wesTools.wesImagePlanes)

from wesTools.wesUtils import chosenModifiers
#import wesTools.wesUtils.chosenModifiers

def UI():
	if cmds.about(batch=True):
		print( "We're in Batch mode.. Will not open wesAnimTools UI!")
		return

	if cmds.dockControl("wesToolBarDock", exists=True):
		cmds.deleteUI("wesToolBarDock", control=True)

	if cmds.window("wesAnimToolsUI", exists=True, resizeToFitChildren=True):
		cmds.deleteUI("wesAnimToolsUI")
		#cmds.windowPref("wesAnimToolsUI", removeAll=True)

	user_width = 140
	user_height = 18

	#Create window interface
	wesAnimToolsUI = cmds.window('wesAnimToolsUI', title="wesAnimToolsUI", sizeable=True, width=user_width)
	
	#Choose either scrollLayout or rowColumnLayout
	#cmds.scrollLayout('wesLayout', height=650, width=user_width+23)
	cmds.rowColumnLayout('wesLayout')
	cmds.setParent('..')	
	cmds.showWindow(wesAnimToolsUI)


	##################Add Modules###################

	#SceneSetup Module
	wesTools.wesSceneSetup.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=False)

	#Screen Tracker Module
	wesTools.wesScreenTracker.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=False)

	#Finger Select
	#wesTools.wesFingerSelect.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=True)


	#wesOffsetAnim
	wesTools.wesOffsetAnim.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=True)


	#reTime module
	wesTools.wesRetime.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=True)


	#imageplane module
	wesTools.wesImagePlanes.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=False)

	#wesKeyEditor module
	wesTools.wesKeyEditor.UI(parentWindow='wesLayout', user_width=user_width, user_height=user_height, frameClosed=False)

	#Dock the window
	cmds.dockControl("wesToolBarDock", label="wesAnimTools", area="right", content=wesAnimToolsUI, allowedArea=['left', 'right'])

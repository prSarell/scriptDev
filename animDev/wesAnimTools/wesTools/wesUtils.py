from maya import cmds
from maya import mel


"""
===========================Wes Utils=====================================
	This is just a collection of frequently used commands to run the other
	tools with.  No need to adjust this code much.


	v1.1 - Converted chosenModifiers to have an argument "Shift","Ctrl","Keyless"

	v1.0 - Current set of wesUtils


=========================================================================
"""

#Shift Ctrl and Alt
def chosenModifiers(kind):
	"The kinds you can choose is 'Shift' , 'Ctrl', 'Keyless' as the argument"
	#State the modifier controls what to do
	whatMod = cmds.getModifiers()

	#This is shift key
	if kind == "Shift":
		if (whatMod & 1) > 0:
			return True


	#This is ctrl key
	if kind == "Ctrl":
		if (whatMod & 4) > 0:
			return True
		
	#No key selected
	if kind == "Keyless":
		if whatMod == 0:
			return True


	return False



def setActiveWindow():
	#Select the maya again
	name = mel.eval("$tmp=$gMainWindow")
	cmds.showWindow(name)



def editAttrChannels(objectNode, channel="all", zeroOut=False, lockOut=False):
	"A function to zero out or lock out the channels of either scale rotate or translate, or all of them."
	
	if channel == "all":
		manips = ['rotate','translate','scale']

	if channel == "rotate":
		manips = ['rotate']

	if channel == "translate":
		manips = ['translate']

	if channel == "scale":
		manips = ['scale']
	
	axis = ['X','Y','Z']




	for manip in manips:
		for axi in axis:
			#Zero out if argument requires:
			if zeroOut and not 'scale' in manip:
				try:
					cmds.setAttr(objectNode+"."+manip+axi,0)
				except:
					pass
			if zeroOut and 'scale' in manip:
				try:
					cmds.setAttr(objectNode+"."+manip+axi,1)
				except:
					pass

			if lockOut:
				try:
					cmds.setAttr(objectNode+"."+manip+axi, lock=True)
				except:
					pass
			

	if channel == "all" and zeroOut:
		cmds.setAttr(objectNode+".visibility", 1)
	if channel == "all" and lockOut:
		cmds.setAttr(objectNode+".visibility", lock=True)

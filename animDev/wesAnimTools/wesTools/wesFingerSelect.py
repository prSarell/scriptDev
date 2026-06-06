#####################################################################################
#######                        Wes Finger Select                              #######
#####################################################################################
import maya.cmds as cmds



#Gather Imports
import wesUtils
imp.reload(wesUtils)
from .wesUtils import setActiveWindow

from .wesUtils import chosenModifiers



#####################################################################################
#######                     Finger Naming Convention                          #######
#####################################################################################

p1 = "_fngPnkyFKA_CTRL"
p2 = "_fngPnkyFKB_CTRL"
p3 = "_fngPnkyFKC_CTRL"

r1 = "_fngRingFKA_CTRL"
r2 = "_fngRingFKB_CTRL"
r3 = "_fngRingFKC_CTRL"

m1 = "_fngMidFKA_CTRL"
m2 = "_fngMidFKB_CTRL"
m3 = "_fngMidFKC_CTRL"

i1 = "_fngIndFKA_CTRL"
i2 = "_fngIndFKB_CTRL"
i3 = "_fngIndFKC_CTRL"

t1 = "_fngThumbFKA_CTRL"
t2 = "_fngThumbFKB_CTRL"
t3 = "_fngThumbFKC_CTRL"



def updateCharSelect():
	sel = cmds.ls(sl=True)
	if sel == []:
		cmds.confirmDialog(message="Please select your character")
	else:
		char_name = sel[0][:sel[0].rindex(":")+1]
		cmds.textField("charSetforHands", e=True, text=char_name)

	setActiveWindow()

def fingerSelect(chosens,side):

	toggleShift = chosenModifiers(kind="Shift")
	toggleCtrl = chosenModifiers(kind="Ctrl")
	toggleReplace = chosenModifiers(kind="Keyless")

	char_name = cmds.textField("charSetforHands", q=True, text=True)
	if char_name == "":
		cmds.confirmDialog(message="Please set your char first by selecting a controller and pressing 'SET CHAR'")
	else:

		list_of_fingers = []

		for each in chosens:
			if cmds.objExists(char_name+side+each):
				list_of_fingers.append(char_name+side+each)


		print("shift is: " + str(toggleShift))
		print("ctrl is: " + str(toggleCtrl))
		print("nothing is: " + str(toggleReplace))
		cmds.select(list_of_fingers, tgl=toggleShift, deselect=toggleCtrl, replace=toggleReplace)

	setActiveWindow()





def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=True):
	if not parentWindow:
			wesAnimToolsUI = cmds.window('wesSceneSetupCustomUI', title="wes SceneSetup", sizeable=True, width=user_width)
			cmds.showWindow(wesAnimToolsUI)
			parentWindow = 'wesSceneSetupCustomUI'



	cmds.frameLayout(collapsable=True, label="Fingers", collapse=frameClosed, parent=parentWindow , width=user_width)

	rw = user_width/2
	fw =user_width/10
	but_heit = user_height


	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="set CHAR", bgc=[.8,.8,.8], command=lambda x:updateCharSelect(), width=user_width*.4)
	cmds.textField("charSetforHands", ed=False, width=user_width*.6)
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=2)

	cmds.button(l="LEFT ALL",bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[p1,p2,p3,r1,r2,r3,m1,m2,m3,i1,i2,i3,t1,t2,t3], side="l"), width=rw, height=but_heit)
	cmds.button(l="RIGHT ALL",bgc=[.8,.5,.5], command=lambda x:fingerSelect(chosens=[p1,p2,p3,r1,r2,r3,m1,m2,m3,i1,i2,i3,t1,t2,t3], side="r"), width=rw, height=but_heit)
	cmds.setParent('..')


	cmds.rowColumnLayout(numberOfColumns=10,)


	cmds.button(l="|", bgc=[.3,.3,.8], command=lambda x:fingerSelect(chosens=[p3], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.7], command=lambda x:fingerSelect(chosens=[r3], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.6], command=lambda x:fingerSelect(chosens=[m3], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.5], command=lambda x:fingerSelect(chosens=[i3], side="l"), width=fw, height=but_heit)
	cmds.button(l="T", bgc=[.3,.3,.4], command=lambda x:fingerSelect(chosens=[t3], side="l"), width=fw, height=but_heit)

	cmds.button(l="T", bgc=[.4,.3,.3], command=lambda x:fingerSelect(chosens=[t3], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.5,.3,.3], command=lambda x:fingerSelect(chosens=[i3], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.6,.3,.3], command=lambda x:fingerSelect(chosens=[m3], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.7,.3,.3], command=lambda x:fingerSelect(chosens=[r3], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.8,.3,.3], command=lambda x:fingerSelect(chosens=[p3], side="r"), width=fw, height=but_heit)

	cmds.button(l="|", bgc=[.3,.3,.8], command=lambda x:fingerSelect(chosens=[p2], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.7], command=lambda x:fingerSelect(chosens=[r2], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.6], command=lambda x:fingerSelect(chosens=[m2], side="l"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.3,.3,.5], command=lambda x:fingerSelect(chosens=[i2], side="l"), width=fw, height=but_heit)
	cmds.button(l="T", bgc=[.3,.3,.4], command=lambda x:fingerSelect(chosens=[t2], side="l"), width=fw, height=but_heit)

	cmds.button(l="T", bgc=[.4,.3,.3], command=lambda x:fingerSelect(chosens=[t2], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.5,.3,.3], command=lambda x:fingerSelect(chosens=[i2], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.6,.3,.3], command=lambda x:fingerSelect(chosens=[m2], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.7,.3,.3], command=lambda x:fingerSelect(chosens=[r2], side="r"), width=fw, height=but_heit)
	cmds.button(l="|", bgc=[.8,.3,.3], command=lambda x:fingerSelect(chosens=[p2], side="r"), width=fw, height=but_heit)


	cmds.button(l="4", bgc=[.3,.3,.8], command=lambda x:fingerSelect(chosens=[p1], side="l"), width=fw, height=but_heit)
	cmds.button(l="3", bgc=[.3,.3,.7], command=lambda x:fingerSelect(chosens=[r1], side="l"), width=fw, height=but_heit)
	cmds.button(l="2", bgc=[.3,.3,.6], command=lambda x:fingerSelect(chosens=[m1], side="l"), width=fw, height=but_heit)
	cmds.button(l="1", bgc=[.3,.3,.5], command=lambda x:fingerSelect(chosens=[i1], side="l"), width=fw, height=but_heit)
	cmds.button(l="T", bgc=[.3,.3,.4], command=lambda x:fingerSelect(chosens=[t1], side="l"), width=fw, height=but_heit)

	cmds.button(l="T", bgc=[.4,.3,.3], command=lambda x:fingerSelect(chosens=[t1], side="r"), width=fw, height=but_heit)
	cmds.button(l="1", bgc=[.5,.3,.3], command=lambda x:fingerSelect(chosens=[i1], side="r"), width=fw, height=but_heit)
	cmds.button(l="2", bgc=[.6,.3,.3], command=lambda x:fingerSelect(chosens=[m1], side="r"), width=fw, height=but_heit)
	cmds.button(l="3", bgc=[.7,.3,.3], command=lambda x:fingerSelect(chosens=[r1], side="r"), width=fw, height=but_heit)
	cmds.button(l="4", bgc=[.8,.3,.3], command=lambda x:fingerSelect(chosens=[p1], side="r"), width=fw, height=but_heit)


	cmds.button(l=".", bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[p3,p2,p1], side="l"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[r3,r2,r1], side="l"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[m3,m2,m1], side="l"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[i3,i2,i1], side="l"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[t3,t2,t1], side="l"), width=fw, height=but_heit*.7)

	cmds.button(l=".", bgc=[.6,.5,.5], command=lambda x:fingerSelect(chosens=[t3,t2,t1], side="r"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.6,.5,.5], command=lambda x:fingerSelect(chosens=[i3,i2,i1], side="r"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.6,.5,.5], command=lambda x:fingerSelect(chosens=[m3,m2,m1], side="r"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.6,.5,.5], command=lambda x:fingerSelect(chosens=[r3,r2,r1], side="r"), width=fw, height=but_heit*.7)
	cmds.button(l=".", bgc=[.6,.5,.5], command=lambda x:fingerSelect(chosens=[p3,p2,p1], side="r"), width=fw, height=but_heit*.7)






	
	cmds.setParent('..')





	cmds.rowColumnLayout(numberOfColumns=2)



	cmds.button(l="Tip",bgc=[.5,.5,1], command=lambda x:fingerSelect(chosens=[p3,r3,m3,i3], side="l"), width=rw, height=but_heit)
	cmds.button(l="Tip",bgc=[1,.5,.5], command=lambda x:fingerSelect(chosens=[p3,r3,m3,i3], side="r"), width=rw, height=but_heit)

	cmds.button(l="Mid",bgc=[.5,.5,.8], command=lambda x:fingerSelect(chosens=[p2,r2,m2,i2], side="l"), width=rw, height=but_heit)
	cmds.button(l="Mid",bgc=[.8,.5,.5], command=lambda x:fingerSelect(chosens=[p2,r2,m2,i2], side="r"), width=rw, height=but_heit)

	cmds.button(l="Base",bgc=[.5,.5,.7], command=lambda x:fingerSelect(chosens=[p1,r1,m1,i1], side="l"), width=rw, height=but_heit)
	cmds.button(l="Base",bgc=[.7,.5,.5], command=lambda x:fingerSelect(chosens=[p1,r1,m1,i1], side="r"), width=rw, height=but_heit)


	cmds.setParent('..')

	cmds.setParent('..')

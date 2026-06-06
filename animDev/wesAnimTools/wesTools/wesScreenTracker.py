"""
##########################################################################################################
######								Wesley's Screen Tracker script									######
######									heywesley@gmail.com											######
##########################################################################################################

A simple and fast way to see your spacing and arcs.	
Just like drawing dots on your monitor, except so much faster.
It also updates as you scrub your timeline!					
Select the object you want to track. Then load the camera, and	
create your tracker!  You can also move the main tracker.  For 	
example, if you selected the head control, you can move the tracker
to the nose. 														

v3.2 - line creation on by default. also adding in visibility distance.

v3.1 - Updated the camera chooser to be like the imageplane chooser with a drop down menu.

v3.0 - Now the ability to select multiple trackers. and delete them. Also to be able to hide them.

v2.2 - Fixing selection after done. selects object animated. also selects in list.

v2.1  - Fixed the creation of curve line by making a checkbox toggle.  Also fixed grouping of interface. (Feb 4, 2021)

v2.0  - Revamp whole interface! Much cleaner interface with a list of trackers.

v1.6  - Get to choose color instead of random

v1.5  - Added Annotations. Removed auto-bake first time.  

v1.4  - Added auto bake for first time
	  - Added random color attribute for multiple coloring	

v1.3  - Now conformed the curve to only be 1 object.  Much faster in creation time.	
	  - Added timeline adjustment, for start frame and end frame	

v1.2  - Curve created, Using skinBind to have it follow.
	  - Further updates will have just one curve to be faster,
		on creation. (Thanks to Thiago Martins and Sebastian Trujillo for the ideas and help!!!)

v1.1  - Curve created, but using scriptJob to update

v1.0  - Uses joints, and sets your viewport to view joints with xray
	  - Updates by scrubbing your timeline.  Best is to press play on every frame. 	

##########################################################################################################
"""

import maya.cmds as cmds
import maya.mel as mel
import imp
from functools import partial

#Gather Imports
import wesTools.wesUtils
imp.reload(wesTools.wesUtils)
from .wesUtils import setActiveWindow
from .wesUtils import editAttrChannels
from .wesUtils import chosenModifiers

usr_timeline = True

def runWesTracker(chooseColor=1):
	
	if not len(cmds.ls(sl=True)) == 1:
		cmds.confirmDialog(message="Please select one object you want to track!")
		return
	
	# camera_name = cameraChooser()
	# if camera_name == "dismiss":
	# 	return

	#Choosing Camera
	cameras_shape = cmds.ls(type='camera')
	cameras = ["World_Space"]
	for ea in cameras_shape:
		cameras.extend(cmds.listRelatives(ea, parent=True))

	#Making camera selection with UI 
	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)
	
	user_width = 400
	user_height = 20

	wesCameraUI = cmds.window('wesCameraChooser', title="Screen / World Space?", sizeable=True, width=user_width, height=50)
	cmds.showWindow(wesCameraUI)
	parentWindow = 'wesCameraChooser'
	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.text(l="Would you want the tracker to be in screen space or world space? :)")
	cmds.separator(style="none",height=16)
	cmds.optionMenu('cameraChoices', label='Choose Space:')
	for camera in cameras:
		cmds.menuItem(label=camera)
	cmds.separator(style="none",height=8)
	cmds.setParent('..')
	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Cancel", command=lambda x:runWesTrackerPartTwo(update=False, chooseColor=chooseColor), width=user_width*.5, height=user_height,bgc=[.6,.3,.3])
	cmds.button(l="Choose This!", command=lambda x:runWesTrackerPartTwo(update=True, chooseColor=chooseColor), width=user_width*.5, height=user_height, bgc=[.3,.6,.3])
	cmds.setParent('..')

def runWesTrackerPartTwo(update, chooseColor):
	sel = cmds.ls(sl=True)
	
	#Close window and return if nothing chosen.
	if update == False:
		if cmds.window("wesCameraChooser", exists=True):
			cmds.deleteUI("wesCameraChooser")
			cmds.windowPref("wesCameraChooser", removeAll=True)
		return

	#Main group
	if not cmds.objExists("wes_ScreenTrackers"):
		cmds.group(empty=True,name="wes_ScreenTrackers")
		cmds.setAttr("wes_ScreenTrackers.useOutlinerColor" , True)
		cmds.setAttr ("wes_ScreenTrackers.outlinerColor" , .3, .44, .19)
		#cmds.parent("World_Space", "wes_ScreenTrackers")
	

	#Find info from camera choise UI
	camera_name = cmds.optionMenu('cameraChoices', q=True, value=True)

	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)

	#Just in case World_Space got deleted
	if camera_name == "World_Space":
		if not cmds.objExists("World_Space"):

			world_obj = cmds.createNode('transform', name="World_Space")
			cmds.parent(world_obj, "wes_ScreenTrackers")
			cmds.setAttr("World_Space.useOutlinerColor" , True)
			cmds.setAttr ("World_Space.outlinerColor" , .3, .44, .19)		

	if cmds.checkBox("wantCurve", query=True, value=True) == True:
		create_curve = True
	else:
		create_curve = False	

	arc_size = float(cmds.floatField("wa_size", q=True, value=True))

	#If I want to track edges... Not sure if its done yet.
	# if ".e[" in sel[0]:
	# 	print( "Edges are selected!!")
	# 	mel.eval("rivet;")
	# 	new_rivet = cmds.ls(sl=True)
	#Object to track is now based on the 

	
	for track_object in sel:
		#RUN THE COMMAND! WOOHOOO!
		wesTracker(track_object, camera_name,arc_size, chooseColor=chooseColor, create_curve=create_curve)

	#To set it to a small joint size as a start
	cmds.jointDisplayScale(0.01)
	
	setActiveWindow()

def wesTracker(track_object,camera_name, arc_size, chooseColor, create_curve=False):


	#Official Names
	#MF means Maya Friendly.  For Naming convention
	mf_track_object = mayaCleanName(track_object)
	mf_camera_name = mayaCleanName(camera_name)

	jnt_name = mf_track_object+"_dot"+"_marker"
	tracker_frame_grp = mf_track_object+"_dot"+"_jnts_GRP"
	curve_frame_grp = mf_track_object+"_dot"+"_curve_GRP"
	curve_frame = mf_track_object+"_dot"+"_curve"
	marker_tracker = jnt_name+"_TRACKER"
	marker_tracker_grp = jnt_name+"_TRACKER_GRP"

	master_group = mf_track_object+"_dot"

	ghost_visiblity = cmds.intField("ghost_visiblity_textBox", q=True, v=True)
	current_time = cmds.currentTime(q=True)
	list_of_markers = []

	color_scheme = {1 : [22, 21],
					2 : [12,20],
					3 : [29, 28],
					4 : [23, 29]}

	
	if not cmds.button("usr_start_fr", q=True, l=True) == "":
		start_fr = int(cmds.button("usr_start_fr", q=True, l=True))
		end_fr = int(cmds.button("usr_end_fr", q=True, l=True))
	else:
		start_fr = int(cmds.playbackOptions(q=True, minTime=True))
		end_fr = int(cmds.playbackOptions(q=True, maxTime=True))

	def createMarker(kind,naming,color=[12,20], cv_amount=2):
		#Joints:
		if kind == "joints":
			cmds.select(clear=True)
			tmp_name = cmds.joint(position=[0,0,0], radius=arc_size)

			#Change color
			cmds.setAttr(tmp_name+".overrideEnabled",1)
			cmds.setAttr(tmp_name+".overrideColor",color[0])

		#Curve
		if kind == "curve":
			pos_amount = []
			key_amount = []
			for point in range(cv_amount):
				pos_amount.append((0,0,0))
				key_amount.append(point)

			tmp_name = cmds.curve(d=1, p=pos_amount, k=key_amount)
			#Change color
			cmds.setAttr(tmp_name+".overrideEnabled",1)
			cmds.setAttr(tmp_name+".overrideColor",color[1])

		cmds.rename(tmp_name,naming)
		return naming


	def createTracker():

		#Check to see if theres one that exists
		if cmds.objExists(marker_tracker) == True:
			cmds.confirmDialog(message="You already created one for this object and for this camera. Try another object =)")
			return


		#Create Master Curve
		createMarker("joints", marker_tracker,)
		cmds.setAttr(marker_tracker+".scaleX", keyable=False, lock=True)
		cmds.setAttr(marker_tracker+".scaleY", keyable=False, lock=True)
		cmds.setAttr(marker_tracker+".scaleZ", keyable=False, lock=True)
		cmds.setAttr(marker_tracker+".overrideEnabled",1)
		cmds.setAttr(marker_tracker+".overrideColor",14)
		cmds.setAttr(marker_tracker+".visibility", lock=True)
		cmds.setAttr(marker_tracker+".radius", float(arc_size)*1.35)
		cmds.group(marker_tracker, name=marker_tracker_grp)
		cmds.parentConstraint(track_object, marker_tracker_grp)


		#Create Groups:
		cmds.group(empty=True,name=master_group)
		cmds.group(empty=True,name=curve_frame_grp)
		cmds.group(empty=True,name=tracker_frame_grp)
		#Make sure this group follows so the joints show at camera space?
		cmds.parentConstraint(camera_name, tracker_frame_grp, maintainOffset=False)
		cmds.parent(tracker_frame_grp,master_group)
		cmds.parent(curve_frame_grp,master_group)
		cmds.parent(marker_tracker_grp,master_group)

		
		for frame in range(start_fr,end_fr):

			marker_frame = jnt_name+"_"+str(frame)
			createMarker("joints", marker_frame, color=color_scheme[chooseColor])


			#Constrain and key on and off
			tmp_constraint = cmds.parentConstraint(marker_tracker, marker_frame, maintainOffset=False)
			cmds.setAttr(tmp_constraint[0]+".enableRestPosition",0)
			cmds.setKeyframe(tmp_constraint[0]+".w0", time=(frame-1), value=0)
			cmds.setKeyframe(tmp_constraint[0]+".w0", time=frame, value=1)
			cmds.setKeyframe(tmp_constraint[0]+".w0", time=(frame+1), value=0)
			cmds.scaleConstraint(marker_tracker, marker_frame, offset=[0.8,0.8,0.8])

			#Ghosting the Visibility!
			cmds.setKeyframe(marker_frame+".visibility", time=(frame - ghost_visiblity - 1), value=0)
			cmds.setKeyframe(marker_frame+".visibility", time=(frame - ghost_visiblity), value=1)
			cmds.setKeyframe(marker_frame+".visibility", time=(frame + ghost_visiblity), value=1)
			cmds.setKeyframe(marker_frame+".visibility", time=(frame + ghost_visiblity + 1), value=0)
			#cmds.cutKey(marker_frame, attribute="visibility", time=(current_time,current_time))


			list_of_markers.append(marker_frame)
			#Lock markers
			editAttrChannels(marker_frame,zeroOut=True)

			#Add to the group
			cmds.parent(marker_frame,tracker_frame_grp)


		#Ctrl Key is On
		if create_curve == True:
			#Create one single curve for all the joints:
			##############################################################################################
			length_of_curve = end_fr - start_fr
			createMarker("curve", curve_frame, color=color_scheme[chooseColor], cv_amount=length_of_curve)


			#Connect Curve to Joints
			counter = start_fr
			for cv_num in range(length_of_curve):
				current_marker = jnt_name+"_"+str(counter)
				tmp_target = cmds.xform(current_marker, query=True, t=True, ws=True)
				cmds.xform(curve_frame+".cv["+str(cv_num)+"]", t=tmp_target)
				counter += 1

			tmp_skinCluster = cmds.skinCluster(list_of_markers,curve_frame)[0]

			counter = start_fr
			for cv_num in range(length_of_curve):
				current_marker = jnt_name+"_"+str(counter)
				cmds.skinPercent(tmp_skinCluster, curve_frame+".cv["+str(cv_num)+"]",tv=(current_marker,1))
				counter += 1

			cmds.parent(curve_frame,curve_frame_grp)
			#############################################################################################
			#This is to bake out the position
			#playThroughOnce(start_fr,end_fr,master_group)

		cmds.parent(master_group, "wes_ScreenTrackers")
		turnOnViewport()
		cmds.currentTime(start_fr)
		cmds.select(track_object)

	#Temporarily turn off auto key frame to see if it fixes the ghosting issue
	cmds.autoKeyframe(state=False)
	createTracker()
	cmds.autoKeyframe(state=True)
	refreshList()
	cmds.textScrollList( "listTrackers", edit=True, selectItem=master_group)
	setActiveWindow()

def deleteTracker():
	#Ctrl Key is On
	if chosenModifiers(kind="Ctrl") == True:
		cmds.delete("wes_ScreenTrackers")
		refreshList()
	
	else:
		try:
			track_object = cmds.textScrollList( "listTrackers", query=True, selectItem=True)
			for track in track_object:
				cmds.delete(track)
			refreshList()
		except:
			cmds.confirmDialog(message='Please Select a tracker from the list :)')
			return

	if cmds.textScrollList( "listTrackers", query=True, numberOfItems=True) == 0:
		#SET THE VIEWPORT SETTINGS
		viewports =  cmds.getPanel( type='modelPanel' )
		for vp in viewports:
			cmds.modelEditor(vp,edit=True, joints=False, jointXray=False)
	return


# def cameraChooser():
# 	#Camera
# 	cameras = ["World_Space"]
# 	cameras.extend(cmds.listCameras(p=True))

# 	result = cmds.confirmDialog(m="Do you want camera space or world space for trackers?", button=cameras)
# 	if "Shape" in result:
# 		result = cmds.listRelatives(result, p=1)[0]
# 	print( "Chosen Camera --> " + result)
# 	return result


def setFrameRange(user_width):
	global usr_timeline

	start_fr = int(cmds.playbackOptions(q=True, minTime=True))
	end_fr = int(cmds.playbackOptions(q=True, maxTime=True))

	if usr_timeline:
		cmds.button("butt_timeline", edit=True, l="Custom:", bgc=[.7,.7,.9], width=user_width*.33)
		cmds.button("usr_start_fr", edit=True, l=start_fr, en=True, width=user_width*.33)
		cmds.button("usr_end_fr", edit=True, l=end_fr, en=True, width=user_width*.33)
		usr_timeline = False
	else:
		cmds.button("butt_timeline", edit=True, l="Use Timeline Range", bgc=[.5,.5,.7], width=user_width*.98)
		cmds.button("usr_start_fr", edit=True, l="", en=False, width=user_width*.01)
		cmds.button("usr_end_fr", edit=True, l="", en=False, width=user_width*.01)
		usr_timeline = True


def turnOnViewport():

	viewports = cmds.getPanel(type='modelPanel')
	cmds.playbackOptions(e=True,playbackSpeed=0, maxPlaybackSpeed=1)
	for vp in viewports:
		#cmds.isolateSelect(vp, state=False)
		cmds.modelEditor(vp,edit=True, joints=True, jointXray=True)

def playThroughOnce(start_fr,end_fr,item):

	viewports = cmds.getPanel(type='modelPanel')
	cmds.select(item)

	for vp in viewports:
		#cmds.isolateSelect(vp, state=True)
		cmds.isolateSelect(vp, addSelected=True)

	save_start = int(cmds.playbackOptions(q=True, min=True))
	save_end = int(cmds.playbackOptions(q=True, max=True))
	print( " in run setup once :  " + str(save_start))
	print( " in run setup once :  " + str(save_end))

	cmds.playbackOptions(e=True, min=start_fr)    
	cmds.playbackOptions(e=True, max=end_fr)
	
	cmds.playbackOptions(e=True,playbackSpeed=0, maxPlaybackSpeed=0)
	cmds.currentTime(start_fr)
	cmds.play( record=True )


	#We have to evalDeferred this so after its done playing once, it will run the rest of the command
	cmds.evalDeferred("wesAnimTools.wesScreenTracker.turnOnViewport()")
	


def selectTracker():
	try:
		track_object = cmds.textScrollList( "listTrackers", query=True, selectItem=True)
		new_sel = []
		for track in track_object:
			new_sel.append(track+"_marker_TRACKER")

		cmds.select(new_sel)
	except:
		cmds.confirmDialog(message='Please Select a tracker from the list')
		return
	
def toggleVisibility():
	try:
		track_object = cmds.textScrollList( "listTrackers", query=True, selectItem=True)
		for track in track_object:
			cmds.setAttr(track+".visibility", not cmds.getAttr(track+".visibility"))
		turnOnViewport()
	except:
		cmds.confirmDialog(message='Please Select a tracker from the list')
		return

def updateSize():
	try:
		track_object = cmds.textScrollList( "listTrackers", query=True, selectItem=True)
	except:
		cmds.confirmDialog(message='Please Select a tracker from the list')
		return

	arc_size = cmds.floatField("wa_size", q=True, value=True)

	for track in track_object:
		marker_tracker = track+"_marker_TRACKER"
		tracker_frame_grp = track+"_jnts_GRP"


		cmds.setAttr(marker_tracker+".radius", float(arc_size)*1.5)
		the_joints = cmds.listRelatives(tracker_frame_grp, children=True, type="joint")

		setActiveWindow()

		for jnt in the_joints:
			print( jnt)
			cmds.setAttr(jnt+".radius", float(arc_size))

		setActiveWindow()

def mayaCleanName(inputName):
	new_name = inputName.replace("|","_")
	new_name = new_name.replace(":","_")
	return new_name



def addCurrentStartTime():
	value = int(cmds.currentTime(q=True))
	cmds.button("usr_start_fr", edit=True, l=value)

def addCurrentEndTime():
	value = int(cmds.currentTime(q=True))
	cmds.button("usr_end_fr", edit=True, l=value)


def refreshList():
	#Clear out the list first
	cmds.textScrollList( "listTrackers", edit=True, removeAll=True)

	if not cmds.objExists("wes_ScreenTrackers"):
		return
	trackers = cmds.listRelatives("wes_ScreenTrackers", children=True)
	if not trackers == None:
		#Remove the world space node
		trackers = [x for x in trackers if not x == "World_Space"]
		#Then add to the list
		for track in trackers:
			cmds.textScrollList( "listTrackers", edit=True, append=track)


def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=False):
	if not parentWindow:
		if cmds.window("wesScreenTrackerCustomUI", exists=True, resizeToFitChildren=True):
			cmds.deleteUI("wesScreenTrackerCustomUI")

		wesAnimToolsUI = cmds.window('wesScreenTrackerCustomUI', title="wesScreenTracker", sizeable=True, width=user_width)
		cmds.showWindow(wesAnimToolsUI)
		parentWindow = 'wesScreenTrackerCustomUI'

	cmds.frameLayout(collapsable=True, label="Screen Tracker", collapse=frameClosed, parent=parentWindow,width=user_width)

	cmds.rowColumnLayout(numberOfColumns=3)
	cmds.button("butt_timeline", l="Use Timeline Range", bgc=[.5,.5,.7], command=lambda x:setFrameRange(user_width=user_width), width=user_width*.98, height=user_height*1, annotation="click to change to custom range")
	cmds.button("usr_start_fr", l="", width=user_width*.01, height=user_height*1, command=lambda x:addCurrentStartTime(), en=False, annotation="click to change start frame to your current frame")
	cmds.button("usr_end_fr",l="",width=user_width*.01, height=user_height*1, command=lambda x:addCurrentEndTime(), en=False, annotation="click to change end frame to your current frame")
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.text("Ghost Distance: ")
	cmds.intField("ghost_visiblity_textBox", ed=True, value=5, width=user_width*.4, height=user_height, annotation="How far you want to see your trackers for.")
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=3)
	cmds.checkBox("wantCurve", l="", value=True, align="left", annotation="Check this on if you want a line connecting the dots!")
	cmds.button(l="Create Arc", command=lambda x:runWesTracker(chooseColor=1), width=user_width*.5, height=user_height*1, bgc=[.3,.6,.3], annotation="Right click to choose different colors")
	cmds.popupMenu()
	cmds.menuItem('Yellow', command=lambda x:runWesTracker(chooseColor=1))
	cmds.menuItem('Red', command=lambda x:runWesTracker(chooseColor=2))
	cmds.menuItem('Blue', command=lambda x:runWesTracker(chooseColor=3))
	cmds.menuItem('Green', command=lambda x:runWesTracker(chooseColor=4))

	cmds.button(l="Delete Arc", command=lambda x:deleteTracker(), width=user_width*.4, height=user_height*1,bgc=[.6,.3,.3], annotation="Ctrl = delete all Arcs")

	cmds.setParent('..')


	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.textScrollList( "listTrackers", allowMultiSelection=True, numberOfRows=7,  width=user_width, selectCommand=partial (selectTracker), dkc=partial (deleteTracker) )
	cmds.popupMenu()
	cmds.menuItem('Refresh', command=lambda x:refreshList())
	refreshList()
	cmds.button(l="Toggle Visibility", command=lambda x:toggleVisibility(), width=user_width, height=user_height)
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Update Size  :", bgc=[.4,.4,.4], command=lambda x:updateSize(), width=user_width*.6, height=user_height)
	cmds.floatField("wa_size", ed=True, value=10, precision=1, width=user_width*.4, height=user_height, enterCommand=lambda x:updateSize(), annotation="Update current joint size.")
	
	cmds.setParent('..')




	cmds.setParent('..')
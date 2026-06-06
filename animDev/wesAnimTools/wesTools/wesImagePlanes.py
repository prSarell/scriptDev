
"""
#####################################################################################
#######                        Wes Image Planes                               #######
#####################################################################################
	To run, place script in scripts folder, then enter this python command:
	
	import wesImagePlanes
	wesImagePlanes.UI()
	
	v1.7d - Added a line to make sure frameOut is long enough for .mov files to play

	v1.7c - fixing camera change by locking channels before the switch

	v1.7b - added ability to change cameras

	v1.7a - Make sure cache range is longer than shot range.
	
	v1.7 - multiple selections possible. ***STILL NEED TO WORK ON THE SHIFTING ITEMS TOGETHER***

	v1.6a - added ability to look for default camera as selection to the drop down menu.

	v1.6 - Automatically add the name of the ref file to the input box!

	v1.5a - Fix it if its only one image.

	v1.5 - Added automatic frame offset! Will find the beginning of the sequence and line it up with your start of the shot!

	v1.4b - reset Scale

	v1.4a - Supports .mov files

	v1.4 - creating Imageplane is now a drop down menu!
		 - Will say what imageplane depth it is


	v1.3 - Make Depth and Offsets Adjustment Dynamic
		 - Added reset button for X and Y when pressing right click.
		 - centerized the depth control

	v1.2 - added transparency UI feature

	v1.1 - Refined imagePlane setup to work with rest of the tools.  Cleaned up general things.



	v1.0 -  First build, to manage imageplanes attached to cameras


	Any questions please contact me at heywesley@gmail.com

"""





import maya.cmds as cmds
import maya.mel as mel
import re
from functools import partial

default_main_cam = "shaker"

def findLowestNumber(file_path):

	#Sort through the reference file to find the IMG sequence starting number:
	file_folder = file_path[:file_path.rindex("/")+1]
	file_extension = "*"+file_path[file_path.rindex("."):]
	print( file_folder)
	print( file_extension)
	
	all_files = cmds.getFileList( folder=file_folder, filespec=file_extension )
	print( "all files --> " + str(all_files))

	number_list = []
	for ea in all_files:
		#Just to look for the numbers
		try:
			number_list.append(int(re.findall(r'\b\d+\b', ea)[-1]))
		except:
			number_list.append(0)
	number_list.sort()
	return number_list[0]
	

def changeCamera():
	#Camera
	cameras_shape = cmds.ls(type='camera')
	cameras = []
	for ea in cameras_shape:
		cameras.extend(cmds.listRelatives(ea, parent=True))


	#Making camera selection with UI 
	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)
	
	user_width = 200
	user_height = 20

	wesCameraUI = cmds.window('wesCameraChooser', title="Attach ImagePlane to...", sizeable=True, width=user_width, height=50)
	cmds.showWindow(wesCameraUI)
	parentWindow = 'wesCameraChooser'

	cmds.rowColumnLayout(numberOfColumns=1)

	cmds.separator(style="none",height=16)
	

	cmds.optionMenu('cameraChoices', label='Choose:')
	for camera in cameras:
		cmds.menuItem(label=camera)

	#if there is the main camera to use, default to that as a selection
	if [x for x in cameras if default_main_cam in x]:
		cameraIndex = cameras.index([x for x in cameras if default_main_cam in x][0])
	else:
		cameraIndex = 1
	cmds.optionMenu('cameraChoices',edit=True, select=(cameraIndex+1))


	cmds.separator(style="none",height=8)
	
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Cancel", command=lambda x:changeCameraPartTwo(update=False), width=user_width*.5, height=user_height,bgc=[.6,.3,.3])
	cmds.button(l="Choose This!", command=lambda x:changeCameraPartTwo(update=True), width=user_width*.5, height=user_height, bgc=[.3,.6,.3])
	cmds.setParent('..')

def changeCameraPartTwo(update):
	if update == False:
		if cmds.window("wesCameraChooser", exists=True):
			cmds.deleteUI("wesCameraChooser")
			cmds.windowPref("wesCameraChooser", removeAll=True)
		return

	#Find info from camera choise UI
	choiceCam = cmds.optionMenu('cameraChoices', q=True, value=True)

	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)

	theIM = cmds.textScrollList("listImagePlanes", query=True, selectItem=True)

	for IM in theIM:

		#Find the values for these channels so that it won't change the size when you transfer cameras.
		scale_size_x = cmds.getAttr(IM+".sizeX")
		scale_size_y = cmds.getAttr(IM+".sizeY")
		
		cmds.imagePlane(IM, e=True, camera=choiceCam)

		cmds.setAttr(IM+".sizeX", scale_size_x)
		cmds.setAttr(IM+".sizeY", scale_size_y)



def createIM(file_path="", im_name="", frame_offset=0, *args):
	#FilePath

	if not file_path:
		file_path = cmds.fileDialog(mode=0, title="Select ImageSequence")

	print( "THIS IS THE FILE PATH!" + str(file_path))
	if file_path == "":
		return


	start_frame = int(cmds.playbackOptions(q=True, ast=True))
	frame_offset = findLowestNumber(file_path) - start_frame
	


	#Camera
	cameras_shape = cmds.ls(type='camera')
	cameras = []
	for ea in cameras_shape:
		cameras.extend(cmds.listRelatives(ea, parent=True))


	#Making camera selection with UI 
	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)
	
	user_width = 200
	user_height = 20

	wesCameraUI = cmds.window('wesCameraChooser', title="Attach ImagePlane to...", sizeable=True, width=user_width, height=50)
	cmds.showWindow(wesCameraUI)
	parentWindow = 'wesCameraChooser'

	cmds.rowColumnLayout(numberOfColumns=1)

	cmds.separator(style="none",height=16)
	

	cmds.optionMenu('cameraChoices', label='Choose:')
	for camera in cameras:
		cmds.menuItem(label=camera)

	#if there is the main camera to use, default to that as a selection
	if [x for x in cameras if default_main_cam in x]:
		cameraIndex = cameras.index([x for x in cameras if default_main_cam in x][0])
	else:
		cameraIndex = 1
	cmds.optionMenu('cameraChoices',edit=True, select=(cameraIndex+1))


	cmds.separator(style="none",height=8)
	
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Cancel", command=lambda x:createIMPartTwo(update=False), width=user_width*.5, height=user_height,bgc=[.6,.3,.3])
	cmds.button(l="Choose This!", command=lambda x:createIMPartTwo(update=True), width=user_width*.5, height=user_height, bgc=[.3,.6,.3])
	cmds.setParent('..')


	cmds.textField("filePath", text=file_path, visible=False)
	cmds.textField("imName", text=im_name, visible=False)
	cmds.textField("frameOffset", text=frame_offset, visible=False)

	cmds.setParent('..')


def createIMPartTwo(update,*args):
	if update == False:
		if cmds.window("wesCameraChooser", exists=True):
			cmds.deleteUI("wesCameraChooser")
			cmds.windowPref("wesCameraChooser", removeAll=True)
		return

	#Find info from UI box
	file_path = cmds.textField("filePath", q=True, text=True)
	im_name = cmds.textField("imName", q=True, text=True)
	frame_offset = cmds.textField("frameOffset", q=True, text=True)
	choiceCam = cmds.optionMenu('cameraChoices', q=True, value=True)

	if cmds.window("wesCameraChooser", exists=True):
		cmds.deleteUI("wesCameraChooser")
		cmds.windowPref("wesCameraChooser", removeAll=True)

	#Extract the name of the image sequence as possible IM name
	possible_im_name = file_path[file_path.rindex("/")+1:file_path.index(".")]

	#Imageplane Name
	if not im_name:
		result = cmds.promptDialog(
						title='imagePlane Name',
						message='Please name your ImagePlane:',
						text=possible_im_name,
						button=['OK', 'Cancel'],
						defaultButton='OK',
						cancelButton='Cancel',
						dismissString='Cancel')
		if result == 'OK':
						im_name = cmds.promptDialog(query=True, text=True)
						if im_name == '':
							im_name = 'noNameImagePlane'
		else:
				return    
							
	print( im_name)

	im_name = im_name + "_plate"

	createdImagePlane = cmds.imagePlane( camera=choiceCam, fileName=file_path, name=im_name, showInAllViews=False, lookThrough=choiceCam)
	cmds.setAttr(createdImagePlane[0]+".useFrameExtension", 1)
	cmds.setAttr(createdImagePlane[0]+".displayOnlyIfCurrent", 1)
	cmds.setAttr(createdImagePlane[0]+".fit", 2)
	cmds.setAttr(createdImagePlane[0]+".frameOffset", int(frame_offset))

	

	#Extending Frame Cache to be long enough! Add an extra 100 frames for just in case!
	shot_length = cmds.playbackOptions(q=1, aet=1) - cmds.playbackOptions(q=1, ast=1)
	cmds.setAttr(createdImagePlane[0]+".frameCache", int(shot_length)+100)
	#Mainly for .mov files to make sure it keeps the length..
	shot_ending = cmds.playbackOptions(q=1, aet=1)
	cmds.setAttr(createdImagePlane[0]+".frameOut", int(shot_ending)+500)

	#If its a .mov file, set it to type mov!
	if ".MOV" in str(file_path).upper():
		cmds.setAttr(createdImagePlane[0]+".type", 2)

	cmds.rename(createdImagePlane[0], im_name)		
	refreshList()


	#cmds.textScrollList("listImagePlanes", selectItem=im_name)
	cmds.select(im_name) 




def renameIM():
	try:
			IMs = cmds.textScrollList( "listImagePlanes", query=True, selectItem=True)
	except:
			cmds.confirmDialog(message='Please Select an imagePlane from the list')
			return
	for theIM in IMs:
		result = cmds.promptDialog(
						title='imagePlane Name',
						message='Your new ImagePlane name:',
						button=['OK', 'Cancel'],
						defaultButton='OK',
						cancelButton='Cancel',
						dismissString='Cancel',
						text=theIM[:theIM.rindex("_plate")])
		if result == 'OK':
						im_name = cmds.promptDialog(query=True, text=True)
						if im_name == '':
							im_name = 'noNameImagePlane'
		else:
				return               
		print( im_name)

		im_name = im_name + "_plate"

		cmds.rename(theIM, im_name)
		refreshList()

def deleteIM():
	try:
			theIM = cmds.textScrollList( "listImagePlanes", query=True, selectItem=True)
	except:
			cmds.confirmDialog(message='Please Select an imagePlane from the list')
			return
	for IM in theIM:
		cmds.delete(IM)
	refreshList()


def connectUI():
	theIM = cmds.textScrollList("listImagePlanes", query=True, selectItem=True)

	for IM in theIM:
		if cmds.getAttr(IM+".displayMode") == 0:
				cmds.button("IMvisibility", edit=True, label="Visibility Off", bgc=[.4,.3,.3])
		else:
				cmds.button("IMvisibility", edit=True, label="Visibilty On", bgc=[.3,.4,.3])

		cmds.connectControl('offsetX', IM+".offsetX")
		cmds.connectControl('offsetY', IM+".offsetY")
		cmds.connectControl('sizeX', IM+".sizeY", IM+".sizeX")
		cmds.connectControl('depth', IM+".depth")

		updateSliders()
		
		cmds.select(IM)

def updateSliders(depthChanger=False):
	theIM = cmds.textScrollList("listImagePlanes", query=True, selectItem=True)
	attrs = [".depth", ".offsetX", ".offsetY", ".sizeX"]
	for IM in theIM:
		for attr in attrs:
			control_name = attr[1:]
			attr_val = cmds.getAttr(IM+attr)
			if attr == ".depth":
				min_attr = attr_val / 10
				max_attr = (attr_val - min_attr) + attr_val
			elif attr == ".sizeX":
				min_attr = attr_val / 10
				max_attr = attr_val + 1
			else:
				min_attr = attr_val - .1
				max_attr = attr_val + .1

			cmds.floatSlider(control_name, edit=True, min=min_attr, max=max_attr)
			cmds.connectControl(control_name, IM+attr)

		if depthChanger == True:
			depth_val = "Imageplane Depth:  " + str(cmds.getAttr(IM+".depth"))[:5]
			cmds.headsUpMessage(depth_val, time=.5, vo=-250)


def visIM():
	try:
			theIM = cmds.textScrollList( "listImagePlanes", query=True, selectItem=True)
	except:
			cmds.confirmDialog(message='Please Select an imagePlane from the list')
			return
	for IM in theIM:
		#Turn it On
		if cmds.getAttr(IM+".displayMode") == 0:
				cmds.setAttr(IM+".displayMode", 3)

				#Check to see if its a .mov file
				if ".MOV" in str(cmds.getAttr(IM+".imageName")).upper():
					print( "yes")
					cmds.setAttr(IM+".type", 2)
				else:
					cmds.setAttr(IM+".type", 0)

				cmds.button("IMvisibility", edit=True, label="Visibilty On", bgc=[.3,.4,.3])

		#Turn it Off
		else:
				cmds.setAttr(IM+".displayMode", 0)
				cmds.setAttr(IM+".type", 1)

				cmds.button("IMvisibility", edit=True, label="Visibility Off", bgc=[.4,.3,.3])

def refreshCache():
		imageplane_shapes= cmds.ls(type="imagePlane")
		imageplanes =[]
		
		for ea in imageplane_shapes:
			imageplanes.extend(cmds.listRelatives(ea, parent=True))

		if not imageplanes == None:
				for im in imageplanes:
					orig_val = cmds.getAttr(im+".frameCache")
					cmds.setAttr(im+".frameCache", 0)
					cmds.setAttr(im+".frameCache", orig_val)


def loadList():
		imageplane_shapes= cmds.ls(type="imagePlane")
		imageplanes =[]
		
		for ea in imageplane_shapes:
			imageplanes.extend(cmds.listRelatives(ea, parent=True))



		if not imageplanes == None:
				for im in imageplanes:
						#Find only the imageplane name
						# short_im = im[im.rindex("->")+2:]              
						# #Button for imageplane
						# print( "Short Form ImagePlane:  "+ short_im)

						cmds.textScrollList( "listImagePlanes", edit=True, append=im)

def refreshList():
		cmds.textScrollList( "listImagePlanes", edit=True, removeAll=True)
		loadList()


def transparencyUI(*args):
	user_width=350
	user_height=30

	try:
		theIM = cmds.textScrollList( "listImagePlanes", query=True, selectItem=True)
	except:
		cmds.confirmDialog(message='Please Select an imagePlane from the list')
		return

	for IM in theIM:
		transUI = IM+"_transparency"
		if cmds.window(transUI, exists=True):
			cmds.deleteUI(transUI)

		wesAnimToolsUI = cmds.window(transUI, title=transUI, sizeable=True, width=user_width, height=user_height)

		cmds.rowColumnLayout(numberOfColumns=1)
		cmds.floatSlider('transparencySlider', min=0, max=1, width=user_width)
		cmds.connectControl('transparencySlider', IM+".alphaGain")
		cmds.setParent('..')
		cmds.setParent('..')		
		cmds.showWindow(wesAnimToolsUI)

def reset(whatKind,*args):
	try:
		theIM = cmds.textScrollList( "listImagePlanes", query=True, selectItem=True)
	except:
		cmds.confirmDialog(message='Please Select an imagePlane from the list')
		return
	for IM in theIM:	
		if whatKind == "X":
			cmds.setAttr(IM+".offsetX", 0)
		if whatKind == "Y":
			cmds.setAttr(IM+".offsetY", 0)

		if whatKind == "Scale":
			cmds.setAttr(IM+".fit", 2)
			mel_cmd = "AEinvokeFitRezGate "+IM+"Shape.sizeX "+IM+"Shape.sizeY" 
			print( mel_cmd)
			mel.eval(mel_cmd)

	connectUI()


def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=False):
		if cmds.window('wesImagePlanes', exists=True):
			cmds.deleteUI('wesImagePlanes')
		if not parentWindow:
			wesAnimToolsUI = cmds.window('wesImagePlanes', title="ImagePlanes", sizeable=True, width=user_width)
			cmds.showWindow(wesAnimToolsUI)
			parentWindow = 'wesImagePlanes'


		cmds.frameLayout("wesImagePlanesFrames", collapsable=True, label="ImagePlanes", collapse=frameClosed, parent=parentWindow, width=user_width )

		cmds.rowColumnLayout(parent="wesImagePlanesFrames", numberOfColumns=3)
		cmds.button(label='Create', command=lambda x:createIM(), width=user_width*.3333, height=user_height*.85, bgc=[.5,.7,.5])
		cmds.button(label='Rename', command=lambda x:renameIM(), width=user_width*.3333, height=user_height*.85, bgc=[.5,.5,.7])
		cmds.button(label='Delete', command=lambda x:deleteIM(), width=user_width*.3333, height=user_height*.85, bgc=[.7,.5,.5])
		cmds.setParent('..')

		cmds.textScrollList( "listImagePlanes", allowMultiSelection=True, numberOfRows=8,  width=user_width, selectCommand=partial (connectUI) , dkc=partial(deleteIM))
		cmds.popupMenu()
		cmds.menuItem('Refresh', command=lambda x:refreshList())
		cmds.menuItem('Clear Cache to Save RAM', command=lambda x:refreshCache())
		cmds.menuItem('Attach to Another Camera', command=lambda x:changeCamera())
		cmds.setParent('..')
		loadList()

		cmds.rowColumnLayout("editImagePlane", parent="wesImagePlanesFrames", numberOfColumns=1)
		cmds.button('IMvisibility', label='Visibility',width=user_width, command=lambda x: visIM())
		cmds.popupMenu()
		cmds.menuItem('Transparency', command=partial(transparencyUI))
		cmds.text('Offset X')
		cmds.floatSlider('offsetX', min=-.1, max=.1, width=user_width, changeCommand=lambda x:updateSliders())
		cmds.popupMenu()
		cmds.menuItem('reset X', command=partial(reset, "X"))
		cmds.text('Offset Y')
		cmds.floatSlider('offsetY', min=-.1, max=.1, width=user_width, changeCommand=lambda x:updateSliders())
		cmds.popupMenu()
		cmds.menuItem('reset Y', command=partial(reset, "Y"))
		cmds.text('Depth')
		cmds.floatSlider('depth', min=0.1, max=100, width=user_width, changeCommand=lambda x:updateSliders(depthChanger=True))
		cmds.text('Scale')
		cmds.floatSlider('sizeX', min=0, max=3, width=user_width, changeCommand=lambda x:updateSliders())
		cmds.popupMenu()
		cmds.menuItem('reset Scale', command=partial(reset, "Scale"))

		cmds.setParent('..')

		cmds.setParent('..')

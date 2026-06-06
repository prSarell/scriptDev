"""Refactoring zs retime tool to have a UI interface, and added features


	1.5 - Now supports alembic caches
	
	
	1.4 - Added a select connected nodes button
		- fixed the refresh button

	1.3 - Created Export to .chan file using selection of reTime
		- Auto add selected objects upon creation of reTime node
		- Clean up UI to make more sense.


	1.2 - Creating multiple retimes. Whole UI has been readjusted to allow for this.
		- Also added bolding of font when retime is on
		- Added safeGuard on the naming.



THINGS TO FIX:
	- anim layers
	- rig updating can break connections


"""

import maya.cmds as cmds
from functools import partial
import maya.mel as mel


def mayaSafeName(usrName, parent_name):
	"""Using the creating of a node with name to find a maya safe name"""
	usr_sel = cmds.ls(sl=True)
	safe_name = cmds.createNode('transform', name=usrName, parent=parent_name)
	cmds.delete(safe_name)
	cmds.select(usr_sel)
	print( "converted " + usrName + " to " + safe_name)
	return safe_name

def wesCreateTimeNode():

	selection = cmds.ls(sl=True)

	if not cmds.objExists("wes_RetimeNode"):
		cmds.createNode('transform', name="wes_RetimeNode")
		cmds.setAttr("wes_RetimeNode.useOutlinerColor" , True)
		cmds.setAttr ("wes_RetimeNode.outlinerColor" , .2, .34, .19)


	##########Manual input name################ 
	result = cmds.promptDialog(
				title='Retime Name',
				message='Retime Name:',
				button=['OK', 'Cancel'],
				defaultButton='OK',
				cancelButton='Cancel',
				dismissString='Cancel')

	if result == 'OK':
			user_name = cmds.promptDialog(query=True, text=True)
			time_master = mayaSafeName(user_name+"_retime", "wes_RetimeNode")
	else:
		return

	if cmds.objExists(time_master):
		cmds.confirmDialog(message=time_master + " node exists already. Please try again!")
		print( time_master + " node already exists")
		return

	wes_tm = cmds.createNode("transform", name=time_master)
	cmds.parent(wes_tm, "wes_RetimeNode")

	#Turn off attrs

	manips = ['rotate','translate','scale']
	axis = ['X','Y','Z']

	for manip in manips:
		for axi in axis:
			cmds.setAttr(wes_tm+"."+manip+axi, keyable=False)
	cmds.setAttr(wes_tm+".visibility", keyable=False)

	#Create Attrs
	cmds.addAttr(wes_tm, ln="fullTime", at="double")
	cmds.setAttr(wes_tm+".fullTime", edit=True, keyable=True)
	cmds.addAttr(wes_tm, ln="reTime", at="double")
	cmds.setAttr(wes_tm+".reTime", edit=True, keyable=True)
	cmds.addAttr(wes_tm, ln="output", at="double")
	cmds.connectAttr(wes_tm+".fullTime", wes_tm+".output", f=True)


	#Calculate Keyframe based on Scene
	start_fr = cmds.playbackOptions(q=True, animationStartTime=True)
	end_fr = cmds.playbackOptions(q=True, animationEndTime=True)
	mid_fr = end_fr - ((end_fr - start_fr)/2)
	mid_value = ((end_fr - mid_fr)/2) + mid_fr

	#Add KeyFrame
	cmds.setKeyframe(wes_tm+".fullTime", time=start_fr, value=start_fr, itt="spline", ott="spline")
	cmds.setKeyframe(wes_tm+".fullTime", time=end_fr, value=end_fr, itt="spline", ott="spline")
	cmds.setInfinity(wes_tm+".fullTime", pri='linear', poi='linear')
	cmds.setKeyframe(wes_tm+".reTime", time=start_fr, value=start_fr, itt="spline", ott="spline")
	cmds.setKeyframe(wes_tm+".reTime", time=end_fr, value=end_fr, itt="spline", ott="spline")

	#middleKey
	cmds.setKeyframe(wes_tm+".reTime", time=mid_fr, value=mid_value, itt="spline", ott="spline")

	cmds.setInfinity(wes_tm+".reTime", pri='linear', poi='linear')

	#Lock the fullTime
	cmds.selectKey(wes_tm+".fullTime")
	mel.eval("doTemplateChannel graphEditor1FromOutliner 1;")

	#Create Conversion Node
	if not cmds.objExists(time_master+"SlaveConverter"):
		cmds.createNode("unitToTimeConversion",name=time_master+"SlaveConverter")
		cmds.connectAttr(wes_tm+".output", time_master+"SlaveConverter.input", force=True)
		cmds.setAttr(time_master+"SlaveConverter.conversionFactor", 250)

	print( time_master + " created")

	#Make retime HUD
	if not cmds.headsUpDisplay("wesRetimeHUD", exists=True):
		cmds.headsUpDisplay("wesRetimeHUD", section=5, block=5,
		 blockSize="small", command="cmds.getAttr('"+time_master+".output')",
		  decimalPrecision=3, dataFontSize="large",
		  lfs="large",
		  label="FullTime",
		  dataAlignment="right",
		  attachToRefresh=True)

	#Add Retime to list
	cmds.textScrollList( "myRetimeList", edit=True, append=time_master)
	cmds.textScrollList( "myRetimeList", edit=True, selectItem=time_master)
	

	#Switch the retimeMode to Retime On!
	wesRetimeMode(time_master)

	#If there are objects selected, then connect the retime!
	if selection:
		cmds.select(selection)
		wesConnectRetime(time_master, action="add", curve_selected=True)


	cmds.select(time_master)


def wesConnectRetime(time_master, action, curve_selected=False):
	


	time_filter = [time_master+"_fullTime", time_master+"_reTime"]

	if curve_selected == False:
		all_curves = []
		all_curves.extend(cmds.ls(type="animCurveTL"))
		all_curves.extend(cmds.ls(type="animCurveTA"))
		all_curves.extend(cmds.ls(type="animCurveTT"))
		all_curves.extend(cmds.ls(type="animCurveTU"))
		curves_no_retime = [x for x in all_curves if x not in time_filter]
		if action == "add":
			cmds.confirmDialog(message="All Curves Connected! Check script editor for details.")
		if action == "remove":
			cmds.confirmDialog(message="All Curves Disconnected! Check script editor for details.")


	if curve_selected == True:
		sel = cmds.ls(sl=True)

		if not sel:
			cmds.confirmDialog(m="Hey bud, please select objects you want to "+action+" to the retime node! :)")
			return


		#connect Alembics
		for s in sel:
			abc_node = []
			#Check to see if it is a geometry node
			if cmds.listRelatives(s, type="mesh"):
				#Check to see if there is an alembic cache attached to this node
				abc_node = cmds.listConnections(cmds.listRelatives(s, type="mesh"), type="AlembicNode")
			#Connect the retime        
			if abc_node:
				if action == "add":
					cmds.connectAttr(time_master+"SlaveConverter.output", abc_node[0]+".time", f=True)
					print( "connected timeMaster to ::: " + abc_node[0]+".time")

				if action == "remove":
					try:
						cmds.disconnectAttr(time_master+"SlaveConverter.output", abc_node[0]+".time")
					except:
						print( "Nothing to disconnect for : "+ abc_node[0])
					print( "Disconnected ::: " + abc_node[0]+".time ::: from timeMaster")



		sel_curves =  cmds.keyframe(sel, query=True, name=True) or []
		curves_no_retime = [x for x in sel_curves if x not in time_filter]
		
		if action == "add":
			print( "Selected Curves Connected! Check script editor for details.")
		if action == "remove":
			print( "Selected Curves Disconnected! Check script editor for details.")


	for node in curves_no_retime:
		if action == "add":
			### Reason why this part doesn't work is because when keyframe(querying), it doesn't return locked curves ###
			##get curve attribute name
			# node_loc = node.rindex("_")
			# node_attr = node[:node_loc] +"."+ node[node_loc+1:]
			# print( node_attr)
			# #check if curve is locked.
			# if cmds.connectionInfo(node_attr, isLocked=True) == True:
			#     if cmds.confirmDialog(message=node_attr + " is locked. Would you like to unlock and connect?"
			#         , button=["Yes","No"], defaultButton="Yes", cancelButton="No") == "Yes":

			#         cmds.setAttr(node_attr, lock=False)
			#         cmds.connectAttr(time_master+"SlaveConverter.output", node+".input", f=True)
			# else:
			#     cmds.connectAttr(time_master+"SlaveConverter.output", node+".input", f=True)

			cmds.connectAttr(time_master+"SlaveConverter.output", node+".input", f=True)
			print( "connected timeMaster to ::: " + node+".input")

		if action == "remove":
			try:
				cmds.disconnectAttr(time_master+"SlaveConverter.output", node+".input")
			except:
				print( "Nothing to disconnect for : "+node)
			print( "Disconnected ::: " + node+".input ::: from timeMaster")


	#use this later for checking if objects are already driven:
		# s_input = cmds.connectionInfo(node+".input", sourceFromDestination=True)
		# if s_input == "":


def wesDisplayHUD(time_master, update=False):
	if update:
		cmds.headsUpDisplay("wesRetimeHUD", edit=True, command="cmds.getAttr('"+time_master+".output')")
		return

	if cmds.headsUpDisplay("wesRetimeHUD", exists=True):
		cmds.headsUpDisplay("wesRetimeHUD", rem=True)
	else:
		cmds.headsUpDisplay("wesRetimeHUD", section=5, block=5,
		 blockSize="small", command="cmds.getAttr('"+time_master+".output')",
		  decimalPrecision=3, dataFontSize="large",
		  lfs="large",
		  label="Time",
		  dataAlignment="right",
		  attachToRefresh=True)

		#Update the name
		current_mode = cmds.connectionInfo(time_master+".output", sourceFromDestination=True)
		if current_mode == time_master+".fullTime":
			update_mode = "fullTime"
			cmds.headsUpDisplay("wesRetimeHUD",e=True, label=update_mode)
		else:
			update_mode = "reTime"
			cmds.headsUpDisplay("wesRetimeHUD",e=True, label=update_mode)

def wesRetimeMode(time_master):
	
	current_mode = cmds.connectionInfo(time_master+".output", sourceFromDestination=True)
	selected_line = cmds.textScrollList( "myRetimeList", q=True, selectIndexedItem=True)[0]

	if current_mode == time_master+".fullTime":
		update_mode = "reTime"
		#update currentTime to the start of the file
		cmds.currentTime(cmds.playbackOptions(query=True, min=True))
		cmds.textScrollList( "myRetimeList", edit=True, lineFont=[selected_line, "boldLabelFont"])
	else:
		update_mode = "fullTime"
		#Update currentTime to the full time
		cmds.currentTime(cmds.getAttr(time_master+".output"))
		cmds.textScrollList( "myRetimeList", edit=True, lineFont=[selected_line, "plainLabelFont"])

	cmds.connectAttr(time_master+"."+update_mode, time_master+".output", force=True)
	if cmds.headsUpDisplay("wesRetimeHUD", ex=True):
		cmds.headsUpDisplay("wesRetimeHUD",e=True, label=update_mode)


def wesImportRetime(time_master):
	
	file_path = cmds.fileDialog(mode=0, title="Look for retime Curve .txt file")
	if len(file_path) >= 1:

		#remove old retime curve
		cmds.delete(time_master+"_reTime")

		#reTime_Loc = cmds.spaceLocator(p=[0,0,0])
		#cmds.addAttr(reTime_Loc, ln="reTime", at="double")
		#cmds.setAttr(reTime_Loc+".reTime", keyable=True, edit=True)

	with open(file_path, "r") as f:
		for line in f:
			t_curve = line[:line.index(" ")]
			v_curve = line[line.index(" "):]
			if t_curve > 0 and v_curve >0:
				cmds.setKeyframe(time_master+".reTime", t=float(t_curve), v=float(v_curve))




def wesExportRetimeUI():
	ctrl = rtSel()
	start_fr = int(cmds.findKeyframe(ctrl, at="reTime", which="first"))
	end_fr = int(cmds.findKeyframe(ctrl, at="reTime", which="last"))

	file_path = cmds.fileDialog(mode=1, title="Exporting retime for:  "+ctrl)
	
	#If no extension set up from user:
	if "*" in file_path:
		file_path = file_path.replace("*","chan")

	#If user sets up wrong extension:
	if not ".chan" in file_path:
		file_path = file_path[:file_path.rindex(".")]+".chan"

	wesExportRetime(start_fr, end_fr, file_path, ctrl)




def wesExportRetime(start_fr, end_fr, file_path, ctrl):
	#New Way
	line_info = ""

	for f in range(start_fr, end_fr+1):
		value = cmds.getAttr(ctrl+".reTime", time=f)
		if f != end_fr:
			line_info += str(f)  + " " + str(value) + "\n"
		else:
			line_info += str(f)  + " " + str(value)

		with open(file_path, "w") as reTime_file:
			reTime_file.write(line_info)



	#Old way:
	# cmds.confirmDialog(message="Currently using old MPC's tool to release")
	# mel.eval("exportAnimCurveToShakeUI()")





def wesRetimeHelp():
	cmds.confirmDialog(message="RETIME TOOL\n\n"+

						"- Select the objects you want to retime, then click on the 'create retime node'\n"+
						"- Connect either everything in scene by clicking on 'add Scene' or 'add Objects' for selected objects\n"+
						"- Toggle Time, to switch between full time and retime\n"+
						"- You can export your retime for compositors or to transfer your retime to another shot.\n\n\n"+

						"Tips:\n"+
						"- Locked Attributes will not connect (ie. Locked Camera attributes will not connect to retime)\n"+
						"- Imageplanes must be driven by keyframes, not expressions\n"+
						"- Bake your curves before you release!")


def wesSelectConnected(time_master):
	"""this one might be a bit dangerous.. a lot of guess work reliance to select the nodes"""

	#putting the [1:] to remove itself from the list (first one seems to be the connection to the retime node)
	tmp_ls = cmds.listConnections(time_master+"SlaveConverter", d=True)[1:]
	appendedList = []
	for ea in tmp_ls:
		connected = cmds.listConnections(ea, d=True)
		#the [0] is to choose the first one, which is the destination
		appendedList.append(connected[0])

	cmds.select(list(set([ea for ea in appendedList])))


def wesDeleteRetime(time_master):
	
	if cmds.objExists(time_master+"SlaveConverter"):
		cmds.delete(time_master+"SlaveConverter")

	if cmds.objExists(time_master):
		cmds.delete(time_master+"_fullTime")
		cmds.delete(time_master+"_reTime")
		cmds.delete(time_master)

	if cmds.headsUpDisplay("wesRetimeHUD", exists=True):
		cmds.headsUpDisplay("wesRetimeHUD", rem=True)

	cmds.textScrollList( "myRetimeList", edit=True, removeItem=time_master)

	


def rtSel():
	time_master = cmds.textScrollList( "myRetimeList", query=True, selectItem=True)
	print( time_master)
	#Just check if there is a retime existing.
	if time_master == None:
		cmds.confirmDialog(message="There is no retime created! Please make one first ;)")
		return

	time_master = time_master[0]
	return time_master

def selectRetime():
	if not rtSel() == None:
		cmds.select(rtSel())
		wesDisplayHUD(rtSel(), update=True)


def intialLoadList():
	if not cmds.objExists("wes_RetimeNode"):
		cmds.textScrollList( "myRetimeList", edit=True, removeAll=True)
		return

	the_list = cmds.listRelatives("wes_RetimeNode", children=True)
	cmds.textScrollList( "myRetimeList", edit=True, removeAll=True)

	if not the_list == None:
		for each in the_list:
			print( each)
			cmds.textScrollList( "myRetimeList", edit=True, append=each)

			#Now if reTime is on, then bold the font:
			current_mode = cmds.connectionInfo(each+".output", sourceFromDestination=True)
			if current_mode == each+".reTime":
				cmds.textScrollList( "myRetimeList", edit=True, selectItem=each)
				selected_line = cmds.textScrollList( "myRetimeList", q=True, selectIndexedItem=True)[0]
				cmds.textScrollList( "myRetimeList", edit=True, lineFont=[selected_line, "boldLabelFont"])

		cmds.textScrollList( "myRetimeList", edit=True, selectIndexedItem=1)


def UI(parentWindow=None, user_width=150, user_height=22, frameClosed=False):
	if not parentWindow:
		if cmds.window("wesRetimeTool", exists=True):
			cmds.deleteUI("wesRetimeTool")
			#cmds.windowPref("wesRetimeTool", removeAll=True)

		wesRetimeUI = cmds.window('wesRetimeTool', title="wesRetime Tool", sizeable=True, width=user_width, height=100)
		cmds.showWindow(wesRetimeUI)
		parentWindow = 'wesRetimeTool'


	cmds.frameLayout(collapsable=True, label="Retime Anim", collapse=frameClosed, parent=parentWindow, width=user_width)
	cmds.rowColumnLayout()

	cmds.rowColumnLayout(numberOfColumns=2) 
	cmds.button(l="Create Retime Node", command=lambda x:wesCreateTimeNode(), width=user_width*.85, height=user_height, bgc=[.8, .8, .8], annotation="Creates a node to store the retime curve.  No retime will be done at this point")
	cmds.button(l="?", command=lambda x:wesRetimeHelp(), width=user_width*.15, height=user_height, bgc=[.2,.2,.2], annotation="Explanation of some common issues with retiming") 
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=1)   
	cmds.textScrollList( "myRetimeList", allowMultiSelection=False, numberOfRows=8,	
		width=user_width, selectCommand=partial (selectRetime), font="plainLabelFont", annotation="Listed retimes.  If its not showing, please reopen this UI")
	cmds.popupMenu()
	cmds.menuItem('Refresh', command=lambda x:intialLoadList())
	cmds.menuItem('Select All Connected Nodes', command=lambda x:wesSelectConnected(rtSel()))
	cmds.button(l="Toggle Retime", command=lambda x:wesRetimeMode(rtSel()), width=user_width, height=user_height*1.3,  bgc=[.7,1,1], annotation="Toggles selected retime on and off")
	cmds.button(l="HUD Display", command=lambda x:wesDisplayHUD(rtSel()), width=user_width, height=user_height*.85,  bgc=[0,.4,.4], annotation="Shows you what mode you are in and what frame is being used.")
	cmds.setParent('..')

	cmds.separator(height=10, style="single")

	cmds.rowColumnLayout(numberOfColumns=3)
	cmds.text("Add:", width=user_width*.3, height=user_height)
	cmds.button(l="Objects", command=lambda x:wesConnectRetime(rtSel(),"add", curve_selected=True), width=user_width*.4, height=user_height,  bgc=[0,.4,0], annotation="Objects that are selected are connected")
	cmds.button(l="Scene", command=lambda x:wesConnectRetime(rtSel(),"add"), width=user_width*.3, height=user_height,  bgc=[0,.3,0], annotation="Anything in your scene with an animCurve")
	cmds.text("Remove:", width=user_width*.3, height=user_height)
	cmds.button(l="Objects", command=lambda x:wesConnectRetime(rtSel(),"remove", curve_selected=True), width=user_width*.4, height=user_height,  bgc=[.4,0,0])
	cmds.button(l="Scene", command=lambda x:wesConnectRetime(rtSel(),"remove"), width=user_width*.3, height=user_height,  bgc=[.3,0,0])
	cmds.setParent('..')



	cmds.separator(height=10, style="single")
	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.button(l="Delete Selected", command=lambda x:wesDeleteRetime(rtSel()), width=user_width, bgc=[.2, .2, .2], height=user_height*.85, annotation="Remove selected retime") 
	cmds.setParent('..')
	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Import", command=lambda x:wesImportRetime(rtSel()), width=user_width*.5, height=user_height*.8,  bgc=[0,.4,.5], annotation="Look for a retime.chan file or retime.txt")
	cmds.button(l="Export", command=lambda x:wesExportRetimeUI(), width=user_width*.5, height=user_height*.8,  bgc=[0,.5,.4], annotation="Using MPC tool to export curve")
	cmds.setParent('..')


	cmds.setParent('..')

	cmds.setParent('..')

	intialLoadList()
	#cmds.showWindow(wesRetimeUI)




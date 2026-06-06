"""
##########################################################################################################
######								Wesley's Key Editor script										######
######									heywesley@gmail.com											######
######																								######
######																								######
######				Currently, you can flatten or exaggerate your curves							######
######				or cushion/favor to the left or right.  This is first							######
###### 				based on selection in the graph editor.  If nothing is 							######
######				selected, Then it will check if there is channelBox 							######
######				highlighted.  Then if nothing is highlighted, it will edit,						######
######				the current keys.																######
######			

					v1.96 - Adding randomize key function

					v1.95 - added match keys

					v1.94 - moved color ticks to here

					v1.93 - Added Tangent editor

					v1.92 - removed channelBoxselect for now as it doesn't work.

					v1.91  - Added matching left and right to favor by ctrl click

					v1.9  - attempt to fix channelBox vs graphEditor selection issue.

					v1.8  - fix channelBox issue.


######				v1.7  - have a choice to auto tangent or not.									######
######																								######
######																								######
######				v1.6  - When Shifting Keys, it will now stop adjacent keys 						######
######					    from moving over.  In future versions, it will							######
######					    override the key.  Set a warning.										######
######					  - Changed wesScaleKeys() to editKeys()									######
######																								######
######																								######
######				v1.5  - Making shift Keys by apart of the curveModifier() function				######
######					  - Shifting keys follow user selection 									######
######					  - Fixed doubling up on shifting keys										######
######					  - WARNING:  Shifting keys can crash into adjacent keys and sit on 		######
######								  not a whole frame number.										######
######																								######
######																								######
######				v1.4  - Adding channel box select, and refactoring code to run functions		######
######					  - Check channel box highlight first -> then graph editor 					######
######					    selection -> if none on both, then just current frame					######
######																								######
##########################################################################################################
"""
import maya.cmds as cmds
import maya.mel as mel
import random
import imp

#Gather Imports
import wesTools.wesUtils
imp.reload(wesTools.wesUtils)
from .wesUtils import setActiveWindow

from .wesUtils import chosenModifiers


def colorTicks(tick):
	if tick == "on":
		cmds.keyframe(tickDrawSpecial=1)
	if tick == "off":
		cmds.keyframe(tickDrawSpecial=0)
	setActiveWindow()


"""Graph Editor"""

def getKeyValue(curve, index):
	"""After Getting the Key frames, we can extract the index #, time Value, and Key Value"""
	i = index
	k_time = cmds.keyframe(curve, query=True, index=(i, i), timeChange=True)[0]
	k_value = cmds.keyframe(curve, query=True, index=(i, i), valueChange=True)[0]

	return [i, k_time, k_value]

################################################################
########     Functions to return what is selected    ###########
def checkGraphEditorSelection(object_sel):
	sent_list_curves = []

	sel_curves =  cmds.keyframe(object_sel, query=True, name=True, sl=True) or []

	#If there are curves selected
	if not sel_curves == []:
		sent_list_curves.extend(sel_curves)

	
	if sent_list_curves != []:
		return sent_list_curves

debug_chch_mode = False
def checkChannelBoxSelection(object_sel):
	if debug_chch_mode: print( "##############Debug Check Channel Box Selection ########################")

	sent_list_curves = []

	#Grab what is selected by the user in the channelBox
	channel_box_selections = mel.eval('selectedChannelBoxPlugs')
	if debug_chch_mode: print( "channel box selection:  " + str(channel_box_selections))

	#Check to see what curves are available
	sel_curves =  cmds.keyframe(object_sel, query=True, name=True)
	if debug_chch_mode: print( "selected curves:  " + str(sel_curves))

	if len(channel_box_selections) != 0:

		curve_names = []

		for chb in channel_box_selections:
				
			#Split the controller name and attribute name
			buffer = chb.split(".")
			control_name = buffer[0]
			attr_name = buffer[1]
			if debug_chch_mode: print( "buffer for splitting:  " + str(buffer))
			if debug_chch_mode: print( "control_name:  " + str(control_name))
			if debug_chch_mode: print( "attr_name:  " + str(attr_name))



			#Look for the graph editor friendly name: attribute name
			attr_long_name = cmds.attributeQuery(attr_name, node=control_name, ln=True)
			if debug_chch_mode: print( "attr_long_name:  " + str(attr_long_name)			)

			if ":" in control_name:
				#Look for the graph editor friendly name: local object name
				local_name = control_name[control_name.rindex(":")+1:]
			else:
				local_name = control_name

			#Combine to make graph editor friendly name
			curve_name = local_name + "_" + attr_long_name
			if debug_chch_mode: print( "curve_name:  " + str(curve_name))
			curve_names.append(curve_name)



		#If there are multiple rigs with the same attrs, we'll need to find the suffix # to find the proper curve
		possible_curves = set(curve_names, )
		if debug_chch_mode: print( "posssible curves:  " + str(possible_curves))
		

		real_curve = possible_curves[0]

		# --------------> This part doesn't work because the possible_curves name doesn't match the curve_name because curve_name doesn't have the nameSpace
		#Now we are just going to narrow down our selection to the same name + 1 character, or the same amount of characters
		#real_curve =  [x for x in possible_curves if len(x) == len(curve_name) or len(x) == (len(curve_name)+1)]
		#real_curve = real_curve[0] 

		if debug_chch_mode: print( "real_curve:  " + str(real_curve))

		sent_list_curves.append(real_curve)
	if debug_chch_mode: print( "#############################################################")
	if sent_list_curves != []:
		return sent_list_curves
		

def createCurrentFrameSelection(object_sel):
	sent_list_curves = []

	#If there is nothing selected in the graph editor.  Drop a key on the selected controls and select those keys.
	current_time = cmds.currentTime(q=True)
	curves_with_keys = cmds.keyframe(object_sel, query=True, name=True)


	#Check if there are any keyable keyframes on selected
	if not curves_with_keys == None:

		#Set a key for each one
		for each in curves_with_keys:
			cmds.setKeyframe(each) 

		sent_list_curves.extend(curves_with_keys)

	if sent_list_curves != []:
		return sent_list_curves

################################################################
debug_edit_mod = False
def editKeys(power,operation):
	"""This function is used to find out what the user has selected.  checks in this order:

	1) Checks if user has selected in graph editor, turn on attribute
	2) Checks if channelBox is highlighted
	3) Then check if graph editor is highlighted
	4) If none of them are highlighted, then it selects current frame."""

	#Multiple Objects Selected
	selected = cmds.ls(sl=True) or []

	full_list_curves = []
	
	#Start with selection is false, so that when you run through each selected and find there selection, then it will turn true
	graph_editor_selection = False
	no_key_selected = False


	#Check each object and add to the full_list_curves
	for sel in selected:


		"""This part is super fugly.  One day this needs to be re-factored to be cleaner"""

		if checkGraphEditorSelection(sel):
			graph_editor_selection = True

		if debug_edit_mod: print( "graph editor selection =  " + str(checkGraphEditorSelection(sel)))
		
		#Adding a checker to see if graph editor is selected
		if not checkGraphEditorSelection(sel):
			print( "Nothing is selected in graph editor cause :: " + str(checkGraphEditorSelection(sel)))
			#Check channel box highlight first -> then graph editor selection -> if none on both, then just current frame
			
			#Taking out channelBox until I can work it <-----------------------------------------------------------------
			#add_this = checkChannelBoxSelection(sel) or checkGraphEditorSelection(sel) or createCurrentFrameSelection(sel)
			add_this = checkGraphEditorSelection(sel) or createCurrentFrameSelection(sel)
		else:
			print( "graph editor does have selection")
			add_this = checkGraphEditorSelection(sel)
		
		

		if add_this:
			full_list_curves.extend(add_this)
		else:
			print( "This item don't work yo!   :  " + str(sel))
		


	print( full_list_curves)
	#We have to make sure something is selected!


	#So if there is no graph editor selection, it will select the keys and also make sure its in tangent mode.
	if not graph_editor_selection:
			current_time = cmds.currentTime(q=True)
			cmds.selectKey(full_list_curves, time=(current_time, current_time))
	

	#Taking out channelBox until I can work it <-----------------------------------------------------------------
	# if checkChannelBoxSelection(sel) and not graph_editor_selection:
	# 	current_time = cmds.currentTime(q=True)
	# 	cmds.setKeyframe(checkChannelBoxSelection(sel))
	# 	cmds.selectKey(checkChannelBoxSelection(sel), time=(current_time, current_time))

	#Remove any duplicates selected!!!
	full_list_curves = set(full_list_curves)
	full_list_curves = list(full_list_curves)

	###########################################################################################
	###########################################################################################
	#Do the actual curve adjustments!	
	curveModifier(power, operation, full_list_curves)##########################################
	#Check if auto-tangent is checked on or not.###############################################
	if cmds.checkBox("autotangent", q=True, value=True):
		#Don't wanna mess with and conflict with the steepen tangent tool.
		if operation != "steepenTangent":
			cmds.keyTangent(itt="auto", ott="auto")
	###########################################################################################
	###########################################################################################


	#Check if the user had originally selected something, if not clear the selection
	if not graph_editor_selection:
		cmds.selectKey(clear=True)

	#Adjust currentTime to reflect adjustment if its shifting keys.
	if graph_editor_selection == False and operation == "shiftKeys":
		cmds.currentTime( (cmds.currentTime(q=True) + power) )
					
				


debug_curve_mod = False
def curveModifier(power, operation, sent_list_curves):
	if debug_curve_mod: print( "================= Curve Modifier Function ================")
	"""This function will apply the value updates to the list of curves selected"""


	#Check if sent_list_curves is a list or not. Then turn it into a list if its not.
	if not type(sent_list_curves) is list or type(sent_list_curves) is tuple:
		sent_list_curves = [sent_list_curves]

	if debug_curve_mod: print( "Curve list argument:  " + str(sent_list_curves))



	for curve in sent_list_curves:
		if debug_curve_mod: print( "Current Curve To Edit:  " + str(curve))
		#This part is the setup:

		#Refresh List
		keys = []
		new_value = 0
		target_value = 0
		sel_keyf_indx = []
		keyf_indx = []


		#Find Key index for each curve
		sel_keyf_indx = cmds.keyframe(curve, query=True, sl=True, indexValue=True)
		if debug_curve_mod: print( "selected keyframe index:  " + str(sel_keyf_indx))


		keyf_indx = cmds.keyframe(curve, query=True, indexValue=True)
		if debug_curve_mod: print( "keyframe index:  " + str(keyf_indx))

		#If there isn't anything selected, then skip and continue the 'for' loop.
		if not sel_keyf_indx == None:
			for each_index in sel_keyf_indx:
				#Retrieve (Index, key Time, key Value) and store as nested list in keys
				keys.append(getKeyValue(curve, each_index))

			#State the anchor points.  Using Index #.
			before_check = (sel_keyf_indx[0] - 1)
			after_check = (sel_keyf_indx[-1] + 1)
			
			#Finding the first and last values of the keys in the selected curves! (Its for setting up match offsets)
			first_key = getKeyValue(curve, sel_keyf_indx[0])
			last_key = getKeyValue(curve, sel_keyf_indx[-1])

			#check if theres a key before the selected key.
			if before_check in keyf_indx:
				before = getKeyValue(curve, before_check)
				if debug_curve_mod: print( "before Value:   "+ str(before) + "  is Previous Keyframe")
			else:
				before = keys[0]
				if debug_curve_mod: print( "before Value:   "+ str(before) + "  is Same Keyframe")

			#check if theres a key after the selected key

			if after_check in keyf_indx:
				after = getKeyValue(curve, after_check)
				if debug_curve_mod: print( "after Value:   "+ str(after) + "  is Next Keyframe")
			else:
				after = keys[-1]
				if debug_curve_mod: print( "after Value:   "+ str(after) + "  is Same Keyframe")



			##################################
			#This part is the adjustment:
			##################################

			#The nested list in Keys are as follows, 0 = index, 1 = Time, 2 = Value
			#Position = the key that is being edited

			if debug_curve_mod: print( "This is the keys:  " + str(keys))
			for position in range(len(keys)):


				#ValueScale to create Target Value
				old_value = keys[position][2]

				#######Create a check to see if we want to Shift Keys By########:
				if operation == "shiftKeys":
					if debug_curve_mod: print( "-------------------shiftKeys---------------------")

					#Time Value of Previous and After KeyFrames
					prev_ind = keys[position][0] -1
					aft_ind = keys[position][0] +1


					#Check if there is keys before or after the Queried one.
					if prev_ind in keyf_indx:
						prev_key = getKeyValue(curve, prev_ind)
					else:
						prev_key = getKeyValue(curve, keys[position][0])

					if aft_ind in keyf_indx:
						aft_key = getKeyValue(curve, aft_ind)
					else:
						aft_key = getKeyValue(curve, keys[position][0])


					if debug_curve_mod: print( "Previous TimeValue:  " + str(prev_key[1]) + "   " + str((keys[position][1])))
					if debug_curve_mod: print( "After TimeValue:  " + str(aft_key[1]) + "   " + str((keys[position][1])))

					#Check to see if the keyframe will override the one where its going.
					if prev_key[1] == (keys[position][1] + power):
						print( "I dont move this key:  " + str(curve))
						cmds.headsUpMessage("There is a Key that couldn't shift to the left", time=3)


						#cmds.cutKey(curve, index=(prev_ind, prev_ind) ,clear=True)
						#Because you are deleting a key before, the index gets changed. Have to reduce by 1 to keep the index correct.
						#keys[position][0] = (keys[position][0] - 1)

					elif aft_key[1] == (keys[position][1] + power):
						print( "I dont move this key:  " + str(curve))
						cmds.headsUpMessage("There is a Key that couldn't shift to the right", time=3)
						#cmds.cutKey(curve, index=(aft_ind, aft_ind) ,clear=True)

					else:
						cmds.keyframe(curve, index=(keys[position][0], keys[position][0]), edit=True, timeChange=power,relative=True)
						if debug_curve_mod: print( "current Keys Value:  " + str(keys[position]))


				######## Increase/Decrease Tangents ######
				#   Checking the out angle 
				elif operation == "steepenTangent":
					if debug_curve_mod: print( "=========STEEPEN TANGENTS!============")
					

					tang_angle = cmds.keyTangent(curve, q=True,index=(keys[position][0],), oa=True)[0]
					if tang_angle < 0:
						add_val = -power
					elif tang_angle > 0:
						add_val = power
					elif tang_angle == 0:
						add_val = 0

					new_angle = float(tang_angle) + float(add_val)
					key_time = cmds.keyframe(curve, q=True,index=(keys[position][0],), tc=True)[0]

					if debug_curve_mod: print( "tang_angle:  " + str(tang_angle))
					if debug_curve_mod: print( "keys position index:  " + str(keys[position][0]))
					if debug_curve_mod: print( "add_val:  " + str(add_val))
					if debug_curve_mod: print( "new_angle:  " + str(new_angle))
					if debug_curve_mod: print( "key_time:  " + str(key_time))


					cmds.keyTangent(curve,time=(key_time,), oa=new_angle)
					

				else:

					#######Create a check to see if we want to flatten and exagerate########:
					if operation == "flatxagerate":

						#TimeScale to scale Target
						ratio_time = (keys[position][1] - before[1]) / (after[1] - before[1])
						#print( "Ratio Time:    " + str(ratio_time)			)
							
						#The value distance between the anchor points
						total_anch_dist = abs(before[2] - after[2])
						#print( "Total Anchor Value change:   "+ str(total_anch_dist))


						#Find the target value for flattening and scaling Keys.
						#If first is less than last:
						if before[2] < after[2]:
							target_value =  before[2] + (total_anch_dist*ratio_time)
						else:
							target_value =  before[2] - (total_anch_dist*ratio_time)


						#To flatten
						if power < 1:

							#If current value is above the target value, go downwards
							if old_value > target_value:
								new_value = old_value - (abs(old_value - target_value) * power)

							#Will also include old_value = target_value
							else:
								new_value = old_value + (abs(old_value - target_value) * power)

						#To scale
						if power > 1:
							if old_value > target_value:
								new_value = target_value + (abs(old_value - target_value) * power)
							if old_value < target_value:
								new_value = target_value - (abs(old_value - target_value) * power)
							if old_value == target_value:
								new_value = old_value

						if power == 1:
							new_value = old_value


					#######Create a check to see if we want to cushion########:
					if operation == "cushionLeft":
						#Find the target value for cushioning to before.
						#If before archor point value is less than after anchor point:
						if before[2] < old_value:

							#Take the old value and subtract half of the value change between the before anchor point and the old value
							#Need to get abs() for the absolute value, removing negatives.
							difference = abs(( old_value - before[2] ) / 2)
							new_value =  old_value - difference * power
						else:
							difference = abs((before[2] - old_value) / 2)
							new_value =  old_value + difference * power

					if operation == "cushionRight":
						#Find the target value for cushioning to before.
						#If before archor point value is less than after anchor point:
						if old_value < after[2]:

							#Take the old value, and add half of the difference between the old and the after value.
							#Need to get abs() for the absolute value, removing negatives.
							difference = abs((after[2] - old_value) / 2)
							#using power, we can reduce or increase the amount of distance
							new_value = old_value + difference * power
						else:
							difference = abs((old_value - after[2]) / 2)
							#using power, we can reduce or increase the amount of distance
							new_value = old_value - difference * power

					#The nested list in Keys are as follows, 0 = index, 1 = Time, 2 = Value
					#Position = the key that is being edited

					########Check to see if we want to Match Left or Right ####:
					if operation == "matchLeft":
						new_value = before[2]
					if operation == "matchRight":
						new_value = after[2]


					#Last and First key is the values of the selected last and first keys.
					# Before and After are the anchor point values.
					if operation == "matchOffsetLeft":
						difference = before[2] - first_key[2]
						new_value = old_value + difference

					if operation == "matchOffsetRight":
						difference = after[2] - last_key[2]
						new_value = old_value + difference

					########Scale value power relative to Zero point #####
					if operation == "relativeZero":
						new_value = old_value * power

					#### Randomizing the selected keys between first and last value####
					if operation == "randomize":
						difference = abs(( first_key[2] - last_key[2] ) / 2)
						new_value = random.uniform((old_value + difference), (old_value - difference))

					#Run final command to update value
					cmds.keyframe(curve, index=(keys[position][0], keys[position][0]), valueChange=new_value, absolute=True)

	if debug_curve_mod: print( "==========================================================")
	



def scaleKeysby(type):
	"""Only for the UI interface use"""

	if type == "flatten":
		percent_by = float(cmds.intField('percentageScale', q=True, value=True ))
		percent = percent_by / 100
		
		if chosenModifiers(kind="Ctrl"):
			editKeys(percent, "relativeZero")
		else:
			editKeys(percent, "flatxagerate")

	if type == "exaggerate":
		percent_by = float(cmds.intField('percentageScale', q=True, value=True ))
		percent = (percent_by / 100) + 1
		
		if chosenModifiers(kind="Ctrl"):
			editKeys(percent, "relativeZero")
		else:
			editKeys(percent, "flatxagerate")

	if type == "cushionLeft":
		percent_by = float(cmds.intField('percentageScale', q=True, value=True ))
		percent = (percent_by / 100)
		if chosenModifiers(kind="Ctrl"):
			editKeys(1, "matchLeft")
		else:
			editKeys(percent, "cushionLeft")


	if type == "cushionRight":
		percent_by = float(cmds.intField('percentageScale', q=True, value=True ))
		percent = (percent_by / 100)
		if chosenModifiers(kind="Ctrl"):
			editKeys(1, "matchRight")
		else:
			editKeys(percent, "cushionRight")
	setActiveWindow()


def shiftKeysBy():
	shift_by = cmds.intField('entered_shift_value', query=True, value=True)
	editKeys(shift_by, "shiftKeys")
	setActiveWindow()

def curveSelected():
	sel = cmds.ls(sl=True)

	if not cmds.keyframe(q=True, selected=True) == None:
		sel_curves = cmds.keyframe(q=True, n=True)
		curve_prompt = ""
		for ea in sel_curves:
			curve_prompt += ea+"\n"
		cmds.confirmDialog(message="Selected Curves:\n\n"+curve_prompt)
	else:
		cmds.confirmDialog(message="No Curves Selected in Graph Editor")
	setActiveWindow()

def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=False):
	if not parentWindow:
		if cmds.window("wesKeyEditorCustomUI", exists=True, resizeToFitChildren=True):
			cmds.deleteUI("wesKeyEditorCustomUI")
	
		wesAnimToolsUI = cmds.window('wesKeyEditorCustomUI', title="wesKeyEditor", sizeable=True, width=user_width)
		cmds.showWindow(wesAnimToolsUI)
		parentWindow = 'wesKeyEditorCustomUI'


	cmds.frameLayout(collapsable=True, label="Graph Editor", collapse=frameClosed, parent=parentWindow, width=user_width)

	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.text("Flatten / Exaggerate", font="fixedWidthFont")
	cmds.setParent('..')


	cmds.rowColumnLayout(numberOfColumns=4)
	cmds.button(l="-", command=lambda x:scaleKeysby("flatten"), width=user_width*.4,height=user_height, bgc=[.701,.286,.521], annotation="Flatten Your Curves!")
	cmds.button(l="+", command=lambda x:scaleKeysby("exaggerate") , width=user_width*.4,height=user_height,bgc=[.286,.701,.467], annotation="Exaggerate Your Curves!")
	cmds.intField('percentageScale', minValue=0, maxValue=100, width=user_width*.15 ,height=user_height, value=20, annotation="The Percentage of which the curve will be affected")
	cmds.text("%", width=user_width*.05, height=user_height, annotation="The Percentage of which the curve will be affected")
	cmds.setParent('..')


	cmds.rowColumnLayout(numberOfColumns=3)
	cmds.button(l="<<", command=lambda x:scaleKeysby("cushionLeft"), width=user_width*.4, height=user_height, bgc=[.651,.286,.749], annotation="Favor to the Left!")
	cmds.button(l=">>", command=lambda x:scaleKeysby("cushionRight") , width=user_width*.4, height=user_height,bgc=[.286,.615,.615], annotation="Favor to the Right!")
	cmds.text("Favor",  width=user_width*.2, height=user_height, font="plainLabelFont" )
	cmds.button(l="<<", command=lambda x:editKeys(1, "matchLeft"), width=user_width*.4, height=user_height, bgc=[.481,.286,.569], annotation="Match keys to the Left!")
	cmds.button(l=">>", command=lambda x:editKeys(1, "matchRight") , width=user_width*.4, height=user_height,bgc=[.106,.615,.435], annotation="Match keys to the Right!")
	cmds.text("Match",  width=user_width*.2, height=user_height, font="plainLabelFont" )
	cmds.setParent('..')

	cmds.separator(style="in", height=1)

	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.text("Shift Keys By...", font="fixedWidthFont")
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=6)
	cmds.button(l="<<", command=lambda x:editKeys(-2, "shiftKeys"), width=user_width*.170, height=user_height, bgc=[1, .4, .2])
	cmds.button(l="<", command=lambda x:editKeys(-1, "shiftKeys"), width=user_width*.214, height=user_height, bgc=[1, .7, .23])
	cmds.button(l=">", command=lambda x:editKeys(1, "shiftKeys"), width=user_width*.214, height=user_height, bgc=[.7, .9, .4])
	cmds.button(l=">>", command=lambda x:editKeys(2, "shiftKeys"), width=user_width*.170, height=user_height, bgc=[.5, .95, 0])
	cmds.button(l="#", command=lambda x:shiftKeysBy(), width=user_width*.107, height=user_height, bgc=[.95, .85, .58], annotation="by # value you input")
	cmds.intField('entered_shift_value', value=10 , width=user_width*.125, height=user_height )
	cmds.setParent('..')

	cmds.separator(style="in", height=1)

	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.button(l="Green Ticks", command=lambda x:colorTicks("on"), width=user_width*.5, height=user_height, bgc=[0,.4,0], annotation="Adds special tick color in timeline to selected keys.")
	cmds.button(l="Red Ticks", command=lambda x:colorTicks("off"), width=user_width*.5, height=user_height,bgc=[.4,0,0], annotation="Removes special tick color in timeline to selected keys.")
	cmds.setParent('..')
	
	cmds.rowColumnLayout(numberOfColumns=2)
	cmds.text("Set:  ",)
	cmds.checkBox("autotangent", label="auto-tangent",editable=True, value=True, annotation="If you want the tangents to be smoothed out after the keys have moved, check this on.")
	cmds.setParent('..')

	cmds.rowColumnLayout(numberOfColumns=1)
	cmds.button(l="What Curve Selected?", command=lambda x:curveSelected(), width=user_width, bgc=[.7, .7, .7])
	cmds.setParent('..')


	cmds.setParent('..')
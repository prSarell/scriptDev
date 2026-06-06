"""
#####################################################################################
#######                        Wes Scene Setup                                #######
#####################################################################################

    v2.1 - update Fun script with better text

    v2.0 - Adding a bunch of Create | Transfer | Bake stuff!

    v1.8 - Add locked constraints for orient. To still constrain even if channels are locked.

    v1.7a - Make gravity ball based on selection.

    v1.7 - custom gravity ball settings

    v1.6 - fast/slow switching is based on reference files.  Set up to be editable by animator.

    v1.5 - Changing snap to to be able to do multiple objects.

    v1.4 - snapTo is updated - trying to skip certain attributes
         - Added right-click rotate and translate

    v1.3 - fix snapTo when keyed. so that it will drop a key on each attribute.

    v1.2 - change gravityBall button

    v1.1 - change gravity ball to a calculated script.

    v1.0 - First basic tools for scene Setup

    Any questions please contact me at heywesley@gmail.com

"""
import maya.cmds as cmds
import maya.mel as mel
import imp
import json

#Gather Imports
import wesTools.wesUtils
imp.reload(wesTools.wesUtils)
from .wesUtils import setActiveWindow
from .wesUtils import chosenModifiers

from .wesGravity import gravCalculator
from .wesGravity import ballLauncher
from .wesGravity import wesGravityUI
from .wesGravity import wesGravityUIRun



####FOR THE FUN EYES!!!!#####
def mayaSafeName(usrName):
    """Using the creating of a node with name to find a maya safe name"""
    usr_sel = cmds.ls(sl=True)
    safe_name = cmds.createNode('transform', name=usrName)
    cmds.delete(safe_name)
    
    #To avoid using : and |
    safe_name = safe_name.replace(":","_")
    safe_name = safe_name.replace("|","")
    cmds.select(usr_sel)
    print( "converted " + usrName + " to " + safe_name)
    return safe_name
def shaderAdd(objectName,rcolor,gcolor,bcolor):
    # Gears Material
    if not cmds.objExists("%s_shader" % objectName):
        shadingNodeee = cmds.shadingNode("blinn", asShader=True, name ="%s_shader" % objectName)
        cmds.setAttr("%s_shader.color" % objectName, rcolor, gcolor, bcolor)

    else:
        shadingNodeee = ("%s_shader" % objectName)
        print( "shading node name : " + shadingNodeee )
        
    # Assing Material   
    # Create Sureface Shader
    if not cmds.objExists(objectName+"Shader"):
        cmds.sets( renderable=True, noSurfaceShader=True, empty=True, name=objectName+"Shader" )
        # Connect material to shader
        cmds.connectAttr("%s.outColor" % shadingNodeee, objectName+"Shader.surfaceShader")


    # Assign shader to objects
    cmds.sets(objectName, edit=True, forceElement=objectName+"Shader")
def runFun():
    sel = cmds.ls(sl=True)

    if sel == []:
        cmds.confirmDialog(message="                      Welcome to the googly eye mode!         \n\n\n Please select a control you want to attach these beautiful eyes! ;)")
        return

    if len(sel) > 2:
        cmds.confirmDialog(message="  Welcome to the googly eye mode!   \n\n\n   Please select just one control!\nOr Camera first and then the control... ;)")
        return        

    if len(sel) == 1:
        constrainTo = sel[0]
    
    else:
        constrainTo = sel[1]
        camAim = sel[0]
        print( camAim)

    l_eye = "leftEye_"+mayaSafeName(constrainTo)
    r_eye = "rightEye_"+mayaSafeName(constrainTo)

    l_pupil = "leftPupil_"+mayaSafeName(constrainTo)
    r_pupil = "rightPupil_"+mayaSafeName(constrainTo)

    goog_eyes = "googlyEyes_"+mayaSafeName(constrainTo)

    cmds.polySphere(name=l_eye)
    cmds.move(1.5,0,3, l_eye)
    cmds.polySphere(name=r_eye)
    cmds.move(-1.5,0,3, r_eye)


    cmds.polySphere(name=l_pupil)
    cmds.move(1.8,0.15,3.65, l_pupil)
    cmds.scale(.4,.4,.4, l_pupil)
    cmds.parent(l_pupil,l_eye)
    cmds.polySphere(name=r_pupil)
    cmds.move(-1.8,0.15,3.65, r_pupil)
    cmds.scale(.4,.4,.4, r_pupil)
    cmds.parent(r_pupil,r_eye)

    cmds.spaceLocator(name=goog_eyes)
    cmds.group(name="GooglyEyes_"+mayaSafeName(constrainTo))

    cmds.parent(r_eye, goog_eyes)
    cmds.parent(l_eye, goog_eyes)

    cmds.parentConstraint(constrainTo, "GooglyEyes_"+mayaSafeName(constrainTo), mo=False)

    shaderAdd(r_eye,1,1,1)
    shaderAdd(l_eye,1,1,1)

    shaderAdd(r_pupil,0,0,0)
    shaderAdd(l_pupil,0,0,0)
    if len(sel) > 1:
        cmds.aimConstraint(camAim,r_eye, aim=[0,0,1])
        cmds.aimConstraint(camAim,l_eye, aim=[0,0,1])

    #for ILM axis and ILM character position
    cmds.scale(0.075,0.075,0.075,goog_eyes)
    cmds.rotate(0,90,0, goog_eyes)
    
    cmds.setAttr(goog_eyes+".translateX", 0.14)
    cmds.setAttr(goog_eyes+".translateY", 0.31)



    cmds.select(goog_eyes)
####END OF THE FUN EYES!!!!#####



"Setup"
def wesCreateLayer():
    selected = cmds.ls(sl=True)

    layer_lock = False
    layer_visible = True

    #Shift key is on
    if chosenModifiers(kind="Shift") == True:
        layer_lock = True

    #Ctrl Key is On
    if chosenModifiers(kind="Ctrl") == True:
        layer_visible = False


    result = cmds.promptDialog(
                title='Layer Name',
                message='Layer Name without _lyr:',
                button=['OK', 'Cancel'],
                defaultButton='OK',
                cancelButton='Cancel',
                dismissString='Cancel')

    if result == 'OK':
            input_name = cmds.promptDialog(query=True, text=True)
    else:
        input_name = selected[-1]

    layer_name = input_name + "_lyr"

    if layer_lock == True:
        disTyp = 2
    else:
        disTyp = 0

    the_layer = cmds.createDisplayLayer(selected, name=layer_name, noRecurse=True)
    cmds.setAttr(the_layer+".visibility", layer_visible)
    cmds.setAttr(the_layer+".displayType", disTyp)

def wesSimpleConstraint(cons_type):

    maintainOffsetChoice = True
    retain_selection = False
    #Shift key is on
    if chosenModifiers(kind="Shift") == True:
        retain_selection = True

    #Ctrl Key is On
    if chosenModifiers(kind="Ctrl") == True:
        maintainOffsetChoice = False

    objects_sel = cmds.ls(sl=True)
    master = objects_sel[-1:]
    slave = objects_sel[:-1]
    print( "This is the driver:  " + str(master))
    print( "This is the driven:  " + str(slave))


    if cons_type == "point":
        for ea in slave:
            skipAxis = []
            if cmds.getAttr(ea+".translateX", lock=True):
                skipAxis.append("x")
            if cmds.getAttr(ea+".translateY", lock=True):
                skipAxis.append("y")
            if cmds.getAttr(ea+".translateZ", lock=True):
                skipAxis.append("z")
            if skipAxis:
                print( ea + " has " + str(skipAxis) + " LOCKED!")
            cmds.pointConstraint(master, ea, maintainOffset=maintainOffsetChoice, skip=skipAxis)

    if cons_type == "orient":
        for ea in slave:
            skipAxis = []
            if cmds.getAttr(ea+".rotateX", lock=True):
                skipAxis.append("x")
            if cmds.getAttr(ea+".rotateY", lock=True):
                skipAxis.append("y")
            if cmds.getAttr(ea+".rotateZ", lock=True):
                skipAxis.append("z")
            if skipAxis:
                print( ea + " has " + str(skipAxis) + " LOCKED!")

            cmds.orientConstraint(master, ea, maintainOffset=maintainOffsetChoice, skip=skipAxis)

    if cons_type == "parent":
        for ea in slave:
            cmds.parentConstraint(master, ea, maintainOffset=maintainOffsetChoice)

    if retain_selection == False:
        cmds.select(slave)


def fixPerspCamera():
    camera_name = mel.eval('findStartUpCamera( "persp" );')
    camera_new = cmds.camera(name='persp', hc="viewSet -p %camera")

    cmds.camera(camera_name, edit=True, startupCamera=False)
    cmds.delete("persp")
    cmds.setAttr(camera_new[0]+".visibility", 0)
    cmds.rename(camera_new[0], "persp")
    cmds.camera("persp", edit=True, startupCamera=True)

"Misc"

def toggleImageplane():
    #Find all viewports
    panels = cmds.getPanel(type='modelPanel')

    imageplanes = cmds.ls(type="cachedImagePlane")
    imageplanes.extend(cmds.ls(type="imagePlane"))



    if cmds.modelEditor(panels[0], q=True, imagePlane=True):
        for ea in panels:
            cmds.modelEditor(ea, e=True, imagePlane=0)
            cmds.modelEditor(ea, e=True, displayTextures=0)
        for im in imageplanes:
            cmds.setAttr(im+".type", 1)

        if chosenModifiers(kind="Ctrl"):
            if cmds.objExists("env_lyr"):
                cmds.setAttr("env_lyr.visibility", 1)
            if cmds.objExists("anim_lyr"):
                cmds.setAttr("anim_lyr.visibility", 1)
            if cmds.objExists("daily_lyr"):
                cmds.setAttr("daily_lyr.visibility", 0)

    else:
        for ea in panels:
            cmds.modelEditor(ea, e=True, imagePlane=1)
            cmds.modelEditor(ea, e=True, displayTextures=1)
        for im in imageplanes:
            if ".MOV" in str(cmds.getAttr(im+".imageName")).upper():
                cmds.setAttr(im+".type",2)
            else:
                cmds.setAttr(im+".type", 0)

        if chosenModifiers(kind="Ctrl"):
            if cmds.objExists("env_lyr"):
                cmds.setAttr("env_lyr.visibility", 0)
            if cmds.objExists("anim_lyr"):
                cmds.setAttr("anim_lyr.visibility", 0)
            if cmds.objExists("daily_lyr"):
                cmds.setAttr("daily_lyr.visibility", 1)



    setActiveWindow()

def fastSlowUpdater(user_width=240, user_height=18):
    #{"slow": 2, "controller": "global_CTRL", "medium": 1, "attribute_name": "modelDisplayLevel", "fast": 0}
    
    #Find the file path
    script_path = __file__
    script_path = script_path.replace("\\","/")
    script_path = script_path[:script_path.rindex("/")+1]
    script_path += 'wesSceneSetup_CHARACTER.json'

    #Read from Char File
    with open(script_path) as info_file:
        char_info = json.load(info_file)


    if cmds.window("fastSlowUpdater", exists=True):
        cmds.deleteUI("fastSlowUpdater")
        cmds.windowPref("fastSlowUpdater", removeAll=True)

    wesFastSlowUpdater = cmds.window('fastSlowUpdater', title="Update the Character Values", sizeable=True, width=user_width, height=100)
    cmds.showWindow(wesFastSlowUpdater)
    parentWindow = 'fastSlowUpdater'

    cmds.frameLayout('fastSlow Updater', lv=False, bv=False, mw=7, mh=7)



    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.text('Controller Name:', width=user_width*.5)
    cmds.textField("controllerTextField", ed=True, width=user_width*.5, height=user_height*1, text=char_info["controller"]) 
    cmds.text('Attribute Name:', width=user_width*.5)
    cmds.textField("attributeTextField", ed=True, width=user_width*.5, height=user_height*1, text=char_info["attribute_name"]) 
    cmds.text('Fast Mode:', width=user_width*.5)
    cmds.textField("fastTextField", ed=True, width=user_width*.5, height=user_height*1, text=char_info["fast"])     
    cmds.text('Medium Mode:', width=user_width*.5)
    cmds.textField("mediumTextField", ed=True, width=user_width*.5, height=user_height*1, text=char_info["medium"])     
    cmds.text('Slow Mode:', width=user_width*.5)
    cmds.textField("slowTextField", ed=True, width=user_width*.5, height=user_height*1, text=char_info["slow"])     
    cmds.setParent('..')

    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.button(l="Save Settings", command=lambda x:fastSlowWriter(script_path, update=True), width=user_width*.5, height=user_height, bgc=[.3,.6,.3])
    cmds.button(l="Cancel", command=lambda x:fastSlowWriter(script_path, update=False), width=user_width*.5, height=user_height,bgc=[.6,.3,.3])
    cmds.setParent('..')


    cmds.setParent('..')


    cmds.setParent('..')


def fastSlowWriter(script_path, update):
    if update == False:
        cmds.deleteUI("fastSlowUpdater")
        cmds.windowPref("fastSlowUpdater", removeAll=True)
        return

    attr_name = cmds.textField("attributeTextField", q=True, text=True)
    if "." in attr_name:
        attr_name = attr_name.replace(".","")
    

    char_info = {
        "controller" : cmds.textField("controllerTextField", q=True, text=True),
        "attribute_name" : attr_name,
        "fast" : cmds.textField("fastTextField", q=True, text=True),
        "medium" : cmds.textField("mediumTextField", q=True, text=True),
        "slow" : cmds.textField("slowTextField", q=True, text=True),
        }

    print( char_info)

    #Write to Char File
    with open(script_path, 'w') as info_file:
        json.dump(char_info, info_file)

    cmds.deleteUI("fastSlowUpdater")
    cmds.windowPref("fastSlowUpdater", removeAll=True)

def fastSlowSwitcher(user_mode):
    """This will toggle all rigPuppets in the scene to switch fast and slow"""

    #Ctrl Key is On, set to medium
    if chosenModifiers(kind="Ctrl") == True:
        user_mode = "medium"

    #Find the file path
    script_path = __file__
    script_path = script_path.replace("\\","/")
    script_path = script_path[:script_path.rindex("/")+1]
    script_path += 'wesSceneSetup_CHARACTER.json'

    #Read from Char File
    with open(script_path) as info_file:
        char_info = json.load(info_file)


    reference_objs = cmds.ls(references=True)
    
    for ref_obj in reference_objs:
        #Check if the reference is loaded or not before continueing
        if cmds.referenceQuery(ref_obj, isLoaded=True):
            name_space = cmds.referenceQuery(ref_obj, namespace=True)
            
            # #Remove weird ":" at the start of the name space...
            # if name_space[0] == ":":
            #     name_space = name_space[1:]
            print( name_space)

            try:
                cmds.setAttr(name_space+ ":" + char_info["controller"] + "." + char_info["attribute_name"], int(char_info[user_mode]))
            except:
                print( "Unable to switch spaces... Are you sure this is the attribute you want to update? --> " + name_space +  ":" + char_info["controller"] + "." + char_info["attribute_name"])


    #Viewport settings
    viewports =  cmds.getPanel( type='modelPanel' )

    if user_mode == "fast":
        for vp in viewports:
            cmds.modelEditor(vp,edit=True, rendererName="base_OpenGL_Renderer")

    for vp in viewports:
        if "_camera" in cmds.modelEditor(vp,q=True, camera=True):
            if chosenModifiers(kind="Shift") == True:
                cmds.modelEditor(vp,edit=True, rendererName="vp2Renderer")    
        

    # #Old way of finding puppets
    # top_nodes =  cmds.ls(assemblies=True)
    # rig_puppets = [x for x in top_nodes if ":rp" in x]
    # for puppet in rig_puppets:
    #   global_ctrl = [x for x in cmds.listRelatives(puppet, children=True) if "global_CTRL" in x]
    #   try:
    #       cmds.setAttr(global_ctrl[0] + ".modelDisplayLevel", user_mode)
    #   except:
    #       print( str(puppet) + " and " + str(global_ctrl) + " did not have a switcher")
    
    setActiveWindow()


def snapTo(which="transrot"):
    #To snap to with constraints
    master = cmds.ls(sl=True)[-1:]
    slave = cmds.ls(sl=True)[:-1]

    if not slave: 
        print( "Select something to snap to! =)")
        return

    if len(slave) > 1:
        for each in slave:
            print( "each slave = " + str(slave))
            snapToCommand(master, each, which)
        return
    else:
        snapToCommand(master[0], slave[0], which)


def snapToCommand(master, slave, which):
    print( "master:  " + str(master))
    print( "slave:  " + str(slave))

    transManips = [".translateX",".translateY",".translateZ"] 
    rotsManips = [".rotateX", ".rotateY", ".rotateZ"]

    trans_skip = []
    rots_skip = []

    for tmanip in transManips:
        if not cmds.getAttr(slave+tmanip, settable=True):
            trans_skip.append(tmanip[-1:].lower())

    for rmanip in rotsManips:
        if not cmds.getAttr(slave+rmanip, settable=True):
            rots_skip.append(rmanip[-1:].lower())


    print( "locked translates: " + str(trans_skip))
    print( "locked rotates: " + str(rots_skip))

    if trans_skip == ['x','y','z'] and rots_skip == ['x','y','z']:
        print( "Translate and Rotates maybe locked or stuckeded!")
        cmds.headsUpMessage("Translate and Rotates maybe locked or stuckeded!", time=3)
        return

    if which == "transrot":
        temp_cns = cmds.parentConstraint(master, slave, skipTranslate=trans_skip, skipRotate=rots_skip, maintainOffset=False)
    elif which == "trans":
        temp_cns = cmds.pointConstraint(master, slave, skip=trans_skip, maintainOffset=False)
    elif which == "rots":
        temp_cns = cmds.orientConstraint(master, slave, skip=rots_skip, maintainOffset=False)

    #Drop a keyframe if there is one
    print( "ALL KEYFRAMES CURVES : " + str(cmds.keyframe(slave, query=True, name=True)))
    if cmds.keyframe(slave, query=True, name=True):
        for ea in cmds.keyframe(slave, query=True, name=True):
            if "translateX" in ea:
                cmds.setKeyframe(slave, attribute="tx")
                print( "Added a keyframe for " + str(ea) + ".tx" )
            if "translateY" in ea:
                cmds.setKeyframe(slave, attribute="ty")
                print( "Added a keyframe for " + str(ea) + ".ty" )
            if "translateZ" in ea:
                cmds.setKeyframe(slave, attribute="tz")
                print( "Added a keyframe for " + str(ea) + ".tz" )

            if "rotate" in ea:
                if "X" == ea[-1:]:
                    cmds.setKeyframe(slave, attribute="rx")
                    print( "Added a keyframe for " + str(ea) + ".rx" )
            if "rotate" in ea:
                if "Y" == ea[-1:]:
                    cmds.setKeyframe(slave, attribute="ry")
                    print( "Added a keyframe for " + str(ea) + ".ry" )
            if "rotate" in ea:
                if "Z" == ea[-1:]:
                    cmds.setKeyframe(slave, attribute="rz")
                    print( "Added a keyframe for " + str(ea) + ".rz" )

    cmds.delete(temp_cns)
    cmds.select(slave)

#==================================================================================
#Fun Create Controller | Transfer Stuff | Bake Stuff!
#==================================================================================


def mayaCleanName(inputName):
    new_name = inputName.replace("|","_")
    new_name = new_name.replace(":","_")
    return new_name

def createCurveCtrl(name):
    #Slanted Box
    curveCtrl = cmds.curve(d=3, p=[
    (-2, -1, 1),
    (-2, -1, 1),
    (2, -1, 1),
    (2, -1, 1),
    (2, -1, -1),
    (2, -1, -1),
    (-2, -1, -1),
    (-2, -1, -1),
    (-2, -1, 1),
    (-2, -1, 1),
    
    (0, 1, 1),
    (0, 1, 1),    
    (-2, -1, 1),
    (-2, -1, 1),
    (0, 1, 1),
    (0, 1, 1),

    
    (2, 1, 1),
    (2, 1, 1),   
    (2,-1, 1),
    (2,-1, 1),
    (2, 1, 1),
    (2, 1, 1),   

    
    (2, 1, -1),
    (2, 1, -1), 
    (2,-1, -1),
    (2,-1, -1),
    (2, 1, -1),
    (2, 1, -1),
    
    
    (0, 1, -1),
    (0, 1, -1),
    (-2, -1, -1),
    (-2, -1, -1),
    (0, 1, -1),
    (0, 1, -1),
    
    (0, 1, 1),    
    
    ])
    newCtrl = cmds.rename(curveCtrl, name)
    new_shape = cmds.listRelatives(newCtrl, shapes=True)
    #Flip direction and center it:
    cmds.move(-1, 0, 0, newCtrl+".cv[0:34]", ls=True, r=True)
    cmds.rotate(0, '180deg', 0, newCtrl+".cv[0:34]")

    cmds.setAttr(new_shape[0]+".overrideEnabled", 1)
    cmds.setAttr(new_shape[0]+".overrideColor", 17) #17 = Yellow, 18 = Light blue
    return newCtrl
    
def makeController():
    sel = cmds.ls(sl=True)

    #clean up the Outliner
    if not cmds.objExists("wes_Custom_Controls"):
        cmds.group(name="wes_Custom_Controls", empty=True)
    cmds.setAttr("wes_Custom_Controls.useOutlinerColor" , True)
    cmds.setAttr ("wes_Custom_Controls.outlinerColor" , .53, .74, .34)
    new_select = []
    for ea in sel:
        clean_sel = mayaCleanName(ea)+"_wesCTRL"
        new_ctrl = createCurveCtrl(clean_sel)
        new_group = cmds.group(empty=True, name=clean_sel+"_ROTATEAXIS")
        temp_cns = cmds.pointConstraint(ea, new_group, mo=False)
        cmds.delete(temp_cns)
        cmds.setAttr(new_group+".translateY", 0)
        cmds.parent(new_ctrl, new_group)
        temp_cns = cmds.parentConstraint(ea, new_ctrl, mo=False)
        #cmds.delete(temp_cns)
        cmds.setAttr(new_ctrl+".rotateOrder",k=True)
        cmds.setAttr(new_ctrl+".rotateOrder", 3)

        cmds.parent(new_group, "wes_Custom_Controls")
        new_select.append(new_group)
    cmds.select(new_select)


def wesBake(smartBake=False,simulation=False, sample=1, sel=None):      
    #If selected, add each selected attr name by splitting the string and appending to list.
    channels_sel = []
    if mel.eval('selectedChannelBoxPlugs'):
        for chb in mel.eval('selectedChannelBoxPlugs'):
            channels_sel.append(chb.split(".")[-1])
    print( channels_sel)
     
    #Object Selection
    if sel == None:
        sel = cmds.ls(sl=True)
    
    #Range based on timeline slider.
    range = int(cmds.playbackOptions(q=True, min=True)),int(cmds.playbackOptions(q=True, max=True))
    
    #Check if smartBake is on:
    #PreserveOutsideKeys is set off so that when there is a pairBlend (incoming anim values) that connection will be deleted so that
    # we can clean up the hanging constraints.
    if smartBake == True:
        cmds.bakeResults(sel, 
            at=channels_sel,
            time=range,
            minimizeRotation=True,
            preserveOutsideKeys=False,
            smart=smartBake,
            simulation=simulation,
            sampleBy=sample)
    else:
        cmds.bakeResults(sel, 
            at=channels_sel,
            time=range,
            minimizeRotation=True,
            preserveOutsideKeys=False,
            simulation=simulation,
            sampleBy=sample)

    cmds.filterCurve()

    def checkCon(obj, attrs):
        #To simplify the coding, make a small function to return list of connections by specified attrs
        con_list = []
        for attr in attrs:
            #first, if attribute exists
            if cmds.attributeQuery(attr, node=obj, exists=True):
                #second, if connection exist
                if cmds.listConnections(obj+"."+attr):
                    #Then add to list
                    con_list.extend(cmds.listConnections(obj+"."+attr))
        print( "---checkCon--- Returns: " + str(con_list))
        return con_list

    constraint_conn_list = ["constraintTranslateX", "constraintTranslateY", "constraintTranslateZ",
                    "constraintRotateX", "constraintRotateY", "constraintRotateZ",
                    "constraintScaleX", "constraintScaleY", "constraintScaleZ"]
                                    
    pairBlend_out_list = ["outTranslateX", "outTranslateY", "outTranslateZ",
                    "outRotateX", "outRotateY", "outRotateZ",
                    "outScaleX", "outScaleY", "outScaleZ"]

    #Delete Constraints if not connected...
    for ea in sel:
        #Check for Constraints
        constraint = cmds.listConnections( ea+'.parentInverseMatrix[0]', d=1, s=0,type='constraint')
        print( "Found Constraint Items: " + str(constraint))
        if constraint:
            for con in constraint:
                live_connect = []
                #Add live connections that are not pairBlends
                direct_connects = set([x for x in checkCon(con, constraint_conn_list) if not "pairBlend" in x])
                if direct_connects:
                    live_connect.extend(direct_connects)
                
                #Check if there are pairBlends:
                pairBlend_list = set([x for x in checkCon(con, constraint_conn_list) if "pairBlend" in x])
                if pairBlend_list:
                    for ea in pairBlend_list:
                        live_connect.extend(set(checkCon(ea, pairBlend_out_list)))
                   
                if live_connect == []:
                    print( "No active constraints for: " + str(con))
                    cmds.delete(con)
                else:
                    print( "FOUND ACTIVE CONSTRAINTS for " + str(con) + " ---> " + str(live_connect))

def transferAnimToLocators(smartBake=True):
    sel = cmds.ls(sl=True)
    for ea in sel:
        print ("this is ea: " + str(ea))
        new_loc = [createLocator(con_node=ea)][0]
        print ("this is loc: " + str(new_loc))
        cmds.parentConstraint(ea, new_loc, mo=False)
        wesBake(smartBake=smartBake, sel=new_loc)

        try: cmds.parentConstraint(new_loc, ea, mo=False)
        except:
            try: cmds.orientConstraint(new_loc, ea, mo=False)
            except:
                try: cmds.pointConstraint(new_loc, ea, mo=False)
                except:
                    cmds.headsUpMessage("Couldn't constrain original CON to the transferred locator!", time=3)

def createLocator(con_node=None, loc_name=None):
    list_of_locs = []

    if con_node:
        new_loc = singleLocator(matchTo=con_node, loc_name=str(con_node))
        list_of_locs.append(new_loc)
    else:
        sel = cmds.ls(sl=True)
        if sel:
            for ea in sel:
                #Locator Name
                new_loc = singleLocator(matchTo=ea, loc_name=str(ea))
                list_of_locs.append(new_loc)
        else:
            new_loc = singleLocator(matchTo=None, loc_name=loc_name)
            list_of_locs.append(new_loc)

    return list_of_locs

def singleLocator(matchTo=None, loc_name=None):
    
    if loc_name == None:
        result = cmds.promptDialog(
                        title='Name Your Locator bro!',
                        message='Give it a beautiful name!',
                        button=['OK', 'Cancel'],
                        defaultButton='OK',
                        cancelButton='Cancel',
                        dismissString='Cancel')
        if result == 'OK':
                        loc_name = cmds.promptDialog(query=True, text=True)
                        if loc_name == '':
                            loc_name = 'wesLocator'
        else:
                return    
    loc_name = loc_name+"_LOC"
    new_loc = cmds.spaceLocator(name=loc_name)[0]

    #Giving more attributes to locator
    cmds.setAttr(new_loc+".rotateOrder",k=True)
    cmds.setAttr(new_loc+".rotateOrder", 3)
    cmds.setAttr(new_loc+".overrideEnabled", 1)
    cmds.setAttr(new_loc+".overrideColor", 17) #17 = Yellow, 18 = Light blue
    cmds.setAttr(new_loc+".localScaleX", 5)
    cmds.setAttr(new_loc+".localScaleY", 5)
    cmds.setAttr(new_loc+".localScaleZ", 5)
    
    if not matchTo == None:
        temp_cons = cmds.parentConstraint(matchTo,new_loc, mo=False)
        cmds.delete(temp_cons)
    return new_loc

def createCtrl():
    #Makes a simple control to a selected object.
    sel = cmds.ls(sl=True)
    for ea in sel:
        new_ctrl = cmds.circle()
        new_shape = cmds.listRelatives(new_ctrl, shapes=True)
        
        #Make into a square
        cmds.select(new_shape[0]+".cv[0]", new_shape[0]+".cv[2]", new_shape[0]+".cv[4]", new_shape[0]+".cv[6]")
        cmds.scale(1.6,1.6,1.6, r=True, p=[0,0,0])

        cmds.setAttr(new_shape[0]+".overrideEnabled", 1)
        cmds.setAttr(new_shape[0]+".overrideColor", 18) #17 = Yellow, 18 = Light blue
        cmds.parent(new_shape, ea, s=True, r=True)
        cmds.delete(new_ctrl)           
    cmds.select(sel)




def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=False):
    if not parentWindow:
            wesAnimToolsUI = cmds.window('wesSceneSetupCustomUI', title="wes SceneSetup", sizeable=True, width=user_width)
            cmds.showWindow(wesAnimToolsUI)
            parentWindow = 'wesSceneSetupCustomUI'


    cmds.frameLayout(collapsable=True, label="Setup", collapse=frameClosed, parent=parentWindow, width=user_width )

    cmds.rowColumnLayout(numberOfColumns=1)
    cmds.button(l="Create Layer", command=lambda x:wesCreateLayer(), width=user_width, height=user_height*1.4, bgc=[0.9,.5,.5], annotation="Creates a display layer.  Shift=Lock.  Ctrl=Hide.")
    
    #Fun line hehe..
    cmds.popupMenu()
    cmds.menuItem(l="Fix Perp Cam!", command=lambda x:fixPerspCamera())    
    cmds.menuItem(l="Click me and add some fun to your shot! :)", command=lambda x:runFun())

    cmds.button(l="Gravity Ball (Decimeters)", command=lambda x:ballLauncher(), width=user_width, height=user_height*1.2, bgc=[.2,.4,.3], annotation="Right-click for more options")
    cmds.popupMenu()
    cmds.menuItem(l="Custom Settings", command=lambda x:wesGravityUI(), annotation="Make your own settings for the gravity ball")
    

    # cmds.button(l="Fix Persp Cam", command=lambda x:fixPerspCamera(), width=user_width, height=user_height*0.8,
    #     annotation="If your persp camera is broken in anyway, this will make a fresh one")
    cmds.setParent('..')

    cmds.separator(style="in", height=3)

    cmds.rowColumnLayout(numberOfColumns=1)
    cmds.button(l="Imageplanes On/Off", command=lambda x:toggleImageplane(), width=user_width, height=user_height*.95, bgc=[.9, .9, 0.4], annotation="if you create an 'env_lyr' in display layer. Hold 'CTRL' to hide the env_lyr and show imageplanes and vice versa.")
    cmds.rowColumnLayout(numberOfColumns=1)

    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.button(l="Fast", command=lambda x:fastSlowSwitcher("fast"), width=user_width*.5, height=user_height*.75, bgc=[.7, .95, .3], annotation="'CTRL' for medium / 'SHIFT' for VP2.0 on _camera")
    cmds.popupMenu()
    cmds.menuItem(l="Change Default Naming Convention", command=lambda x:fastSlowUpdater() )
    cmds.button(l="Slow", command=lambda x:fastSlowSwitcher("slow"), width=user_width*.5, height=user_height*.75, bgc=[1, .6, .4], annotation="'CTRL' for medium / 'SHIFT' for VP2.0 on _camera")
    cmds.popupMenu()
    cmds.menuItem(l="Change Default Naming Convention", command=lambda x:fastSlowUpdater() )

    cmds.setParent('..')

    cmds.separator(style="in", height=10)

    cmds.rowColumnLayout(numberOfColumns=3)
    
    cmds.button(l="create", command=lambda x:makeController(), width=user_width*.333, height=user_height, bgc=[.78, .78, .55], annotation="Create a Control for selected object")
    cmds.popupMenu()
    cmds.menuItem(l="Locator", command=lambda x:createLocator())
    cmds.menuItem(l="Controller", command=lambda x:makeController())
    cmds.menuItem(l="Control Shape to existing object!", command=lambda x:createCtrl())

    cmds.button(l="transfer", command=lambda x:transferAnimToLocators(smartBake=False), width=user_width*.333, height=user_height, bgc=[.78, .55, .78], annotation="Transfer anim to locator on 1s")
    cmds.popupMenu()
    cmds.menuItem(l="Transfer Anim on 1s", command=lambda x:transferAnimToLocators(smartBake=False))
    cmds.menuItem(l="Transfer Anim on Same Keys (SmartBake)", command=lambda x:transferAnimToLocators(smartBake=True))


    cmds.button(l="bake", command=lambda x:wesBake(smartBake=False), width=user_width*.333, height=user_height, bgc=[.55, .78, .78], annotation="Bake anim on 1s")
    cmds.popupMenu()
    cmds.menuItem(l="Bake Anim on 1s", command=lambda x:wesBake())
    cmds.menuItem(l="Bake Anim on Same Keys (SmartBake)", command=lambda x:wesBake(smartBake=True))
    


    cmds.setParent('..')





    cmds.setParent('..')
    cmds.button(l="Snap To", command=lambda x:snapTo(), width=user_width, height=user_height*1, bgc=[.5, .5, .5], annotation="Shift select object to snap to.  If there is a key it will key")
    cmds.popupMenu()
    cmds.menuItem(l="Translate Only", command=lambda x:snapTo(which="trans"))
    cmds.menuItem(l="Rotates Only", command=lambda x:snapTo(which="rots"))
    cmds.setParent('..')

    cmds.rowColumnLayout(numberOfColumns=3)
    cmds.button(l="point", command=lambda x:wesSimpleConstraint("point"), width=user_width*.333, height=user_height, bgc=[.4, .5, .5], annotation="Ctrl = Constrain without any offsets.")
    cmds.button(l="orient", command=lambda x:wesSimpleConstraint("orient"), width=user_width*.333, height=user_height, bgc=[.5, .4, .5], annotation="Ctrl = Constrain without any offsets.")
    cmds.button(l="parent", command=lambda x:wesSimpleConstraint("parent"), width=user_width*.333, height=user_height, bgc=[.5, .5, .4], annotation="Ctrl = Constrain without any offsets.")
    cmds.setParent('..')



    cmds.setParent('..')
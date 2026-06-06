"""
##########################################################################################################
######                              Wesley's Offset Anim script                                     ######
######                                  heywesley@gmail.com                                         ######
######                                                                                              ######
######                                                                                              ######
                        This tool allows you to quickly save sets of offsets.
                        Which allows you to revert back at any given time to make easy
                        changes and then offset it again either at the same amount, or
                        at another amount.  You can offset certain groups of keys, or
                        the entire objects selected.

                    v1.1b - added checker to make sure theres no duplicate names

                    v1.1a - fix refresh button

                    v1.1  - convert integer to float. Allows for more detailed offsets.

                    v1.0  - First running version of the script





######                                                                                              ######
######                                                                                              ######
######                                                                                              ######
######                                                                                              ######
##########################################################################################################
"""




import maya.cmds as cmds
import maya.mel as mel
import ast
from functools import partial

def setActiveWindow():
    #Select the maya again
    name = mel.eval("$tmp=$gMainWindow")
    cmds.showWindow(name)

def mayaSafeName(usrName):
    """Using the creating of a node with name to find a maya safe name"""
    usr_sel = cmds.ls(sl=True)
    safe_name = cmds.createNode('transform', name=usrName)
    cmds.delete(safe_name)
    cmds.select(usr_sel)
    print( "converted " + usrName + " to " + safe_name)
    return safe_name

def grabValues(whatGrabbing):
    list_name = cmds.textScrollList( "myOffsetList", query=True, selectItem=True)[0]
    sort_this_list = cmds.getAttr(list_name+".offsetAnim")

    #0 = List // 1 = increment // 2 = hasOffset
    buffer_split = sort_this_list.split("|")
    object_selection = ast.literal_eval(buffer_split[0])
    increment = buffer_split[1]
    hasOffset = buffer_split[2]

    #Extract objects only, selection:
    object_list = []
    for each in object_selection:
        object_list.append(each[0])

    if whatGrabbing == "object_selection":
        return object_selection
    if whatGrabbing == "object_list":
        return object_list
    if whatGrabbing == "increment":
        return int(increment)
    if whatGrabbing == "hasOffset":
        return hasOffset





def findSelectedKeys(object_sel):
    """It will return a list of curves and a list of indexes.  [ [curve, index],[curve, index],[curve, index] ]"""
    all_selected = []
    #find if there is selected keys
    selected_curves = cmds.keyframe(object_sel, q=True,name=True, selected=True)

    #If there isn't any selcted keys, then just return letting us know its none selected
    if not selected_curves:
        group = []
        group.append([object_sel, "NONE SELECTED"])
        return group
        

    for each in selected_curves:
        #print( "\n working on this curve: " + str(each))
    
        curve_and_indexes = [each, cmds.keyframe(each, q=True, indexValue=True, selected=True)]
        #print( curve_and_indexes)
        all_selected.append(curve_and_indexes)

    return all_selected


def createRanges(lst):
    ret = []
    a = b = lst[0]                           # a and b are range's bounds

    for el in lst[1:]:
        if el == b+1: b = el                 # range grows
        else:                                # range ended
            ret.append(a if a==b else [a,b]) # is a single or a range?
            a = b = el                       # let's start again with a single
    ret.append(a if a==b else [a,b])         # corner case for last single/range
    return ret


def offsetAnim(selection,increment):

    timeValue = 0


    #### OLD COLD ####

    # for ea in selection:
    #     cmds.keyframe(ea, relative=True, timeChange=(0 + timeValue), option="over")
    #     timeValue = timeValue + increment


    ####NEW CODE######

    #Lets find the first grouping of object + curve_and_indexes
    for sel in selection:
        #sel[0] = object
        #now lets look into the curve_and_indexes:
        #rebuilding as list
        print( str(sel) + "<---- This suppose to be the selection groupping")
        

        obj_name = sel[0]
        for curve_grouping in sel[1]:
            curve_name = curve_grouping[0]
            indexes = curve_grouping[1]
            print( obj_name)
            print( curve_name)
            print( indexes)

            if indexes == "NONE SELECTED":
                cmds.keyframe(obj_name, relative=True, timeChange=(0 + timeValue), option="over")
                
            else:
                #create ranges to group moves.
                new_ranges = createRanges(indexes)

                #Now lets break it down and look at each index range.
                for ea_range in new_ranges:
                    print( "For: " + curve_name + "   ---     Range list is: " + str(ea_range))
                    cmds.keyframe(curve_name, index=(ea_range[0], ea_range[1]), relative=True, timeChange=(0 + timeValue), option="over")
                    

        #Update the increment for the next object in list
        timeValue = timeValue + increment

def runOffset():
    object_selection = grabValues("object_selection")

    #Check user inputted:    
    increment = cmds.intField('entered_offset_value', q=True, value=True)
    list_name = cmds.textScrollList( "myOffsetList", query=True, selectItem=True)[0]
    
    #Check if we are reverting or offsetting:
    hasOffset = grabValues("hasOffset")
    if hasOffset == "True":
        increment = -increment

        offsetAnim(object_selection,increment)        

        #Update UI and Note
        cmds.button("offsetButton", e=True,l="Offset:", bgc=[.65, 1, .28])
        #update increment value
        cmds.intField('entered_offset_value', e=True, enable=True)

        the_note = str(grabValues("object_selection")) + "|" + str(-increment) + "|" + "False"
        cmds.setAttr(list_name+".offsetAnim", the_note, type="string")

    else:
        offsetAnim(object_selection,increment)

        #Update UI and Note
        cmds.button("offsetButton", e=True,l="Revert:", bgc=[1, .35, .28])
        #update increment value
        cmds.intField('entered_offset_value', e=True, enable=False)

        the_note = str(grabValues("object_selection")) + "|" + str(increment) + "|" + "True"
        cmds.setAttr(list_name+".offsetAnim", the_note, type="string")

    setActiveWindow()


def createList():

    #Check if there is more than one selected
    selection = cmds.ls(sl=True)
    if not len(selection) > 1:
        cmds.confirmDialog(message="dudee.. you can't offset just one controller.. LOL!! go back.. go select more than 1 ;)")
        return

    #So far this tool doesn't handle "|" very well.  So going to put in a warning here:
    if [x for x in selection if "|" in x]:
        bad_ones = ""
        tmp = [x for x in selection if "|" in x]
        for ea in tmp:
            bad_ones = bad_ones + (ea+"\n")



        cmds.confirmDialog(message="Sorry bud!\n\nThere are duplicate names in the selection.\nI'm not good enough to handle it yet!\nPlease rename these ones: \n\n"+ bad_ones)
        return

    #creating the list...
    new_note = []
    for sel in selection:
        groupings = []

        for each in findSelectedKeys(sel):
            groupings.append(each)

        new_note.append([sel, groupings])

    # [    object , [ [curve ,[indexes]], [curve,[indexes]] ]      ]
    print( new_note)



    if not cmds.objExists("wes_OffsetAnimNode"):
        cmds.createNode( 'transform', n='wes_OffsetAnimNode' )
        cmds.setAttr("wes_OffsetAnimNode.useOutlinerColor" , True)
        cmds.setAttr ("wes_OffsetAnimNode.outlinerColor" , .2, .34, .19)

    #Temporary Increment:
    increment = 1
    has_offset = False

    #########auto-make a name, remove any nameSpaces#############
    #
    # first_obj = selection[0]
    # print( first_obj)
    # if ":" in first_obj:
    #     name_no_namespace = first_obj[first_obj.rindex(":")+1:]
    # else:
    #     name_no_namespace = first_obj
    ############################################################

    ##########Manual input name################ 
    result = cmds.promptDialog(
                title='Offset Name',
                message='Offset List Name:',
                button=['OK', 'Cancel'],
                defaultButton='OK',
                cancelButton='Cancel',
                dismissString='Cancel')

    if result == 'OK':
            user_name = cmds.promptDialog(query=True, text=True)
            list_name = mayaSafeName(user_name) + "_offset"
    else:
        return


    ############################################

    


    if not cmds.objExists(list_name):
        cmds.createNode('transform', n=list_name)
        cmds.parent(list_name, "wes_OffsetAnimNode")
    
        #Write out the values as a note:
        the_note = str(new_note) + "|" + str(increment) + "|" + str(has_offset)
        print( the_note)

        cmds.addAttr(list_name, dt="string", longName="offsetAnim", shortName="offAnm")
        cmds.setAttr(list_name+".offsetAnim", the_note, type="string")
        cmds.textScrollList( "myOffsetList", edit=True, append=list_name)

        #select the list
        cmds.textScrollList( "myOffsetList", edit=True, selectItem=list_name)
        cmds.select(selection)

    else:
        cmds.confirmDialog(message="Ufgghkjahaj! One already exists yo! Make a custom name yo!")

    updateButtons()


def deleteList():
    list_name = cmds.textScrollList( "myOffsetList", query=True, selectItem=True)[0]
    cmds.delete(list_name)
    cmds.textScrollList( "myOffsetList", edit=True, removeItem=list_name)
    cmds.select(cl=True)

def updateButtons():
    increment = grabValues("increment")
    hasOffset = grabValues("hasOffset")

    print( hasOffset)
    print( increment)

    if hasOffset == "True":
        cmds.button("offsetButton", e=True,l="Revert:", bgc=[1, .35, .28])
        #update increment value
        cmds.intField('entered_offset_value', e=True, enable=False, value=increment)
    else:
        cmds.button("offsetButton", e=True,l="Offset:", bgc=[.65, 1, .28])
        #update increment value
        cmds.intField('entered_offset_value', e=True, enable=True, value=increment)



    #Select values
    print( grabValues("object_list"))
    cmds.select(grabValues("object_list"))


def loadList():
    if not cmds.objExists("wes_OffsetAnimNode"):
        return

    #Clear list first
    cmds.textScrollList( "myOffsetList", edit=True, removeAll=True)

    the_list = cmds.listRelatives("wes_OffsetAnimNode", children=True)
    if not the_list == None:
        for each in the_list:
            print( each)
            cmds.textScrollList( "myOffsetList", edit=True, append=each)


def UI(parentWindow=None, user_width=180, user_height=17, frameClosed=False):
    if not parentWindow:
        if cmds.window("wesOffsetAnimCustomUI", exists=True, resizeToFitChildren=True):
            cmds.deleteUI("wesOffsetAnimCustomUI")

        wesAnimToolsUI = cmds.window('wesOffsetAnimCustomUI', title="wesOffsetAnim", sizeable=True, width=user_width, height=100)
        cmds.showWindow(wesAnimToolsUI)
        parentWindow = 'wesOffsetAnimCustomUI'

    cmds.frameLayout(collapsable=True, label="Offset Anim", collapse=frameClosed, parent=parentWindow,width=user_width)
    
    cmds.rowColumnLayout(numberOfColumns=1)
    cmds.button(l="Create List", command=lambda x:createList(), width=user_width, bgc=[.8, .8, .8])    
    cmds.textScrollList( "myOffsetList", allowMultiSelection=False, numberOfRows=8,  width=user_width, selectCommand=partial (updateButtons) )

    cmds.popupMenu()
    cmds.menuItem('Refresh', command=lambda x:loadList())

    cmds.button(l="Delete Selected", command=lambda x:deleteList(), width=user_width, bgc=[.2, .2, .2], height=user_height*.85) 
    cmds.setParent('..')
    



    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.button("offsetButton", l="Offset:", command=lambda x:runOffset(), width=user_width*.7, height=user_height*1.3, bgc=[.65, 1, .28]) #bgc=[1, .35, .28])
    cmds.intField ('entered_offset_value', value=1 , width=user_width*.3, height=user_height*1.3 )
    cmds.setParent('..')


    cmds.setParent('..')

    loadList()

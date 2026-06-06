
import maya.cmds as cmds
import math

"""
Formula helped and solved by Jeffrey Sum, Physics Teacher in California!  Thank you for your support!
"""

def gravCalculator(obj, numFrames=49, velocity=9.807, frame_rate=24, transY=0, frame=1001, grav=-9.807, metric=10):
    print ("input velocity: " + str(velocity))
    print ("input grav: " + str(grav))
    print ("input transY: " + str(transY))

    for time in range(numFrames):

        cmds.setKeyframe(obj, attribute="ty", value=transY, time=(frame, frame))
        
        final_velocity = velocity + ( grav * (1.000 / frame_rate ) )
        displacement = .5 * ( velocity + final_velocity) * (1.000 / frame_rate )    
        velocity = final_velocity
        transY = transY + displacement * metric   
        frame = frame + 1

    """
        v = g * t
        d = 0.5 * g * t^2.

        VELOCITY?! : 96.1779
        
        vf - vi = g * t
        vf = vi + g * t
        final_velocity = velocity + ( grav * (1.000 / frame_rate ) )
        final_velocity = -9.807 + ( 9.807 * (1 / 24))  
            -9.848                       0.408625
        
        distransY = .5 * ( velocity + final_velocity) * (1.000 / frame_rate )    
        distransY = .5 *     ( -9.807 + -9.848 )      *       (1 / 24)
          -0.4096    = .5 *             -19.655          *         .04167
        
        distransY = .5 *     ( -9.807 + -9.848 )      *       (1 / 24)^2

                       .5 *             -19.655           *         .001736

        transY = transY - distransY * metric   
          4.096         0     -   -0.4096    *   10
    """

def ballLauncher(frame_rate=24, grav=-9.807, metric=10):
    if not cmds.ls(sl=True):
        cmds.confirmDialog(m="Please select an object!")
        return
    if len(cmds.ls(sl=True)) > 1:
        cmds.confirmDialog(m="Please select only one object!")
        return
    
    sel = cmds.ls(sl=True)[0]
    
    #To find world space values, use a temporary oject:
    value_grab = cmds.polySphere()[0]
    cmds.pointConstraint(sel, value_grab, mo=False)

    cur_time = cmds.currentTime(q=True)
    end_time = cmds.playbackOptions(q=True, max=True)
    numFrames = int(end_time - cur_time)


    cur_val_x = cmds.getAttr(value_grab+".translateX")
    cur_val_y = cmds.getAttr(value_grab+".translateY")
    cur_val_z = cmds.getAttr(value_grab+".translateZ")
    past_val_x = cmds.getAttr(value_grab+".translateX", time=(cur_time-1))
    past_val_y = cmds.getAttr(value_grab+".translateY", time=(cur_time-1))
    past_val_z = cmds.getAttr(value_grab+".translateZ", time=(cur_time-1))
    cmds.delete(value_grab)


    #Possibly right equation
    displacement = ( cur_val_y - past_val_y )
    print ("displacement : " + str(displacement))
    per_frame_time = 1.000 / frame_rate
    velocity = displacement / per_frame_time / metric
    print ("initial velocity :" + str(velocity))

    #  vf = vi + g * t
    #   v = d / t

    #Find the next values
    next_val_x = cur_val_x + (cur_val_x - past_val_x)
    next_val_z = cur_val_z + (cur_val_z - past_val_z)
    


    #Creating the ball
    tmp_sphere = cmds.polySphere()[0]
    gravCalculator(tmp_sphere, numFrames=numFrames, velocity=velocity, frame_rate=frame_rate, transY=cur_val_y, frame=cur_time, grav=grav)

    #Translation linear of X and Z axis:
    cmds.setKeyframe(tmp_sphere, attribute="tx", value=cur_val_x, time=(cur_time))
    cmds.setKeyframe(tmp_sphere, attribute="tz", value=cur_val_z, time=(cur_time))
    cmds.setKeyframe(tmp_sphere, attribute="tx", value=next_val_x, time=(cur_time+1))
    cmds.setKeyframe(tmp_sphere, attribute="tz", value=next_val_z, time=(cur_time+1))
    cmds.keyTangent(tmp_sphere, itt="clamped", ott="clamped")
    cmds.setInfinity(tmp_sphere, poi="linear")

    #Set scale value to the bounding box of selected object's shape! woop woop.
    bb = cmds.exactWorldBoundingBox(cmds.listRelatives(sel, shapes=True)[0])
    bbox = [(bb[3]-bb[0]),(bb[4]-bb[1]), (bb[5]-bb[2])]
    scale_val = ( max(bbox)/2 ) * 1.1 #Making it 10% bigger.

    cmds.setAttr(tmp_sphere+".scaleX", scale_val)
    cmds.setAttr(tmp_sphere+".scaleY", scale_val)
    cmds.setAttr(tmp_sphere+".scaleZ", scale_val)

    #Final touch up clean ups.
    cmds.setAttr(tmp_sphere+".translateX", lock=True)
    cmds.setAttr(tmp_sphere+".translateY", lock=True)
    cmds.setAttr(tmp_sphere+".translateZ", lock=True)
    new_name = cmds.rename(tmp_sphere,"wesGravityBall"+sel)
    cmds.select(new_name)
    

def wesGravityUI(user_width=200, user_height=20):

    if cmds.window("wesGravityUI", exists=True):
        cmds.deleteUI("wesGravityUI")
        cmds.windowPref("wesGravityUI", removeAll=True)

    wesRetimeUI = cmds.window('wesGravityUI', title="Update the Character Values", sizeable=True, width=user_width, height=100)
    cmds.showWindow(wesRetimeUI)
    parentWindow = 'wesGravityUI'

    cmds.frameLayout('wesGravity UI Settings', lv=False, bv=False, mw=7, mh=7)

    #speed, numFrames=49, velocity=-98.07, frame_rate=24, transY=0, frame=1001

    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.text('Frame Rate:', width=user_width*.7)
    cmds.textField("frameRateTextField", ed=True, width=user_width*.3, height=user_height*1, text=24) 
    cmds.text('Velocity:', width=user_width*.7)
    cmds.textField("velocityTextField", ed=True, width=user_width*.3, height=user_height*1, text=9.807) 
    cmds.text('transY:', width=user_width*.7)
    cmds.textField("transYTextField", ed=True, width=user_width*.3, height=user_height*1, text=0)     
    cmds.text('Starting Frame:', width=user_width*.7)
    cmds.textField("startingFrameTextField", ed=True, width=user_width*.3, height=user_height*1, text=1001)     
    cmds.text('Length of Frames:', width=user_width*.7)
    cmds.textField("lengthFramesTextField", ed=True, width=user_width*.3, height=user_height*1, text=49)     
    cmds.setParent('..')

    cmds.rowColumnLayout(numberOfColumns=2)
    cmds.button(l="Create Custom Gravity Ball", command=lambda x:wesGravityUIRun(update=True), width=user_width*.8, height=user_height, bgc=[.3,.6,.3])
    cmds.button(l="Cancel", command=lambda x:wesGravityUIRun(update=False), width=user_width*.2, height=user_height,bgc=[.6,.3,.3])
    cmds.setParent('..')


    cmds.setParent('..')


    cmds.setParent('..')

def wesGravityUIRun(update):
    if update == False:
        cmds.deleteUI("wesGravityUI")
        cmds.windowPref("wesGravityUI", removeAll=True)  
        return

    #speed, numFrames=49, velocity=-98.07, frame_rate=24, transY=0, frame=1001
    frame_rate = int(cmds.textField("frameRateTextField", q=True, text=True))
    velocity = float(cmds.textField("velocityTextField", q=True, text=True))
    transY = float(cmds.textField("transYTextField", q=True, text=True))
    frame = int(cmds.textField("startingFrameTextField", q=True, text=True))
    numFrames = int(cmds.textField("lengthFramesTextField", q=True, text=True))

    tmp_sphere = cmds.polySphere()[0]
    gravCalculator(tmp_sphere, numFrames=numFrames, velocity=velocity, frame_rate=frame_rate, transY=transY, frame=frame)
    cmds.setAttr(tmp_sphere+".translateY", lock=True)
    new_name = cmds.rename(tmp_sphere,"wesGravityBall_custom")
    cmds.select(new_name)

    cmds.deleteUI("wesGravityUI")
    cmds.windowPref("wesGravityUI", removeAll=True)  

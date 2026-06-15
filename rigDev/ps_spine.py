import maya.cmds as cmds
import maya.mel as mel
from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui

WINDOW_NAME = 'spineRigTool'
_win = None


def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def show():
    global _win
    try:
        _win.close()
        _win.deleteLater()
    except Exception:
        pass
    _win = SpineRigUI(_maya_main_window())
    _win.show()


# ── rig builder ───────────────────────────────────────────────────────────────

def buildSpine(prefix, surface_spans=3):
    existing = cmds.ls(prefix + '_000_FK', prefix + '_000_SKL', prefix + '_000_JNT')
    if existing:
        raise RuntimeError(
            'Rig nodes already exist for "' + prefix + '" (' + ', '.join(existing) + '). '
            'Undo the previous build or delete existing rig nodes before rebuilding.'
        )

    currentIntangent = cmds.keyTangent(query=True, itt=True, g=True)
    currentOutTangent = cmds.keyTangent(query=True, ott=True, g=True)

    try:
        cmds.keyTangent(itt='linear', g=True)
        cmds.keyTangent(ott='linear', g=True)

        cmds.select(prefix)
        curve_shape = cmds.listRelatives(prefix, shapes=True, noIntermediate=True)[0]
        degree = cmds.getAttr(prefix + '.degree')
        span = cmds.getAttr(prefix + '.spans')
        pointNumber = degree + span
        points = cmds.getAttr(prefix + '.cv[0:' + str(pointNumber) + ']')
        joint = None

        for i in range(0, pointNumber):
            lastJoint = joint
            joint = cmds.joint(p=(points[i][0], points[i][1], points[i][2]),
                               n=(prefix + '_' + str(i).zfill(3) + '_FK'))
            if i > 0:
                cmds.joint(lastJoint, e=True, zso=True, oj='xyz', sao='xup')
                cmds.setAttr(lastJoint + '.jointOrientX', 0)
            cmds.joint(e=True, oj='none', secondaryAxisOrient='xup', zso=True)

        cmds.setAttr(prefix + '_' + str(pointNumber - 1).zfill(3) + '_FK.jointOrient', 0, 0, 0)

        selection = cmds.ls(sl=True)
        startJoint = prefix + '_000_FK'
        endJoint = selection

        cmds.select(startJoint, endJoint)
        cmds.ikHandle(sol='ikSplineSolver', name=(prefix + '_000_IKH'))
        # Wire the spine curve into the IK handle.
        # Use isConnected to check the exact attribute — listConnections can
        # return either the shape or the transform depending on Maya version,
        # making name comparison unreliable.
        if not cmds.isConnected(curve_shape + '.worldSpace[0]',
                                 prefix + '_000_IKH.inCurve'):
            # Disconnect whatever the IK solver auto-connected, delete its curve
            # transform, then wire in our spine curve.
            # Must disconnect BEFORE connectAttr — Maya keeps broken connections
            # alive even after the source node is deleted.
            ik_plugs = cmds.listConnections(prefix + '_000_IKH.inCurve',
                                            source=True, plugs=True) or []
            for plug in ik_plugs:
                cmds.disconnectAttr(plug, prefix + '_000_IKH.inCurve')
                src_node = plug.split('.')[0]
                src_xform = cmds.listRelatives(src_node, parent=True) or []
                to_del = src_xform[0] if src_xform else src_node
                if to_del != prefix and cmds.objExists(to_del):
                    cmds.delete(to_del)
            cmds.connectAttr(curve_shape + '.worldSpace[0]',
                             prefix + '_000_IKH.inCurve')

        connections = cmds.listConnections(prefix + '_000_IKH', t='ikEffector')
        cmds.rename(str(connections[0]), prefix + '_000_EFF')

        cmds.select(prefix + '_000_FK')
        selection = cmds.ls(sl=True)
        rels = ([str(s) for s in cmds.listRelatives(selection, ad=True, typ='joint')] +
                [str(s) for s in selection])
        relsSort = sorted(rels)

        for count, jnt in enumerate(relsSort):
            cmds.select(clear=True)
            newJoint = cmds.joint()
            skinJNT = cmds.rename(newJoint, prefix + '_' + str(count).zfill(3) + '_JNT')
            cmds.parent(skinJNT, jnt)
            cmds.setAttr(skinJNT + '.tx', 0)
            cmds.setAttr(skinJNT + '.ty', 0)
            cmds.setAttr(skinJNT + '.tz', 0)
            cmds.setAttr(skinJNT + '.jointOrientX', cmds.getAttr(jnt + '.jointOrientX'))
            cmds.setAttr(skinJNT + '.jointOrientY', cmds.getAttr(jnt + '.jointOrientY'))
            cmds.setAttr(skinJNT + '.jointOrientZ', cmds.getAttr(jnt + '.jointOrientZ'))

        cmds.setAttr(prefix + '_000_JNT.jointOrientX', 0)
        cmds.setAttr(prefix + '_000_JNT.jointOrientY', 0)
        cmds.setAttr(prefix + '_000_JNT.jointOrientZ', 0)

        for i in range(0, 2):
            cmds.duplicate(prefix, n='loft' + str(i).zfill(3) + '_CRV')

        cmds.rebuildCurve('loft000_CRV', rt=0, s=pointNumber)
        cmds.rebuildCurve('loft001_CRV', rt=0, s=pointNumber)
        cmds.move(.5, 0, 0, 'loft000_CRV', absolute=True)
        cmds.move(-.5, 0, 0, 'loft001_CRV', absolute=True)

        cmds.loft('loft000_CRV', 'loft001_CRV', ch=True, rn=True, ar=True, n=(prefix + '_000_GEO'))
        cmds.rebuildSurface(prefix + '_000_GEO', ch=True, rpo=True, rt=False, end=True, kr=False,
                            kcp=False, kc=False, su=True, du=3, sv=surface_spans, dv=3,
                            tol=0.01, fr=False, dir=2)
        cmds.delete(prefix + '_000_GEO', ch=True)

        cmds.loft('loft000_CRV', 'loft001_CRV', ch=True, rn=True, ar=True, n=(prefix + '_001_GEO'))
        cmds.rebuildSurface(prefix + '_001_GEO', ch=True, rpo=True, rt=False, end=True, kr=False,
                            kcp=False, kc=False, su=True, du=3, sv=surface_spans, dv=3,
                            tol=0.01, fr=False, dir=2)
        cmds.delete(prefix + '_001_GEO', ch=True)

        cmds.delete('loft000_CRV', 'loft001_CRV')
        cmds.reverseSurface(prefix + '_000_GEO', ch=True, d=0, rpo=True)
        cmds.reverseSurface(prefix + '_001_GEO', ch=True, d=0, rpo=True)

        for i in range(0, 3):
            cmds.joint(p=(0, 0, 0), name=prefix + '_Geo' + str(i).zfill(3) + '_FK')
            cmds.group(em=True, name=prefix + '_Geo' + str(i).zfill(3) + '_GRP')

        cmds.parent(prefix + '_Geo000_FK', prefix + '_Geo000_GRP')
        cmds.parent(prefix + '_Geo001_FK', prefix + '_Geo001_GRP')
        cmds.parent(prefix + '_Geo002_FK', prefix + '_Geo002_GRP')

        cmds.createNode('follicle', name=prefix + '_Mid000_FOLShape')
        cmds.connectAttr(prefix + '_000_GEOShape.worldMatrix[0]',
                         prefix + '_Mid000_FOLShape.inputWorldMatrix')
        cmds.connectAttr(prefix + '_000_GEOShape.local',
                         prefix + '_Mid000_FOLShape.inputSurface')
        cmds.connectAttr(prefix + '_Mid000_FOLShape.outTranslate', prefix + '_Mid000_FOL.translate')
        cmds.connectAttr(prefix + '_Mid000_FOLShape.outRotate', prefix + '_Mid000_FOL.rotate')
        cmds.setAttr(prefix + '_Mid000_FOLShape.parameterU', .5)
        cmds.setAttr(prefix + '_Mid000_FOLShape.parameterV', .5)

        for i in range(0, 3):
            cmds.circle(radius=4, nr=(0, 1, 0), c=(0, 0, 0),
                        n=prefix + '_' + str(i).zfill(3) + '_CTL', ch=False)
            cmds.group(em=True, name=prefix + '_CTL' + str(i).zfill(3) + '_GRP')

        cmds.parent(prefix + '_000_CTL', prefix + '_CTL000_GRP')
        cmds.parent(prefix + '_001_CTL', prefix + '_CTL001_GRP')
        cmds.parent(prefix + '_002_CTL', prefix + '_CTL002_GRP')

        cmds.group(em=True, name=prefix + '_CTL001_TopSDK_GRP')
        cmds.parent(prefix + '_CTL001_TopSDK_GRP', prefix + '_Mid000_FOL')
        cmds.setAttr(prefix + '_CTL001_TopSDK_GRP.translate', 0, 0, 0)

        cmds.group(em=True, name=prefix + '_CTL001_TopRotateSDK_GRP')
        cmds.parent(prefix + '_CTL001_TopRotateSDK_GRP', prefix + '_CTL001_TopSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_TopRotateSDK_GRP.translate', 0, 0, 0)

        cmds.group(em=True, name=prefix + '_CTL001_BtmRotateSDK_GRP')
        cmds.parent(prefix + '_CTL001_BtmRotateSDK_GRP', prefix + '_CTL001_TopRotateSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_BtmRotateSDK_GRP.translate', 0, 0, 0)

        cmds.parent(prefix + '_CTL001_GRP', prefix + '_CTL001_BtmRotateSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_GRP.translate', 0, 0, 0)
        cmds.rename(prefix + '_CTL001_GRP', prefix + '_CTL001_BtmSDK_GRP')

        cmds.parentConstraint(prefix + '_001_CTL', prefix + '_Geo001_FK')
        cmds.setAttr(prefix + '_CTL001_BtmSDK_GRP.rotate', 0, 0, 0)
        pc = cmds.pointConstraint(prefix + '_000_EFF', prefix + '_CTL002_GRP', mo=False)[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_002_CTL', prefix + '_Geo002_FK')
        pc = cmds.pointConstraint(prefix + '_000_FK', prefix + '_CTL000_GRP', mo=False)[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo000_FK')

        up_loc = prefix + '_up_LOC'
        cmds.spaceLocator(n=up_loc)
        cmds.parent(up_loc, prefix + '_000_FK')
        cmds.setAttr(up_loc + '.translate', 0, 0, -2)
        cmds.setAttr(up_loc + '.rotate', 0, 0, 0)
        ac = cmds.aimConstraint(prefix + '_001_FK', prefix + '_CTL000_GRP',
                                aimVector=[0, 1, 0], worldUpType='object',
                                worldUpObject=up_loc)[0]
        cmds.delete(ac)

        cmds.parent(up_loc, endJoint)
        cmds.setAttr(up_loc + '.translate', 0, 0, -2)
        cmds.setAttr(up_loc + '.rotate', 0, 0, 0)
        ac = cmds.aimConstraint(lastJoint, prefix + '_CTL002_GRP',
                                aimVector=[0, -1, 0], upVector=[0, 0, -1],
                                worldUpType='object', worldUpObject=up_loc)[0]
        cmds.delete(ac)
        cmds.delete(up_loc)

        cmds.group(em=True, name=prefix + '_UpTwist000_NULL')
        cmds.group(em=True, name=prefix + '_DwnTwist000_NULL')
        cmds.parent(prefix + '_UpTwist000_NULL', prefix + '_000_CTL')
        cmds.parent(prefix + '_DwnTwist000_NULL', prefix + '_002_CTL')
        cmds.setAttr(prefix + '_DwnTwist000_NULL.translate', 0, 0, 0)
        cmds.setAttr(prefix + '_UpTwist000_NULL.translate', 0, 0, 0)
        cmds.setAttr(prefix + '_DwnTwist000_NULL.rotate', 180, 0, 90)
        cmds.setAttr(prefix + '_UpTwist000_NULL.rotate', 180, 0, 90)

        cmds.select(prefix + '_000_CTL')
        cmds.addAttr(keyable=True, longName='twist')
        cmds.select(prefix + '_002_CTL')
        cmds.addAttr(keyable=True, longName='twist')

        cmds.parent(prefix + '_Geo001_GRP', prefix + '_Mid000_FOL')
        cmds.setAttr(prefix + '_Geo001_GRP.translate', 0, 0, 0)
        cmds.setAttr(prefix + '_Geo001_GRP.rotate', 0, 0, 0)

        pc = cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo000_GRP')[0]
        cmds.delete(pc)
        pc = cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo002_GRP')[0]
        cmds.delete(pc)

        for i in range(0, pointNumber):
            node = cmds.createNode('multiplyDivide',
                                   n=(prefix + '_Twist' + str(i).zfill(3) + '_MDN'))
            cmds.connectAttr(prefix + '_002_CTL.twist', node + '.input1X')
            cmds.connectAttr(prefix + '_001_CTL.rotateY', node + '.input1Y')
            cmds.connectAttr(prefix + '_000_CTL.twist', node + '.input1Z')

        for i in range(0, pointNumber):
            pma = cmds.createNode('plusMinusAverage',
                                  n=(prefix + '_Twist' + str(i).zfill(3) + '_PMA'))
            cmds.setAttr(pma + '.operation', 1)
            cmds.connectAttr(prefix + '_Twist' + str(i).zfill(3) + '_MDN.outputX',
                             pma + '.input1D[0]')
            cmds.connectAttr(prefix + '_Twist' + str(i).zfill(3) + '_MDN.outputY',
                             pma + '.input1D[1]')
            cmds.connectAttr(prefix + '_Twist' + str(i).zfill(3) + '_MDN.outputZ',
                             pma + '.input1D[2]')

        for i in range(0, pointNumber):
            cmds.connectAttr(prefix + '_Twist' + str(i).zfill(3) + '_PMA.output1D',
                             prefix + '_' + str(i).zfill(3) + '_JNT.rotateX')

        cmds.createNode('curveInfo', n=(prefix + '_000_CIN'))
        cmds.connectAttr(curve_shape + '.worldSpace', prefix + '_000_CIN.inputCurve')
        cmds.createNode('multiplyDivide', n=(prefix + '_SquashStretch000_MDN'))
        cmds.setAttr(prefix + '_SquashStretch000_MDN.operation', 2)
        cmds.connectAttr(prefix + '_000_CIN.arcLength',
                         prefix + '_SquashStretch000_MDN.input1.input1X')
        stretchInfo = cmds.getAttr(prefix + '_SquashStretch000_MDN.input1X')
        cmds.setAttr(prefix + '_SquashStretch000_MDN.input2X', stretchInfo)

        for i in range(0, pointNumber):
            cmds.connectAttr(prefix + '_SquashStretch000_MDN.outputX',
                             prefix + '_' + str(i).zfill(3) + '_FK.scaleX')

        for i in range(0, pointNumber):
            cmds.spaceLocator(n='folliclePos' + str(i).zfill(3) + '_LOC')
            cmds.parentConstraint(prefix + '_' + str(i).zfill(3) + '_FK',
                                  'folliclePos' + str(i).zfill(3) + '_LOC')

        for i in range(0, pointNumber):
            cpos = cmds.createNode('closestPointOnSurface',
                                   n='folliclePos' + str(i).zfill(3) + '_CPOS')
            cmds.connectAttr('folliclePos' + str(i).zfill(3) + '_LOC.translate',
                             cpos + '.inPosition')
            cmds.connectAttr(prefix + '_001_GEOShape.worldSpace', cpos + '.inputSurface')

        for i in range(0, pointNumber):
            fol_shape = prefix + '_Joint_' + str(i).zfill(3) + '_FOLShape'
            fol_xform = prefix + '_Joint_' + str(i).zfill(3) + '_FOL'
            cpos_name = 'folliclePos' + str(i).zfill(3) + '_CPOS'

            cmds.createNode('follicle', n=fol_shape)
            cmds.connectAttr(prefix + '_001_GEOShape.worldMatrix',
                             fol_shape + '.inputWorldMatrix')
            cmds.connectAttr(prefix + '_001_GEOShape.local', fol_xform + '.inputSurface')
            cmds.connectAttr(fol_shape + '.outTranslate', fol_xform + '.translate')
            cmds.connectAttr(fol_shape + '.outRotate', fol_xform + '.rotate')

            for axis in ['translateX', 'translateY', 'translateZ',
                         'rotateX', 'rotateY', 'rotateZ']:
                cmds.setAttr(fol_xform + '.' + axis, lock=True)

            cmds.connectAttr(cpos_name + '.parameterU', fol_xform + '.parameterU')
            cmds.connectAttr(cpos_name + '.parameterV', fol_xform + '.parameterV')
            cmds.disconnectAttr(cpos_name + '.parameterU', fol_xform + '.parameterU')
            cmds.disconnectAttr(cpos_name + '.parameterV', fol_xform + '.parameterV')
            cmds.delete(cpos_name)
            cmds.delete('folliclePos' + str(i).zfill(3) + '_LOC')

        for i in range(0, pointNumber):
            drv = cmds.joint(n=(prefix + '_Joint_' + str(i).zfill(3) + '_DRV'))
            cmds.parent(drv, prefix + '_Joint_' + str(i).zfill(3) + '_FOL')
            for axis in ['translateX', 'translateY', 'translateZ',
                         'rotateX', 'rotateY', 'rotateZ']:
                cmds.setAttr(drv + '.' + axis, 0)

        cmds.skinCluster(prefix + '_Geo000_FK', prefix + '_Geo002_FK',
                         prefix + '_000_GEO', dr=4.5, n=prefix + '_Geo000_SKN')
        cmds.skinCluster(prefix + '_Geo000_FK', prefix + '_Geo002_FK', prefix + '_Geo001_FK',
                         prefix + '_001_GEO', dr=4.5, n=prefix + '_Geo001_SKN')

        driverJoints = cmds.ls(prefix + '_Joint*_DRV')
        cmds.skinCluster(driverJoints, prefix, n=prefix + '_Crv000_SKN')

        cmds.rename(prefix, prefix + '_000_CRV')

        lengthOfCurve = cmds.getAttr(prefix + '_SquashStretch000_MDN.input2X')
        rotationAmount = 90

        topTX = prefix + '_002_CTL.tx'
        topRZ = prefix + '_002_CTL.rz'
        btmTX = prefix + '_000_CTL.tx'
        btmRZ = prefix + '_000_CTL.rz'
        midTopTranslateSDK  = prefix + '_CTL001_TopSDK_GRP.rz'
        midTopRotateSDK     = prefix + '_CTL001_TopRotateSDK_GRP.rz'
        midBtmTranslateSDK  = prefix + '_CTL001_BtmSDK_GRP.rz'
        midBtmRotateSDK     = prefix + '_CTL001_BtmRotateSDK_GRP.rz'

        for driver, driven, val_pairs in [
            (topTX, midTopTranslateSDK,
             [(lengthOfCurve, -rotationAmount), (-lengthOfCurve, rotationAmount), (0, 0)]),
            (topRZ, midTopRotateSDK,
             [(rotationAmount, -rotationAmount), (-rotationAmount, rotationAmount), (0, 0)]),
            (btmRZ, midBtmRotateSDK,
             [(rotationAmount, -rotationAmount), (-rotationAmount, rotationAmount), (0, 0)]),
            (btmTX, midBtmTranslateSDK,
             [(lengthOfCurve, rotationAmount), (-lengthOfCurve, -rotationAmount), (0, 0)]),
        ]:
            for dv, dv_val in val_pairs:
                cmds.setAttr(driver, dv)
                cmds.setAttr(driven, dv_val)
                cmds.setDrivenKeyframe(driven, cd=driver)

        theJoints = list(range(pointNumber))
        theJointsLength = float(len(theJoints)) - 1
        half = len(theJoints) // 2

        for aJoint in theJoints:
            MDN = prefix + '_Twist' + str(aJoint).zfill(3) + '_MDN'
            cmds.setAttr(MDN + '.input2Z', 1 - float(aJoint) / theJointsLength)
            cmds.setAttr(MDN + '.input2X', float(aJoint) / theJointsLength)

        for aJoint in theJoints[:half + 1]:
            MDN = prefix + '_Twist' + str(aJoint).zfill(3) + '_MDN'
            cmds.setAttr(MDN + '.input2Y', 2 * (float(aJoint) / theJointsLength))

        for aJoint in theJoints[half + 1:]:
            MDN = prefix + '_Twist' + str(aJoint).zfill(3) + '_MDN'
            cmds.setAttr(MDN + '.input2Y', 2 * (1 - float(aJoint) / theJointsLength))

        cmds.group(em=True, name=(prefix + '_All000_GRP'))
        cmds.group(em=True, name=(prefix + '_All001_GRP'))
        cmds.group(em=True, name=(prefix + '_All002_GRP'))

        all000_ctl = cmds.curve(name=(prefix + '_All000_CTL'), degree=3,
                   point=[(-2.587e-15, 5.448e-36, 8.4899356232051044),
                          (4.086088758749157, 5.448e-36, 4.8693000688131338),
                          (6.8101479312486024, 5.448e-36, 1.2486645144211457),
                          (5.4481183449988837, 5.448e-36, -3.9998118128096531),
                          (2.587e-15, 5.448e-36, -6.7238709853090981),
                          (-5.4481183449988766, 5.448e-36, -3.9998118128096594),
                          (-6.8101479312485997, 5.448e-36, 1.248664514421141),
                          (-4.0860887587491641, 5.448e-36, 4.8693000688131205),
                          (-1.724e-15, 2.041e-32, 8.4899356232051044)])
        cmds.addAttr(longName='subControlOneVisibility', keyable=True, min=0, max=1,
                     attributeType='long')
        cmds.addAttr(longName='subControlTwoVisibility', keyable=True, min=0, max=1,
                     attributeType='long')
        cmds.rename(cmds.listRelatives(all000_ctl, shapes=True)[0], prefix + '_All000_CTLShape')
        cmds.setAttr(prefix + '_All000_CTL.subControlOneVisibility', keyable=False, channelBox=True)
        cmds.setAttr(prefix + '_All000_CTL.subControlTwoVisibility', keyable=False, channelBox=True)

        all001_ctl = cmds.curve(name=(prefix + '_All001_CTL'), degree=3,
                   point=[(-2.412e-15, 4.223e-35, 7.9372176682272988),
                          (3.8185271911283234, 4.223e-35, 4.5536652958006165),
                          (6.3642119852138777, 4.223e-35, 1.170112923373918),
                          (5.0913695881711041, 4.223e-35, -3.7346874250304691),
                          (2.423e-15, 4.223e-35, -6.2803722191160229),
                          (-5.091369588171097, 4.223e-35, -3.7346874250304749),
                          (-6.364211985213875, 4.223e-35, 1.1701129233739136),
                          (-3.8185271911283292, 4.223e-35, 4.553665295800605),
                          (-1.606e-15, 1.911e-32, 7.9372176682272988)])
        cmds.rename(cmds.listRelatives(all001_ctl, shapes=True)[0], prefix + '_All001_CTLShape')

        all002_ctl = cmds.curve(name=(prefix + '_All002_CTL'), degree=3,
                   point=[(-2.195e-15, 8.120e-35, 7.246874953712628),
                          (3.4846338500471794, 8.120e-35, 4.1591815734589863),
                          (5.80772308341197, 8.120e-35, 1.0714881932053306),
                          (4.6461784667295767, 8.120e-35, -3.4044347127470127),
                          (2.217e-15, 8.120e-35, -5.7275239461118046),
                          (-4.6461784667295722, 8.120e-35, -3.404434712747018),
                          (-5.8077230834119673, 8.120e-35, 1.0714881932053264),
                          (-3.4846338500471838, 8.120e-35, 4.1591815734589765),
                          (-1.460e-15, 1.748e-32, 7.246874953712628)])
        cmds.rename(cmds.listRelatives(all002_ctl, shapes=True)[0], prefix + '_All002_CTLShape')

        cmds.parent(prefix + '_All000_CTL', prefix + '_All000_GRP')
        cmds.parent(prefix + '_All001_CTL', prefix + '_All001_GRP')
        cmds.parent(prefix + '_All002_CTL', prefix + '_All002_GRP')
        pc = cmds.parentConstraint(prefix + '_000_CTL', prefix + '_All000_GRP')[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_All000_CTL', prefix + '_All001_GRP')
        cmds.parentConstraint(prefix + '_All001_CTL', prefix + '_All002_GRP')
        cmds.group(em=True, name=(prefix + '_NoTransform000_GRP'))

        cmds.connectAttr(prefix + '_All000_CTL.subControlOneVisibility',
                         prefix + '_All001_CTL.visibility')
        cmds.connectAttr(prefix + '_All000_CTL.subControlTwoVisibility',
                         prefix + '_All002_CTL.visibility')

        cmds.parent(prefix + '_000_FK', prefix + '_All000_GRP')
        cmds.parent(prefix + '_000_IKH', prefix + '_All000_GRP')

        cmds.parent(prefix + '_000_CRV', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_000_GEO', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_001_GEO', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_Geo000_GRP', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_Geo001_GRP', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_Geo002_GRP', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_Mid000_FOL', prefix + '_NoTransform000_GRP')

        cmds.select(prefix + '_Joint*_FOL')
        for fol in cmds.ls(sl=True):
            cmds.parent(fol, prefix + '_NoTransform000_GRP')

        cmds.group(em=True, name=(prefix + '_Master000_GRP'))
        cmds.parent(prefix + '_NoTransform000_GRP', prefix + '_Master000_GRP')
        cmds.parent(prefix + '_All000_GRP', prefix + '_Master000_GRP')

        cmds.parentConstraint(prefix + '_All002_CTL', prefix + '_CTL000_GRP')
        cmds.group(em=True, name=prefix + '_CTL002constraint_GRP')
        pc = cmds.parentConstraint(prefix + '_002_CTL', prefix + '_CTL002constraint_GRP')[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_CTL002constraint_GRP', prefix + '_CTL002_GRP')
        cmds.parent(prefix + '_CTL002constraint_GRP', prefix + '_All002_CTL')
        cmds.parent(prefix + '_000_IKH', prefix + '_All000_CTL')
        cmds.parent(prefix + '_000_FK', prefix + '_All000_CTL')

        cmds.createNode('multiplyDivide', n=prefix + '_GlobalScale000_MDN')
        arcLen = cmds.getAttr(prefix + '_000_CIN.arcLength')
        cmds.setAttr(prefix + '_GlobalScale000_MDN.input1X', arcLen)
        cmds.select(prefix + '_All000_CTL', r=True)
        cmds.addAttr(prefix + '_All000_CTL', longName='globalScale', defaultValue=1, keyable=True)
        cmds.connectAttr(prefix + '_All000_CTL.globalScale',
                         prefix + '_GlobalScale000_MDN.input2X')
        cmds.connectAttr(prefix + '_GlobalScale000_MDN.outputX',
                         prefix + '_SquashStretch000_MDN.input2X')

        scale_targets = (
            [prefix + '_All000_GRP', prefix + '_All001_GRP', prefix + '_All002_GRP',
             prefix + '_Mid000_FOL', prefix + '_Geo000_FK', prefix + '_Geo001_FK',
             prefix + '_Geo002_FK', prefix + '_CTL000_GRP', prefix + '_CTL002_GRP'] +
            [prefix + '_Joint_' + str(i).zfill(3) + '_FOL' for i in range(pointNumber)]
        )
        for node in scale_targets:
            for axis in ['scaleX', 'scaleY', 'scaleZ']:
                cmds.connectAttr(prefix + '_All000_CTL.globalScale', node + '.' + axis)

        cmds.setAttr(prefix + '_All000_CTL.scaleX', lock=True, keyable=False)
        cmds.setAttr(prefix + '_All000_CTL.scaleY', lock=True, keyable=False)
        cmds.setAttr(prefix + '_All000_CTL.scaleZ', lock=True, keyable=False)

        cmds.createNode('addDoubleLinear', n=prefix + 'ExtraTwist000_ADL')
        cmds.createNode('addDoubleLinear', n=prefix + 'ExtraTwist002_ADL')
        cmds.connectAttr(prefix + '_000_CTL.rotateY', prefix + 'ExtraTwist000_ADL.input1')
        cmds.connectAttr(prefix + '_002_CTL.rotateY', prefix + 'ExtraTwist002_ADL.input1')
        cmds.connectAttr(prefix + 'ExtraTwist000_ADL.output', prefix + '_000_CTL.twist')
        cmds.connectAttr(prefix + 'ExtraTwist002_ADL.output', prefix + '_002_CTL.twist')

        spineCRVdegree = cmds.getAttr(prefix + '_000_CRV.degree')
        spineCRVspans = cmds.getAttr(prefix + '_000_CRV.spans')
        totalSpineJoints = spineCRVdegree + spineCRVspans

        for i in range(0, totalSpineJoints):
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_JNT.jointOrient', 0, 0, 0)

        for i in range(0, totalSpineJoints):
            cmds.select(clear=True)
            cmds.joint(name=prefix + '_' + str(i).zfill(3) + '_SKL')
            pc = cmds.parentConstraint(prefix + '_' + str(i).zfill(3) + '_JNT',
                                       prefix + '_' + str(i).zfill(3) + '_SKL')[0]
            cmds.delete(pc)
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_SKL.rotate', 0, 0, 0)
            cmds.parentConstraint(prefix + '_' + str(i).zfill(3) + '_JNT',
                                  prefix + '_' + str(i).zfill(3) + '_SKL')

        for i in range(0, totalSpineJoints - 1):
            cmds.parent(prefix + '_' + str(i + 1).zfill(3) + '_SKL',
                        prefix + '_' + str(i).zfill(3) + '_SKL')

        for i in range(0, totalSpineJoints - 2):
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_SKL.jointOrient', 0, 0, 0)
            jX = cmds.getAttr(prefix + '_' + str(i).zfill(3) + '_SKL.rotateX')
            jY = cmds.getAttr(prefix + '_' + str(i).zfill(3) + '_SKL.rotateY')
            jZ = cmds.getAttr(prefix + '_' + str(i).zfill(3) + '_SKL.rotateZ')
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_SKL.jointOrientX', jX)
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_SKL.jointOrientY', jY)
            cmds.setAttr(prefix + '_' + str(i).zfill(3) + '_SKL.jointOrientZ', jZ)

        cmds.setAttr(prefix + '_' + str(totalSpineJoints - 1).zfill(3) + '_SKL.jointOrient',
                     0, 0, 0)
        cmds.setAttr(prefix + '_002_CTL.rotateOrder', 4)

        cmds.rename(prefix + '_All000_CTL', prefix + 'COG_CTL')
        cmds.rename(prefix + '_All001_CTL', prefix + 'COG_Mid_CTL')
        cmds.rename(prefix + '_All002_CTL', prefix + 'COG_Btm_CTL')
        cmds.rename(prefix + '_000_CTL', prefix + 'Btm_CTL')
        cmds.rename(prefix + '_001_CTL', prefix + 'Mid_CTL')
        cmds.rename(prefix + '_002_CTL', prefix + 'Top_CTL')

        cmds.parent(prefix + '_All000_GRP', prefix + '_NoTransform000_GRP')
        cmds.parent(prefix + '_NoTransform000_GRP', world=True)
        cmds.group(em=True, name=prefix + '_Controls_GRP')
        cmds.parent(prefix + '_CTL000_GRP', prefix + '_CTL002_GRP',
                    prefix + '_All001_GRP', prefix + '_All002_GRP',
                    prefix + '_All000_GRP', prefix + '_Controls_GRP')
        cmds.parent(prefix + '_Controls_GRP', prefix + '_NoTransform000_GRP')
        cmds.delete(prefix + '_Master000_GRP')

        cmds.group(em=True, name=prefix + '_Rig_GRP')
        cmds.parent(prefix + '_Rig_GRP', prefix + '_NoTransform000_GRP')

        cmds.select(prefix + '_Joint*_FOL', prefix + '_Mid*_FOL')
        for fol in cmds.ls(sl=True):
            cmds.parent(fol, prefix + '_Rig_GRP')

        cmds.select(prefix + '_Geo*_GRP')
        for grp in cmds.ls(sl=True):
            cmds.parent(grp, prefix + '_Rig_GRP')

        cmds.parent(prefix + '_000_GEO', prefix + '_001_GEO', prefix + '_000_CRV',
                    prefix + '_Rig_GRP')

        for shape in [prefix + 'COG_CTLShape', prefix + 'COG_Mid_CTLShape',
                      prefix + 'COG_Btm_CTLShape', prefix + 'Btm_CTLShape',
                      prefix + 'Mid_CTLShape', prefix + 'Top_CTLShape']:
            cmds.setAttr(shape + '.overrideEnabled', 1)
            cmds.setAttr(shape + '.overrideColor', 22)

        cmds.select(clear=True)

    finally:
        cmds.keyTangent(itt=currentIntangent[0], g=True)
        cmds.keyTangent(ott=currentOutTangent[0], g=True)


def hideTorso(prefix):
    degree = cmds.getAttr(prefix + '_000_CRV.degree')
    span = cmds.getAttr(prefix + '_000_CRV.spans')
    pointNumber = degree + span

    lk = {'lock': True, 'keyable': False}
    for ctl, attrs in [
        (prefix + 'COG_CTL',     ['visibility', 'scaleX', 'scaleY', 'scaleZ']),
        (prefix + 'COG_Mid_CTL', ['visibility', 'scaleX', 'scaleY', 'scaleZ']),
        (prefix + 'COG_Btm_CTL', ['visibility', 'scaleX', 'scaleY', 'scaleZ']),
        (prefix + 'Btm_CTL',     ['twist', 'visibility', 'scaleX', 'scaleY', 'scaleZ']),
        (prefix + 'Mid_CTL',     ['visibility', 'scaleX', 'scaleY', 'scaleZ']),
        (prefix + 'Top_CTL',     ['twist', 'visibility', 'scaleX', 'scaleY', 'scaleZ']),
    ]:
        for attr in attrs:
            cmds.setAttr(ctl + '.' + attr, **lk)

    for node in [prefix + '_000_FK', prefix + '_000_GEO', prefix + '_001_GEO',
                 prefix + '_000_CRV', prefix + '_000_IKH', prefix + '_Geo000_FK',
                 prefix + '_Geo001_FK', prefix + '_Geo002_FK']:
        cmds.setAttr(node + '.visibility', 0)

    cmds.setAttr(prefix + '_Mid000_FOLShape.visibility', 0)

    for i in range(0, pointNumber):
        cmds.setAttr(prefix + '_Joint_' + str(i).zfill(3) + '_FOL.visibility', 0)


def addTip(prefix, tip_crv):
    """
    Append FK tip controls to the top of an existing spine rig and extend its
    SKL chain continuously to the tip.

    tip_crv: a NURBS curve drawn above the spine whose CVs define the tip
    control positions and count. The curve is hidden and parented into the rig
    after sampling.

    Each CV becomes one tip CTL. Controls are daisy-chain parentConstrained
    (first GRP to {prefix}Top_CTL, each subsequent GRP to the previous CTL).
    The spine SKL chain is extended in-place from its last joint — no separate
    tip SKL chain — giving one continuous chain from rig base to tip end.
    """
    top_ctl = prefix + 'Top_CTL'
    no_xf_grp = prefix + '_NoTransform000_GRP'

    if not cmds.objExists(top_ctl):
        raise RuntimeError('Spine Top_CTL not found: ' + top_ctl)
    if not cmds.objExists(no_xf_grp):
        raise RuntimeError('Spine NoTransform GRP not found: ' + no_xf_grp)
    if not cmds.objExists(tip_crv):
        raise RuntimeError('Tip curve not found: ' + tip_crv)

    tip_grp = prefix + '_TipRig_GRP'
    if cmds.objExists(tip_grp):
        raise RuntimeError('Tip rig already exists: ' + tip_grp)

    crv_shapes = cmds.listRelatives(tip_crv, shapes=True, noIntermediate=True) or []
    if not crv_shapes or cmds.nodeType(crv_shapes[0]) != 'nurbsCurve':
        raise RuntimeError(tip_crv + ' is not a NURBS curve')

    # Sample CV positions — same pattern as buildSpine
    degree = cmds.getAttr(tip_crv + '.degree')
    spans = cmds.getAttr(tip_crv + '.spans')
    tip_count = degree + spans
    points = cmds.getAttr(tip_crv + '.cv[0:' + str(tip_count) + ']')

    # Find last spine SKL by counting JNT joints
    jnt_list = sorted(cmds.ls(prefix + '_*_JNT', type='joint') or [])
    if not jnt_list:
        raise RuntimeError('No spine JNT joints found for prefix: ' + prefix)
    last_spine_skl = prefix + '_' + str(len(jnt_list) - 1).zfill(3) + '_SKL'
    if not cmds.objExists(last_spine_skl):
        raise RuntimeError('Last spine SKL not found: ' + last_spine_skl)
    next_skl_idx = len(jnt_list)

    # Container group for the tip CTL chain
    cmds.group(em=True, name=tip_grp)
    cmds.parent(tip_grp, no_xf_grp)
    cog_ctl = prefix + 'COG_CTL'
    for axis in ['scaleX', 'scaleY', 'scaleZ']:
        cmds.connectAttr(cog_ctl + '.globalScale', tip_grp + '.' + axis)

    # Hide and store the tip curve inside the rig
    cmds.parent(tip_crv, tip_grp)
    cmds.setAttr(tip_crv + '.visibility', 0)

    # ── CTL daisy-chain at CV positions ───────────────────────────────────
    # Skip CV[0] — it overlaps with the spine Top_CTL/last SKL.
    prev_driver = top_ctl
    ctl_names = []
    for i in range(1, tip_count):
        idx = str(i).zfill(3)
        grp = prefix + '_Tip_' + idx + '_GRP'
        ctl = prefix + '_Tip_' + idx + '_CTL'
        cv_pos = (points[i][0], points[i][1], points[i][2])

        cmds.group(em=True, name=grp)
        cmds.parent(grp, tip_grp)
        # Position at CV, match orientation to driver, then constrain with offset
        cmds.xform(grp, ws=True, t=cv_pos)
        oc = cmds.orientConstraint(prev_driver, grp, mo=False)[0]
        cmds.delete(oc)
        cmds.setAttr(grp + '.rotateOrder', 4)
        cmds.addAttr(grp, longName='twist', at='double', keyable=False)
        cmds.setAttr(grp + '.twist', lock=True)
        for attr in ('.v', '.sx', '.sy', '.sz'):
            cmds.setAttr(grp + attr, lock=True, keyable=False)
        cmds.parentConstraint(prev_driver, grp, mo=True)

        cmds.select(clear=True)
        cmds.circle(radius=2, nr=(0, 1, 0), c=(0, 0, 0), name=ctl, ch=False)
        cmds.parent(ctl, grp)
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotateOrder', 4)
        cmds.addAttr(ctl, longName='twist', at='double', keyable=True)
        for attr in ('.v', '.sx', '.sy', '.sz'):
            cmds.setAttr(ctl + attr, lock=True, keyable=False)
        ctl_shape = cmds.listRelatives(ctl, shapes=True)[0]
        cmds.setAttr(ctl_shape + '.overrideEnabled', 1)
        cmds.setAttr(ctl_shape + '.overrideColor', 22)

        ctl_names.append(ctl)
        prev_driver = ctl

    # ── Extend spine SKL chain ────────────────────────────────────────────
    new_skl_names = []
    for i in range(tip_count - 1):
        cmds.select(clear=True)
        skl = prefix + '_' + str(next_skl_idx + i).zfill(3) + '_SKL'
        cmds.joint(name=skl)
        new_skl_names.append(skl)

    # Parent as a chain continuing from the last spine SKL
    cmds.parent(new_skl_names[0], last_spine_skl)
    for i in range(1, len(new_skl_names)):
        cmds.parent(new_skl_names[i], new_skl_names[i - 1])

    # Constrain each new SKL to its matching tip CTL
    for i, ctl in enumerate(ctl_names):
        skl = new_skl_names[i]
        pc = cmds.parentConstraint(ctl, skl)[0]
        cmds.delete(pc)
        cmds.setAttr(skl + '.rotate', 0, 0, 0)
        cmds.parentConstraint(ctl, skl)

    cmds.select(clear=True)


def addFK(prefix):
    """
    Build a daisy-chain FK rig that blends with the spine rig on the SKL joints.

    Duplicates the SKL chain as _FKJNT joints (suffix is _FKJNT rather than _FK
    because _FK is already used by the IK spline joints). Daisy-chains circle
    CTLs using the same structure as the tip rig, then adds a second
    parentConstraint target on each SKL joint alongside the existing JNT
    constraint. A FK_IK attribute on COG_CTL (0 = full IK, 1 = full FK) drives
    the blend via one MDN + PMA wired to each constraint's weight attributes.
    """
    cog_ctl = prefix + 'COG_CTL'
    btm_ctl = prefix + 'Btm_CTL'
    no_xf_grp = prefix + '_NoTransform000_GRP'
    fk_grp_name = prefix + '_FK_GRP'

    for node in [cog_ctl, no_xf_grp]:
        if not cmds.objExists(node):
            raise RuntimeError('Expected node not found: ' + node)
    if cmds.objExists(fk_grp_name):
        raise RuntimeError('FK rig already exists: ' + fk_grp_name)

    skl_joints = sorted(cmds.ls(prefix + '_*_SKL', type='joint') or [])
    if not skl_joints:
        raise RuntimeError('No SKL joints found for prefix: ' + prefix)
    count = len(skl_joints)

    # Container group parented under NoTransform, scaled with rig
    cmds.group(em=True, name=fk_grp_name)
    cmds.parent(fk_grp_name, no_xf_grp)
    for axis in ['scaleX', 'scaleY', 'scaleZ']:
        cmds.connectAttr(cog_ctl + '.globalScale', fk_grp_name + '.' + axis)

    # ── FK joint chain ─────────────────────────────────────────────────────
    fk_joints = []
    for i, skl in enumerate(skl_joints):
        idx = str(i).zfill(3)
        fk_jnt = prefix + '_' + idx + '_FKJNT'
        cmds.select(clear=True)
        cmds.joint(name=fk_jnt)
        pc = cmds.parentConstraint(skl, fk_jnt, mo=False)[0]
        cmds.delete(pc)
        cmds.setAttr(fk_jnt + '.rotate', 0, 0, 0)
        for attr in ('jointOrientX', 'jointOrientY', 'jointOrientZ'):
            cmds.setAttr(fk_jnt + '.' + attr, cmds.getAttr(skl + '.' + attr))
        fk_joints.append(fk_jnt)

    cmds.parent(fk_joints[0], fk_grp_name)
    for i in range(1, count):
        cmds.parent(fk_joints[i], fk_joints[i - 1])

    # ── CTL daisy chain (mirrors tip rig structure) ────────────────────────
    prev_driver = btm_ctl if cmds.objExists(btm_ctl) else None
    ctl_names = []
    for i, skl in enumerate(skl_joints):
        idx = str(i).zfill(3)
        grp = prefix + '_FK_' + idx + '_GRP'
        ctl = prefix + '_FK_' + idx + '_CTL'

        cmds.group(em=True, name=grp)
        cmds.parent(grp, fk_grp_name)
        pc = cmds.parentConstraint(skl, grp, mo=False)[0]
        cmds.delete(pc)
        cmds.setAttr(grp + '.rotateOrder', 4)
        cmds.addAttr(grp, longName='twist', at='double', keyable=False)
        cmds.setAttr(grp + '.twist', lock=True)
        for attr in ('.v', '.sx', '.sy', '.sz'):
            cmds.setAttr(grp + attr, lock=True, keyable=False)
        if prev_driver:
            cmds.parentConstraint(prev_driver, grp, mo=True)

        cmds.select(clear=True)
        cmds.circle(radius=4, nr=(0, 1, 0), c=(0, 0, 0), name=ctl, ch=False)
        cmds.rotate(0, 0, 90, ctl + '.cv[*]', relative=True, objectSpace=True)
        cmds.parent(ctl, grp)
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotateOrder', 4)
        cmds.addAttr(ctl, longName='twist', at='double', keyable=True)
        for attr in ('.v', '.sx', '.sy', '.sz'):
            cmds.setAttr(ctl + attr, lock=True, keyable=False)
        ctl_shape = cmds.listRelatives(ctl, shapes=True)[0]
        cmds.setAttr(ctl_shape + '.overrideEnabled', 1)
        cmds.setAttr(ctl_shape + '.overrideColor', 18)

        cmds.parentConstraint(ctl, fk_joints[i])

        ctl_names.append(ctl)
        prev_driver = ctl

    # ── FK_IK attr on COG_CTL ──────────────────────────────────────────────
    if not cmds.attributeQuery('FK_IK', node=cog_ctl, exists=True):
        cmds.addAttr(cog_ctl, longName='FK_IK', attributeType='float',
                     min=0, max=1, defaultValue=0, keyable=True)

    # ── MDN: outputX = FK_IK (FK weight), outputY = -FK_IK ───────────────
    mdn = cmds.createNode('multiplyDivide', name=prefix + '_FKIK_MDN')
    cmds.setAttr(mdn + '.operation', 1)
    cmds.setAttr(mdn + '.input1X', 1.0)
    cmds.connectAttr(cog_ctl + '.FK_IK', mdn + '.input2X')
    cmds.setAttr(mdn + '.input1Y', -1.0)
    cmds.connectAttr(cog_ctl + '.FK_IK', mdn + '.input2Y')

    # ── PMA: 1 + (-FK_IK) = 1 - FK_IK (IK weight) ────────────────────────
    pma = cmds.createNode('plusMinusAverage', name=prefix + '_FKIK_PMA')
    cmds.setAttr(pma + '.operation', 1)
    cmds.setAttr(pma + '.input1D[0]', 1.0)
    cmds.connectAttr(mdn + '.outputY', pma + '.input1D[1]')

    # ── Add FK constraint to each SKL, wire both weights ──────────────────
    for i, skl in enumerate(skl_joints):
        cmds.parentConstraint(fk_joints[i], skl, mo=True)

        pc_node = (cmds.listRelatives(skl, children=True,
                                      type='parentConstraint') or [None])[0]
        if not pc_node:
            continue

        weight_list = cmds.parentConstraint(pc_node, query=True,
                                             weightAliasList=True) or []
        if len(weight_list) < 2:
            continue

        # weight_list[0] = existing JNT (IK) weight, [1] = new FKJNT (FK) weight
        cmds.connectAttr(pma + '.output1D', pc_node + '.' + weight_list[0], force=True)
        cmds.connectAttr(mdn + '.outputX', pc_node + '.' + weight_list[1], force=True)

    # ── Visibility: FK_GRP on when FK_IK=1, spine CTLs on when FK_IK=0 ───
    cmds.connectAttr(mdn + '.outputX', fk_grp_name + '.visibility')
    for spine_ctl in [prefix + 'Btm_CTL', prefix + 'Mid_CTL', prefix + 'Top_CTL']:
        if cmds.objExists(spine_ctl):
            cmds.setAttr(spine_ctl + '.visibility', lock=False)
            cmds.connectAttr(pma + '.output1D', spine_ctl + '.visibility', force=True)

    cmds.select(clear=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _spine_preview(spans, w=100, h=20):
    px = QtGui.QPixmap(w, h)
    px.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pad_x, pad_y = 1, 2
    rect = QtCore.QRectF(pad_x, pad_y, w - 2 * pad_x, h - 2 * pad_y)
    p.setBrush(QtGui.QColor(72, 72, 72))
    p.setPen(QtCore.Qt.PenStyle.NoPen)
    p.drawRoundedRect(rect, 2, 2)
    p.setPen(QtGui.QPen(QtGui.QColor(160, 160, 160), 1.0))
    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect, 2, 2)
    p.setPen(QtGui.QPen(QtGui.QColor(140, 140, 140), 0.8))
    seg = rect.width() / spans
    for i in range(1, spans):
        x = rect.left() + i * seg
        p.drawLine(QtCore.QPointF(x, rect.top() + 1),
                   QtCore.QPointF(x, rect.bottom() - 1))
    p.end()
    return px


# ── UI ────────────────────────────────────────────────────────────────────────

class SpineRigUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ps_spine')
        self.setMinimumWidth(320)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window |
            QtCore.Qt.WindowType.WindowCloseButtonHint
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QtWidgets.QLabel('ps_spine')
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 14px; font-weight: bold; padding: 4px 0px;')
        layout.addWidget(title)

        layout.addWidget(_separator())

        # Draw button
        draw_btn = QtWidgets.QPushButton('Draw Curve')
        draw_btn.clicked.connect(self._draw_curve)
        layout.addWidget(draw_btn)

        layout.addWidget(_separator())

        # Surface fidelity — radio buttons with spine segment preview
        fidelity_box = QtWidgets.QGroupBox('Surface Fidelity')
        fidelity_layout = QtWidgets.QVBoxLayout(fidelity_box)
        fidelity_layout.setSpacing(6)
        self._fidelity_group = QtWidgets.QButtonGroup(self)
        for spans in (3, 5, 7, 9):
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            rb = QtWidgets.QRadioButton(str(spans))
            if spans == 3:
                rb.setChecked(True)
            self._fidelity_group.addButton(rb, spans)
            preview = QtWidgets.QLabel()
            preview.setPixmap(_spine_preview(spans))
            row.addWidget(rb)
            row.addWidget(preview)
            row.addStretch()
            fidelity_layout.addLayout(row)
        layout.addWidget(fidelity_box)

        layout.addWidget(_separator())

        # Build button
        build_btn = QtWidgets.QPushButton('Build Rig')
        build_btn.setMinimumHeight(36)
        build_btn.clicked.connect(self._build)
        layout.addWidget(build_btn)

        layout.addWidget(_separator())

        # Add FK section
        fk_box = QtWidgets.QGroupBox('Add FK')
        fk_layout = QtWidgets.QVBoxLayout(fk_box)
        fk_layout.setSpacing(6)
        fk_note = QtWidgets.QLabel(
            'Select the rig\'s COG_CTL then click Add FK Rig.\n'
            'FK_IK = 0 → spine rig, FK_IK = 1 → FK.'
        )
        fk_note.setWordWrap(True)
        fk_layout.addWidget(fk_note)
        fk_btn = QtWidgets.QPushButton('Add FK Rig')
        fk_btn.clicked.connect(self._add_fk)
        fk_layout.addWidget(fk_btn)
        layout.addWidget(fk_box)

        layout.addWidget(_separator())

        # Add Tip section
        tip_box = QtWidgets.QGroupBox('Add Tip')
        tip_layout = QtWidgets.QVBoxLayout(tip_box)
        tip_layout.setSpacing(6)

        tip_btn = QtWidgets.QPushButton('Add Tip To Rig')
        tip_btn.clicked.connect(self._add_tip)
        tip_layout.addWidget(tip_btn)

        layout.addWidget(tip_box)

        layout.addWidget(_separator())

        # Log
        log_box = QtWidgets.QGroupBox('Log')
        log_layout = QtWidgets.QVBoxLayout(log_box)
        self._log = QtWidgets.QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        self._log.setFont(QtGui.QFont('Courier New', 9))
        log_layout.addWidget(self._log)
        layout.addWidget(log_box)

    def _log_msg(self, msg):
        self._log.appendPlainText(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def _draw_curve(self):
        mel.eval('CVCurveTool')

    def _build(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('ERROR: Select the spine curve before building.')
            return

        prefix = sel[0]
        shapes = cmds.listRelatives(prefix, shapes=True, noIntermediate=True) or []
        if not shapes or cmds.objectType(shapes[0]) != 'nurbsCurve':
            self._log_msg(f'ERROR: "{prefix}" is not a NURBS curve.')
            return

        spans = self._fidelity_group.checkedId()
        self._log_msg(f'Building "{prefix}" ({spans} spans)...')

        try:
            buildSpine(prefix, surface_spans=spans)
            hideTorso(prefix)
            self._log_msg(f'Done — "{prefix}" spine rig built.')
            cmds.inViewMessage(
                amg=f'<b>{prefix}</b> spine rig built.',
                pos='midCenter', fade=True
            )
        except Exception as e:
            self._log_msg(f'ERROR: {e}')

    def _add_tip(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('ERROR: Select the tip curve before adding.')
            return
        tip_crv = sel[0]
        shapes = cmds.listRelatives(tip_crv, shapes=True, noIntermediate=True) or []
        if not shapes or cmds.objectType(shapes[0]) != 'nurbsCurve':
            self._log_msg(f'ERROR: "{tip_crv}" is not a NURBS curve.')
            return
        prefix = tip_crv
        self._log_msg(f'Adding tip to "{prefix}" from "{tip_crv}"...')
        try:
            addTip(prefix, tip_crv)
            self._log_msg(f'Done — tip rig added to "{prefix}".')
            cmds.inViewMessage(
                amg=f'<b>{prefix}</b> tip rig added.',
                pos='midCenter', fade=True
            )
        except Exception as e:
            self._log_msg(f'ERROR: {e}')

    def _add_fk(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._log_msg('ERROR: Select the COG_CTL before adding FK rig.')
            return
        node = sel[0]
        if not node.endswith('COG_CTL'):
            self._log_msg(f'ERROR: "{node}" does not look like a COG_CTL — '
                          'select the rig\'s COG_CTL and try again.')
            return
        prefix = node[:-len('COG_CTL')]
        self._log_msg(f'Adding FK rig to "{prefix}" — FK joints named _FKJNT '
                      '(suffix _FK is reserved by the IK spline joints)...')
        try:
            addFK(prefix)
            self._log_msg(
                f'Done — FK rig added. Key {node}.FK_IK: 0 = spine rig, 1 = FK.'
            )
            cmds.inViewMessage(
                amg=f'<b>{prefix}</b> FK rig added.',
                pos='midCenter', fade=True
            )
        except Exception as e:
            self._log_msg(f'ERROR: {e}')


def _separator():
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    return line

import maya.cmds as cmds
import maya.mel as mel
from PySide6 import QtWidgets, QtCore
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
    currentIntangent = cmds.keyTangent(query=True, itt=True, g=True)
    currentOutTangent = cmds.keyTangent(query=True, ott=True, g=True)

    try:
        cmds.keyTangent(itt='linear', g=True)
        cmds.keyTangent(ott='linear', g=True)

        cmds.select(prefix)
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
        cmds.delete('curve1')
        cmds.connectAttr(prefix + 'Shape.worldSpace[0]', prefix + '_000_IKH.inCurve')

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
        cmds.pointConstraint(prefix + '_000_EFF', prefix + '_CTL002_GRP', mo=False)
        cmds.delete(prefix + '_CTL002_GRP_pointConstraint1')
        cmds.parentConstraint(prefix + '_002_CTL', prefix + '_Geo002_FK')
        cmds.pointConstraint(prefix + '_000_FK', prefix + '_CTL000_GRP', mo=False)
        cmds.delete(prefix + '_CTL000_GRP_pointConstraint1')
        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo000_FK')

        cmds.spaceLocator(n='up')
        cmds.parent('up', prefix + '_000_FK')
        cmds.setAttr('up.translate', 0, 0, -2)
        cmds.setAttr('up.rotate', 0, 0, 0)
        cmds.aimConstraint(prefix + '_001_FK', prefix + '_CTL000_GRP',
                           aimVector=[0, 1, 0], worldUpType='object', worldUpObject='up')
        cmds.delete(prefix + '_CTL000_GRP_aimConstraint1')

        cmds.parent('up', endJoint)
        cmds.setAttr('up.translate', 0, 0, -2)
        cmds.setAttr('up.rotate', 0, 0, 0)
        cmds.aimConstraint(lastJoint, prefix + '_CTL002_GRP',
                           aimVector=[0, -1, 0], upVector=[0, 0, -1],
                           worldUpType='object', worldUpObject='up')
        cmds.delete(prefix + '_CTL002_GRP_aimConstraint1')
        cmds.delete('up')

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

        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo000_GRP')
        cmds.delete(prefix + '_Geo000_GRP_parentConstraint1')
        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo002_GRP')
        cmds.delete(prefix + '_Geo002_GRP_parentConstraint1')

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
        cmds.connectAttr(prefix + 'Shape.worldSpace', prefix + '_000_CIN.inputCurve')
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
        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_All000_GRP')
        cmds.parentConstraint(prefix + '_All000_CTL', prefix + '_All001_GRP')
        cmds.parentConstraint(prefix + '_All001_CTL', prefix + '_All002_GRP')
        cmds.delete(prefix + '_All000_GRP_parentConstraint1')
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
        cmds.parentConstraint(prefix + '_002_CTL', prefix + '_CTL002constraint_GRP')
        cmds.delete(prefix + '_CTL002constraint_GRP_parentConstraint1')
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
            cmds.parentConstraint(prefix + '_' + str(i).zfill(3) + '_JNT',
                                  prefix + '_' + str(i).zfill(3) + '_SKL')
            cmds.delete(prefix + '_' + str(i).zfill(3) + '_SKL_parentConstraint1')
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

        # Prefix
        prefix_row = QtWidgets.QHBoxLayout()
        prefix_row.addWidget(QtWidgets.QLabel('Prefix:'))
        self._prefix = QtWidgets.QLineEdit('spine')
        prefix_row.addWidget(self._prefix)
        layout.addLayout(prefix_row)

        # Draw button
        draw_btn = QtWidgets.QPushButton('Draw Spine Curve')
        draw_btn.clicked.connect(self._draw_curve)
        layout.addWidget(draw_btn)

        layout.addWidget(_separator())

        # Fidelity slider
        fidelity_header = QtWidgets.QHBoxLayout()
        fidelity_header.addWidget(QtWidgets.QLabel('Surface Fidelity:'))
        fidelity_header.addStretch()
        self._fidelity_label = QtWidgets.QLabel('3 spans')
        fidelity_header.addWidget(self._fidelity_label)
        layout.addLayout(fidelity_header)

        slider_row = QtWidgets.QHBoxLayout()
        slider_row.addWidget(QtWidgets.QLabel('Low'))
        self._fidelity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._fidelity.setMinimum(3)
        self._fidelity.setMaximum(9)
        self._fidelity.setValue(3)
        self._fidelity.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._fidelity.setTickInterval(1)
        self._fidelity.valueChanged.connect(
            lambda v: self._fidelity_label.setText(f'{v} spans')
        )
        slider_row.addWidget(self._fidelity)
        slider_row.addWidget(QtWidgets.QLabel('High'))
        layout.addLayout(slider_row)

        layout.addWidget(_separator())

        # Build button
        build_btn = QtWidgets.QPushButton('Build Rig')
        build_btn.setMinimumHeight(36)
        build_btn.clicked.connect(self._build)
        layout.addWidget(build_btn)

    def _draw_curve(self):
        mel.eval('CVCurveTool')

    def _build(self):
        prefix = self._prefix.text().strip()
        if not prefix:
            QtWidgets.QMessageBox.warning(self, 'ps_spine', 'Please enter a prefix.')
            return

        sel = cmds.ls(sl=True)
        if not sel:
            QtWidgets.QMessageBox.warning(
                self, 'ps_spine',
                'Select the spine curve before building.'
            )
            return

        curve = sel[0]
        shapes = cmds.listRelatives(curve, shapes=True) or []
        if not shapes or cmds.objectType(shapes[0]) != 'nurbsCurve':
            QtWidgets.QMessageBox.warning(
                self, 'ps_spine',
                f'"{curve}" is not a NURBS curve.'
            )
            return

        actual_prefix = cmds.rename(curve, prefix) if curve != prefix else curve
        if actual_prefix != prefix:
            self._prefix.setText(actual_prefix)

        spans = self._fidelity.value()

        try:
            buildSpine(actual_prefix, surface_spans=spans)
            hideTorso(actual_prefix)
            cmds.inViewMessage(
                amg=f'<b>{actual_prefix}</b> spine rig built.',
                pos='midCenter', fade=True
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 'ps_spine',
                f'Build failed:\n{str(e)}'
            )


def _separator():
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    return line

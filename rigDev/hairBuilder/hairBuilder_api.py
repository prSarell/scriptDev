"""hairBuilder_api.py — hair rig builder + 6-step workflow API."""
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

# ── vector helpers ────────────────────────────────────────────────────────────

def _sub(a, b):  return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _add(a, b):  return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def _scale(v, s): return (v[0]*s, v[1]*s, v[2]*s)
def _len(v):     return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
def _norm(v):
    d = _len(v)
    return _scale(v, 1.0/d) if d > 1e-10 else (0.0, 1.0, 0.0)

# ── button 1: build ───────────────────────────────────────────────────────────

def buildHairRig(prefix, surface_spans=3, tip_count=4):
    """Build the full hair rig from a selected NURBS curve named *prefix*."""
    currentIT = cmds.keyTangent(query=True, itt=True, g=True)
    currentOT = cmds.keyTangent(query=True, ott=True, g=True)
    try:
        cmds.keyTangent(itt='linear', g=True)
        cmds.keyTangent(ott='linear', g=True)

        # ── curve ────────────────────────────────────────────────────────────
        cmds.select(prefix)
        curve_shape = cmds.listRelatives(prefix, shapes=True, noIntermediate=True)[0]
        degree = cmds.getAttr(prefix + '.degree')
        span   = cmds.getAttr(prefix + '.spans')
        pointNumber = degree + span
        points = cmds.getAttr(prefix + '.cv[0:' + str(pointNumber) + ']')

        # ── FK joints ────────────────────────────────────────────────────────
        joint = None
        for i in range(pointNumber):
            lastJoint = joint
            joint = cmds.joint(p=(points[i][0], points[i][1], points[i][2]),
                               n=(prefix + '_' + str(i).zfill(3) + '_FK'))
            if i > 0:
                cmds.joint(lastJoint, e=True, zso=True, oj='xyz', sao='xup')
                cmds.setAttr(lastJoint + '.jointOrientX', 0)
            cmds.joint(e=True, oj='none', secondaryAxisOrient='xup', zso=True)
        cmds.setAttr(prefix + '_' + str(pointNumber-1).zfill(3) + '_FK.jointOrient', 0, 0, 0)

        # ── IK handle ────────────────────────────────────────────────────────
        selection  = cmds.ls(sl=True)
        startJoint = prefix + '_000_FK'
        endJoint   = selection
        cmds.select(startJoint, endJoint)
        cmds.ikHandle(sol='ikSplineSolver', name=(prefix + '_000_IKH'))
        if not cmds.isConnected(curve_shape + '.worldSpace[0]',
                                prefix + '_000_IKH.inCurve'):
            ik_plugs = cmds.listConnections(prefix + '_000_IKH.inCurve',
                                            source=True, plugs=True) or []
            for plug in ik_plugs:
                cmds.disconnectAttr(plug, prefix + '_000_IKH.inCurve')
                src_node  = plug.split('.')[0]
                src_xform = cmds.listRelatives(src_node, parent=True) or []
                to_del    = src_xform[0] if src_xform else src_node
                if to_del != prefix and cmds.objExists(to_del):
                    cmds.delete(to_del)
            cmds.connectAttr(curve_shape + '.worldSpace[0]',
                             prefix + '_000_IKH.inCurve')
        effs = cmds.listConnections(prefix + '_000_IKH', t='ikEffector')
        cmds.rename(str(effs[0]), prefix + '_000_EFF')

        # ── JNT joints ───────────────────────────────────────────────────────
        cmds.select(prefix + '_000_FK')
        rels = ([str(s) for s in cmds.listRelatives(cmds.ls(sl=True),
                                                     ad=True, typ='joint')] +
                [str(s) for s in cmds.ls(sl=True)])
        for count, jnt in enumerate(sorted(rels)):
            cmds.select(clear=True)
            jntNode = cmds.rename(cmds.joint(),
                                  prefix + '_' + str(count).zfill(3) + '_JNT')
            cmds.parent(jntNode, jnt)
            for ax in ('tx', 'ty', 'tz'):
                cmds.setAttr(jntNode + '.' + ax, 0)
            for ax in ('X', 'Y', 'Z'):
                cmds.setAttr(jntNode + '.jointOrient' + ax,
                             cmds.getAttr(jnt + '.jointOrient' + ax))
        for ax in ('X', 'Y', 'Z'):
            cmds.setAttr(prefix + '_000_JNT.jointOrient' + ax, 0)

        # ── loft surfaces ─────────────────────────────────────────────────────
        for i in range(2):
            cmds.duplicate(prefix, n='loft' + str(i).zfill(3) + '_CRV')
        cmds.rebuildCurve('loft000_CRV', rt=0, s=pointNumber)
        cmds.rebuildCurve('loft001_CRV', rt=0, s=pointNumber)
        cmds.move( .5, 0, 0, 'loft000_CRV', absolute=True)
        cmds.move(-.5, 0, 0, 'loft001_CRV', absolute=True)
        for idx in range(2):
            geo = prefix + '_' + str(idx).zfill(3) + '_GEO'
            cmds.loft('loft000_CRV', 'loft001_CRV', ch=True, rn=True, ar=True, n=geo)
            cmds.rebuildSurface(geo, ch=True, rpo=True, rt=False, end=True, kr=False,
                                kcp=False, kc=False, su=True, du=3,
                                sv=surface_spans, dv=3, tol=0.01, fr=False, dir=2)
            cmds.delete(geo, ch=True)
        cmds.delete('loft000_CRV', 'loft001_CRV')
        cmds.reverseSurface(prefix + '_000_GEO', ch=True, d=0, rpo=True)
        cmds.reverseSurface(prefix + '_001_GEO', ch=True, d=0, rpo=True)

        # ── geo joints + mid follicle ─────────────────────────────────────────
        for i in range(3):
            cmds.joint(p=(0,0,0), name=prefix + '_Geo' + str(i).zfill(3) + '_FK')
            cmds.group(em=True, name=prefix + '_Geo' + str(i).zfill(3) + '_GRP')
            cmds.parent(prefix + '_Geo' + str(i).zfill(3) + '_FK',
                        prefix + '_Geo' + str(i).zfill(3) + '_GRP')
        cmds.createNode('follicle', name=prefix + '_Mid000_FOLShape')
        cmds.connectAttr(prefix + '_000_GEOShape.worldMatrix[0]',
                         prefix + '_Mid000_FOLShape.inputWorldMatrix')
        cmds.connectAttr(prefix + '_000_GEOShape.local',
                         prefix + '_Mid000_FOLShape.inputSurface')
        cmds.connectAttr(prefix + '_Mid000_FOLShape.outTranslate',
                         prefix + '_Mid000_FOL.translate')
        cmds.connectAttr(prefix + '_Mid000_FOLShape.outRotate',
                         prefix + '_Mid000_FOL.rotate')
        cmds.setAttr(prefix + '_Mid000_FOLShape.parameterU', .5)
        cmds.setAttr(prefix + '_Mid000_FOLShape.parameterV', .5)

        # ── 3 main CTLs + SDK chain ───────────────────────────────────────────
        for i in range(3):
            cmds.circle(radius=4, nr=(0,1,0), c=(0,0,0),
                        n=prefix + '_' + str(i).zfill(3) + '_CTL', ch=False)
            cmds.group(em=True, name=prefix + '_CTL' + str(i).zfill(3) + '_GRP')
            cmds.parent(prefix + '_' + str(i).zfill(3) + '_CTL',
                        prefix + '_CTL' + str(i).zfill(3) + '_GRP')

        cmds.group(em=True, name=prefix + '_CTL001_TopSDK_GRP')
        cmds.parent(prefix + '_CTL001_TopSDK_GRP', prefix + '_Mid000_FOL')
        cmds.setAttr(prefix + '_CTL001_TopSDK_GRP.translate', 0, 0, 0)
        cmds.group(em=True, name=prefix + '_CTL001_TopRotateSDK_GRP')
        cmds.parent(prefix + '_CTL001_TopRotateSDK_GRP',
                    prefix + '_CTL001_TopSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_TopRotateSDK_GRP.translate', 0, 0, 0)
        cmds.group(em=True, name=prefix + '_CTL001_BtmRotateSDK_GRP')
        cmds.parent(prefix + '_CTL001_BtmRotateSDK_GRP',
                    prefix + '_CTL001_TopRotateSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_BtmRotateSDK_GRP.translate', 0, 0, 0)
        cmds.parent(prefix + '_CTL001_GRP', prefix + '_CTL001_BtmRotateSDK_GRP')
        cmds.setAttr(prefix + '_CTL001_GRP.translate', 0, 0, 0)
        cmds.rename(prefix + '_CTL001_GRP', prefix + '_CTL001_BtmSDK_GRP')

        # ── position CTLs via temporary constraints ───────────────────────────
        cmds.parentConstraint(prefix + '_001_CTL', prefix + '_Geo001_FK')
        cmds.setAttr(prefix + '_CTL001_BtmSDK_GRP.rotate', 0, 0, 0)
        pc = cmds.pointConstraint(prefix + '_000_EFF',
                                  prefix + '_CTL002_GRP', mo=False)[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_002_CTL', prefix + '_Geo002_FK')
        pc = cmds.pointConstraint(prefix + '_000_FK',
                                  prefix + '_CTL000_GRP', mo=False)[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_000_CTL', prefix + '_Geo000_FK')

        up_loc = prefix + '_up_LOC'
        cmds.spaceLocator(n=up_loc)
        cmds.parent(up_loc, prefix + '_000_FK')
        cmds.setAttr(up_loc + '.translate', 0, 0, -2)
        cmds.setAttr(up_loc + '.rotate', 0, 0, 0)
        ac = cmds.aimConstraint(prefix + '_001_FK', prefix + '_CTL000_GRP',
                                aimVector=[0,1,0], worldUpType='object',
                                worldUpObject=up_loc)[0]
        cmds.delete(ac)
        cmds.parent(up_loc, endJoint)
        cmds.setAttr(up_loc + '.translate', 0, 0, -2)
        cmds.setAttr(up_loc + '.rotate', 0, 0, 0)
        ac = cmds.aimConstraint(lastJoint, prefix + '_CTL002_GRP',
                                aimVector=[0,-1,0], upVector=[0,0,-1],
                                worldUpType='object', worldUpObject=up_loc)[0]
        cmds.delete(ac)
        cmds.delete(up_loc)

        for n in (prefix + '_UpTwist000_NULL', prefix + '_DwnTwist000_NULL'):
            cmds.group(em=True, name=n)
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
        pc = cmds.parentConstraint(prefix + '_000_CTL',
                                   prefix + '_Geo000_GRP')[0]
        cmds.delete(pc)
        pc = cmds.parentConstraint(prefix + '_000_CTL',
                                   prefix + '_Geo002_GRP')[0]
        cmds.delete(pc)

        # ── twist MDN + PMA nodes ─────────────────────────────────────────────
        for i in range(pointNumber):
            node = cmds.createNode('multiplyDivide',
                                   n=(prefix + '_Twist' + str(i).zfill(3) + '_MDN'))
            cmds.connectAttr(prefix + '_002_CTL.twist', node + '.input1X')
            cmds.connectAttr(prefix + '_001_CTL.rotateY', node + '.input1Y')
            cmds.connectAttr(prefix + '_000_CTL.twist', node + '.input1Z')
        for i in range(pointNumber):
            pma = cmds.createNode('plusMinusAverage',
                                  n=(prefix + '_Twist' + str(i).zfill(3) + '_PMA'))
            cmds.setAttr(pma + '.operation', 1)
            mdn = prefix + '_Twist' + str(i).zfill(3) + '_MDN'
            cmds.connectAttr(mdn + '.outputX', pma + '.input1D[0]')
            cmds.connectAttr(mdn + '.outputY', pma + '.input1D[1]')
            cmds.connectAttr(mdn + '.outputZ', pma + '.input1D[2]')
        for i in range(pointNumber):
            cmds.connectAttr(prefix + '_Twist' + str(i).zfill(3) + '_PMA.output1D',
                             prefix + '_' + str(i).zfill(3) + '_JNT.rotateX')

        # ── curveInfo + squash/stretch ─────────────────────────────────────────
        cin = cmds.createNode('curveInfo', n=(prefix + '_000_CIN'))
        cmds.connectAttr(curve_shape + '.worldSpace', cin + '.inputCurve')
        mdn = cmds.createNode('multiplyDivide',
                              n=(prefix + '_SquashStretch000_MDN'))
        cmds.setAttr(mdn + '.operation', 2)
        cmds.connectAttr(cin + '.arcLength', mdn + '.input1.input1X')
        cmds.setAttr(mdn + '.input2X', cmds.getAttr(mdn + '.input1X'))
        for i in range(pointNumber):
            cmds.connectAttr(mdn + '.outputX',
                             prefix + '_' + str(i).zfill(3) + '_FK.scaleX')

        # ── joint follicles ───────────────────────────────────────────────────
        for i in range(pointNumber):
            cmds.spaceLocator(n='folliclePos' + str(i).zfill(3) + '_LOC')
            cmds.parentConstraint(prefix + '_' + str(i).zfill(3) + '_FK',
                                  'folliclePos' + str(i).zfill(3) + '_LOC')
        for i in range(pointNumber):
            cpos = cmds.createNode('closestPointOnSurface',
                                   n='folliclePos' + str(i).zfill(3) + '_CPOS')
            cmds.connectAttr('folliclePos' + str(i).zfill(3) + '_LOC.translate',
                             cpos + '.inPosition')
            cmds.connectAttr(prefix + '_001_GEOShape.worldSpace', cpos + '.inputSurface')
        for i in range(pointNumber):
            fsh = prefix + '_Joint_' + str(i).zfill(3) + '_FOLShape'
            fxf = prefix + '_Joint_' + str(i).zfill(3) + '_FOL'
            cpos = 'folliclePos' + str(i).zfill(3) + '_CPOS'
            cmds.createNode('follicle', n=fsh)
            cmds.connectAttr(prefix + '_001_GEOShape.worldMatrix', fsh + '.inputWorldMatrix')
            cmds.connectAttr(prefix + '_001_GEOShape.local',       fxf + '.inputSurface')
            cmds.connectAttr(fsh + '.outTranslate', fxf + '.translate')
            cmds.connectAttr(fsh + '.outRotate',    fxf + '.rotate')
            for ax in ['translateX','translateY','translateZ',
                       'rotateX','rotateY','rotateZ']:
                cmds.setAttr(fxf + '.' + ax, lock=True)
            cmds.connectAttr(cpos + '.parameterU', fxf + '.parameterU')
            cmds.connectAttr(cpos + '.parameterV', fxf + '.parameterV')
            cmds.disconnectAttr(cpos + '.parameterU', fxf + '.parameterU')
            cmds.disconnectAttr(cpos + '.parameterV', fxf + '.parameterV')
            cmds.delete(cpos)
            cmds.delete('folliclePos' + str(i).zfill(3) + '_LOC')
        for i in range(pointNumber):
            drv = cmds.joint(n=(prefix + '_Joint_' + str(i).zfill(3) + '_DRV'))
            cmds.parent(drv, prefix + '_Joint_' + str(i).zfill(3) + '_FOL')
            for ax in ['translateX','translateY','translateZ',
                       'rotateX','rotateY','rotateZ']:
                cmds.setAttr(drv + '.' + ax, 0)

        # ── skin clusters ─────────────────────────────────────────────────────
        cmds.skinCluster(prefix + '_Geo000_FK', prefix + '_Geo002_FK',
                         prefix + '_000_GEO', dr=4.5,
                         n=prefix + '_Geo000_SKN')
        cmds.skinCluster(prefix + '_Geo000_FK', prefix + '_Geo002_FK',
                         prefix + '_Geo001_FK',
                         prefix + '_001_GEO', dr=4.5,
                         n=prefix + '_Geo001_SKN')
        driverJoints = cmds.ls(prefix + '_Joint*_DRV')
        cmds.skinCluster(driverJoints, prefix, n=prefix + '_Crv000_SKN')

        cmds.rename(prefix, prefix + '_000_CRV')

        # ── COG CTLs ──────────────────────────────────────────────────────────
        lengthOfCurve = cmds.getAttr(prefix + '_SquashStretch000_MDN.input2X')

        all000 = cmds.curve(name=(prefix + '_All000_CTL'), degree=3,
            point=[(-2.587e-15,5.448e-36,8.4899356232051044),
                   (4.086088758749157,5.448e-36,4.8693000688131338),
                   (6.8101479312486024,5.448e-36,1.2486645144211457),
                   (5.4481183449988837,5.448e-36,-3.9998118128096531),
                   (2.587e-15,5.448e-36,-6.7238709853090981),
                   (-5.4481183449988766,5.448e-36,-3.9998118128096594),
                   (-6.8101479312485997,5.448e-36,1.248664514421141),
                   (-4.0860887587491641,5.448e-36,4.8693000688131205),
                   (-1.724e-15,2.041e-32,8.4899356232051044)])
        cmds.addAttr(longName='subControlOneVisibility', keyable=True, min=0, max=1,
                     attributeType='long')
        cmds.addAttr(longName='subControlTwoVisibility', keyable=True, min=0, max=1,
                     attributeType='long')
        cmds.rename(cmds.listRelatives(all000, shapes=True)[0],
                    prefix + '_All000_CTLShape')
        cmds.setAttr(prefix + '_All000_CTL.subControlOneVisibility',
                     keyable=False, channelBox=True)
        cmds.setAttr(prefix + '_All000_CTL.subControlTwoVisibility',
                     keyable=False, channelBox=True)

        all001 = cmds.curve(name=(prefix + '_All001_CTL'), degree=3,
            point=[(-2.412e-15,4.223e-35,7.9372176682272988),
                   (3.8185271911283234,4.223e-35,4.5536652958006165),
                   (6.3642119852138777,4.223e-35,1.170112923373918),
                   (5.0913695881711041,4.223e-35,-3.7346874250304691),
                   (2.423e-15,4.223e-35,-6.2803722191160229),
                   (-5.091369588171097,4.223e-35,-3.7346874250304749),
                   (-6.364211985213875,4.223e-35,1.1701129233739136),
                   (-3.8185271911283292,4.223e-35,4.553665295800605),
                   (-1.606e-15,1.911e-32,7.9372176682272988)])
        cmds.rename(cmds.listRelatives(all001, shapes=True)[0],
                    prefix + '_All001_CTLShape')

        all002 = cmds.curve(name=(prefix + '_All002_CTL'), degree=3,
            point=[(-2.195e-15,8.120e-35,7.246874953712628),
                   (3.4846338500471794,8.120e-35,4.1591815734589863),
                   (5.80772308341197,8.120e-35,1.0714881932053306),
                   (4.6461784667295767,8.120e-35,-3.4044347127470127),
                   (2.217e-15,8.120e-35,-5.7275239461118046),
                   (-4.6461784667295722,8.120e-35,-3.404434712747018),
                   (-5.8077230834119673,8.120e-35,1.0714881932053264),
                   (-3.4846338500471838,8.120e-35,4.1591815734589765),
                   (-1.460e-15,1.748e-32,7.246874953712628)])
        cmds.rename(cmds.listRelatives(all002, shapes=True)[0],
                    prefix + '_All002_CTLShape')

        for i, grp in enumerate(
                (prefix + '_All000_GRP', prefix + '_All001_GRP',
                 prefix + '_All002_GRP')):
            cmds.group(em=True, name=grp)
        cmds.parent(prefix + '_All000_CTL', prefix + '_All000_GRP')
        cmds.parent(prefix + '_All001_CTL', prefix + '_All001_GRP')
        cmds.parent(prefix + '_All002_CTL', prefix + '_All002_GRP')
        pc = cmds.parentConstraint(prefix + '_000_CTL',
                                   prefix + '_All000_GRP')[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_All000_CTL', prefix + '_All001_GRP')
        cmds.parentConstraint(prefix + '_All001_CTL', prefix + '_All002_GRP')

        cmds.connectAttr(prefix + '_All000_CTL.subControlOneVisibility',
                         prefix + '_All001_CTL.visibility')
        cmds.connectAttr(prefix + '_All000_CTL.subControlTwoVisibility',
                         prefix + '_All002_CTL.visibility')

        cmds.parent(prefix + '_000_FK',  prefix + '_All000_GRP')
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
        cmds.parent(prefix + '_All000_GRP',         prefix + '_Master000_GRP')

        cmds.parentConstraint(prefix + '_All002_CTL', prefix + '_CTL000_GRP')
        cmds.group(em=True, name=prefix + '_CTL002constraint_GRP')
        pc = cmds.parentConstraint(prefix + '_002_CTL',
                                   prefix + '_CTL002constraint_GRP')[0]
        cmds.delete(pc)
        cmds.parentConstraint(prefix + '_CTL002constraint_GRP',
                              prefix + '_CTL002_GRP')
        cmds.parent(prefix + '_CTL002constraint_GRP', prefix + '_All002_CTL')
        cmds.parent(prefix + '_000_IKH', prefix + '_All000_CTL')
        cmds.parent(prefix + '_000_FK',  prefix + '_All000_CTL')

        # ── global scale ──────────────────────────────────────────────────────
        cmds.createNode('multiplyDivide', n=prefix + '_GlobalScale000_MDN')
        arcLen = cmds.getAttr(prefix + '_000_CIN.arcLength')
        cmds.setAttr(prefix + '_GlobalScale000_MDN.input1X', arcLen)
        cmds.addAttr(prefix + '_All000_CTL', longName='globalScale',
                     defaultValue=1, keyable=True)
        cmds.connectAttr(prefix + '_All000_CTL.globalScale',
                         prefix + '_GlobalScale000_MDN.input2X')
        cmds.connectAttr(prefix + '_GlobalScale000_MDN.outputX',
                         prefix + '_SquashStretch000_MDN.input2X')
        scale_targets = (
            [prefix + '_All000_GRP', prefix + '_All001_GRP',
             prefix + '_All002_GRP', prefix + '_Mid000_FOL',
             prefix + '_Geo000_FK', prefix + '_Geo001_FK',
             prefix + '_Geo002_FK', prefix + '_CTL000_GRP',
             prefix + '_CTL002_GRP'] +
            [prefix + '_Joint_' + str(i).zfill(3) + '_FOL'
             for i in range(pointNumber)]
        )
        for node in scale_targets:
            for ax in ('scaleX', 'scaleY', 'scaleZ'):
                cmds.connectAttr(prefix + '_All000_CTL.globalScale',
                                 node + '.' + ax)
        for ax in ('scaleX', 'scaleY', 'scaleZ'):
            cmds.setAttr(prefix + '_All000_CTL.' + ax, lock=True, keyable=False)

        cmds.createNode('addDoubleLinear', n=prefix + 'ExtraTwist000_ADL')
        cmds.createNode('addDoubleLinear', n=prefix + 'ExtraTwist002_ADL')
        cmds.connectAttr(prefix + '_000_CTL.rotateY',
                         prefix + 'ExtraTwist000_ADL.input1')
        cmds.connectAttr(prefix + '_002_CTL.rotateY',
                         prefix + 'ExtraTwist002_ADL.input1')
        cmds.connectAttr(prefix + 'ExtraTwist000_ADL.output',
                         prefix + '_000_CTL.twist')
        cmds.connectAttr(prefix + 'ExtraTwist002_ADL.output',
                         prefix + '_002_CTL.twist')

        # ── SDK set driven keys ───────────────────────────────────────────────
        rotAmt = 90
        topTX  = prefix + '_002_CTL.tx'
        topRZ  = prefix + '_002_CTL.rz'
        btmTX  = prefix + '_000_CTL.tx'
        btmRZ  = prefix + '_000_CTL.rz'
        midTopT  = prefix + '_CTL001_TopSDK_GRP.rz'
        midTopR  = prefix + '_CTL001_TopRotateSDK_GRP.rz'
        midBtmS  = prefix + '_CTL001_BtmSDK_GRP.rz'
        midBtmR  = prefix + '_CTL001_BtmRotateSDK_GRP.rz'
        for driver, driven, pairs in [
            (topTX, midTopT,
             [(lengthOfCurve,-rotAmt), (-lengthOfCurve,rotAmt), (0,0)]),
            (topRZ, midTopR,
             [(rotAmt,-rotAmt), (-rotAmt,rotAmt), (0,0)]),
            (btmRZ, midBtmR,
             [(rotAmt,-rotAmt), (-rotAmt,rotAmt), (0,0)]),
            (btmTX, midBtmS,
             [(lengthOfCurve,rotAmt), (-lengthOfCurve,-rotAmt), (0,0)]),
        ]:
            for dv, dvv in pairs:
                cmds.setAttr(driver, dv)
                cmds.setAttr(driven, dvv)
                cmds.setDrivenKeyframe(driven, cd=driver)

        theJoints = list(range(pointNumber))
        half = len(theJoints) // 2
        for j in theJoints:
            mdn = prefix + '_Twist' + str(j).zfill(3) + '_MDN'
            cmds.setAttr(mdn + '.input2Z', 1 - float(j) / (len(theJoints)-1))
            cmds.setAttr(mdn + '.input2X', float(j) / (len(theJoints)-1))
        for j in theJoints[:half+1]:
            mdn = prefix + '_Twist' + str(j).zfill(3) + '_MDN'
            cmds.setAttr(mdn + '.input2Y', 2*(float(j)/(len(theJoints)-1)))
        for j in theJoints[half+1:]:
            mdn = prefix + '_Twist' + str(j).zfill(3) + '_MDN'
            cmds.setAttr(mdn + '.input2Y', 2*(1-float(j)/(len(theJoints)-1)))

        # ── SKL joints from JNT values (to set initial orient) ────────────────
        for i in range(pointNumber):
            jnt = prefix + '_' + str(i).zfill(3) + '_JNT'
            for ax in ('X', 'Y', 'Z'):
                cmds.setAttr(jnt + '.jointOrient' + ax, 0)

        # ── rename controls ───────────────────────────────────────────────────
        cmds.rename(prefix + '_All000_CTL', prefix + 'COG_CTL')
        cmds.rename(prefix + '_All001_CTL', prefix + 'COG_Mid_CTL')
        cmds.rename(prefix + '_All002_CTL', prefix + 'COG_Btm_CTL')
        cmds.rename(prefix + '_000_CTL',    prefix + 'Btm_CTL')
        cmds.rename(prefix + '_001_CTL',    prefix + 'Mid_CTL')
        cmds.rename(prefix + '_002_CTL',    prefix + 'Top_CTL')

        # ── final grouping ────────────────────────────────────────────────────
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
        cmds.parent(prefix + '_000_GEO', prefix + '_001_GEO',
                    prefix + '_000_CRV', prefix + '_Rig_GRP')

        # ── control colours ───────────────────────────────────────────────────
        for shape in (prefix + 'COG_CTLShape', prefix + 'COG_Mid_CTLShape',
                      prefix + 'COG_Btm_CTLShape', prefix + 'Btm_CTLShape',
                      prefix + 'Mid_CTLShape',     prefix + 'Top_CTLShape'):
            cmds.setAttr(shape + '.overrideEnabled', 1)
            cmds.setAttr(shape + '.overrideColor', 22)
        cmds.setAttr(prefix + '_002_CTL.rotateOrder', 4)

        # ── tip controls (extending beyond Top_CTL) ───────────────────────────
        _build_tip_controls(prefix, pointNumber, tip_count)

        # ── merged SKL chain ──────────────────────────────────────────────────
        _build_skl_chain(prefix, pointNumber, tip_count)

        cmds.select(clear=True)

    finally:
        cmds.keyTangent(itt=currentIT[0], g=True)
        cmds.keyTangent(ott=currentOT[0], g=True)

    return pointNumber


def _build_tip_controls(prefix, pointNumber, tip_count):
    """Daisy-chained FK tip controls extending from Top_CTL."""
    last_fk  = prefix + '_' + str(pointNumber-1).zfill(3) + '_FK'
    prev_fk  = prefix + '_' + str(pointNumber-2).zfill(3) + '_FK'
    p_last   = cmds.xform(last_fk, q=True, ws=True, t=True)
    p_prev   = cmds.xform(prev_fk, q=True, ws=True, t=True)
    tip_dir  = _norm(_sub(tuple(p_last), tuple(p_prev)))
    tip_step = _len(_sub(tuple(p_last), tuple(p_prev)))

    tip_root = cmds.group(em=True, n=prefix + '_Tip_GRP')
    cmds.parent(tip_root, prefix + '_NoTransform000_GRP')

    top_ctl  = prefix + 'Top_CTL'
    prev_ctl = top_ctl

    for i in range(1, tip_count + 1):
        tip_pos = _add(tuple(p_last), _scale(tip_dir, tip_step * i))
        grp = cmds.group(em=True, n=prefix + '_Tip' + str(i).zfill(3) + '_GRP')
        cmds.parent(grp, tip_root)
        cmds.xform(grp, ws=True, t=tip_pos)

        ctl = cmds.circle(radius=3, nr=(0,1,0), c=(0,0,0),
                          n=prefix + '_Tip' + str(i).zfill(3) + '_CTL',
                          ch=False)[0]
        cmds.parent(ctl, grp)
        cmds.xform(ctl, t=(0,0,0), ro=(0,0,0), os=True)

        for attr in ('scaleX', 'scaleY', 'scaleZ', 'visibility'):
            cmds.setAttr(prefix + '_Tip' + str(i).zfill(3) + '_CTL.' + attr,
                         lock=True, keyable=False)

        ctl_shape = cmds.listRelatives(ctl, shapes=True)[0]
        cmds.setAttr(ctl_shape + '.overrideEnabled', 1)
        cmds.setAttr(ctl_shape + '.overrideColor', 18)  # cyan

        # Live parentConstraint: GRP follows previous CTL
        cmds.parentConstraint(prev_ctl, grp)
        prev_ctl = prefix + '_Tip' + str(i).zfill(3) + '_CTL'


def _build_skl_chain(prefix, pointNumber, tip_count):
    """Single continuous SKL chain: spine JNTs → tip CTLs."""
    cmds.select(clear=True)

    # Spine portion
    for i in range(pointNumber):
        jnt = prefix + '_' + str(i).zfill(3) + '_JNT'
        pos = cmds.xform(jnt, q=True, ws=True, t=True)
        cmds.joint(n=prefix + '_' + str(i).zfill(3) + '_SKL', p=pos)

    cmds.joint(prefix + '_000_SKL', e=True,
               oj='xyz', sao='xup', ch=True, zso=True)
    cmds.setAttr(prefix + '_' + str(pointNumber-1).zfill(3) + '_SKL.jointOrient',
                 0, 0, 0)

    for i in range(pointNumber):
        skl = prefix + '_' + str(i).zfill(3) + '_SKL'
        jnt = prefix + '_' + str(i).zfill(3) + '_JNT'
        cmds.parentConstraint(jnt, skl)

    # Tip portion — continued from last spine SKL
    cmds.select(prefix + '_' + str(pointNumber-1).zfill(3) + '_SKL')
    for i in range(1, tip_count + 1):
        tip_ctl = prefix + '_Tip' + str(i).zfill(3) + '_CTL'
        tip_pos = cmds.xform(tip_ctl, q=True, ws=True, t=True)
        tip_skl = cmds.joint(n=prefix + '_Tip' + str(i).zfill(3) + '_SKL',
                             p=tip_pos)
        cmds.parentConstraint(tip_ctl, tip_skl)

    # Orient tip portion
    last_spine = prefix + '_' + str(pointNumber-1).zfill(3) + '_SKL'
    cmds.joint(last_spine, e=True, oj='xyz', sao='xup', ch=True, zso=True)
    cmds.setAttr(prefix + '_Tip' + str(tip_count).zfill(3) + '_SKL.jointOrient',
                 0, 0, 0)

    # Keep SKL root at world level (outside NoTransform group so it survives clean)
    cmds.select(clear=True)


def get_skl_joints(prefix, pointNumber, tip_count):
    """Return ordered list of all SKL joints for this rig."""
    spine = [prefix + '_' + str(i).zfill(3) + '_SKL' for i in range(pointNumber)]
    tips  = [prefix + '_Tip' + str(i).zfill(3) + '_SKL'
             for i in range(1, tip_count + 1)]
    return spine + tips


# ── button 2: skin hair ───────────────────────────────────────────────────────

def skin_hair(geo, prefix, pointNumber, tip_count):
    """Bind geo to the SKL chain. Returns the skinCluster node name."""
    skl = get_skl_joints(prefix, pointNumber, tip_count)
    missing = [j for j in skl if not cmds.objExists(j)]
    if missing:
        raise RuntimeError('SKL joints not found: ' + ', '.join(missing))
    sc = cmds.skinCluster(skl + [geo], toSelectedBones=True,
                          n=prefix + '_Hair_SKN')[0]
    return sc


# ── button 3: position hair ───────────────────────────────────────────────────

def position_hair(prefix, scalp_vertex):
    """
    Build a surface follicle from *scalp_vertex*, snap the rig root to it,
    and parentConstraint the rig root to the follicle.
    Returns (scalp_mesh, follicle_transform).
    """
    # Resolve mesh + UV from vertex
    mesh = scalp_vertex.split('.')[0]
    sel = om.MSelectionList()
    sel.add(scalp_vertex)
    dag, comp = sel.getComponent(0)
    fn_mesh   = om.MFnMesh(dag)
    it_vert   = om.MItMeshVertex(dag, comp)
    vert_pos  = it_vert.position(om.MSpace.kWorld)
    _, face_idx = fn_mesh.getClosestPoint(vert_pos, om.MSpace.kWorld)
    u, v = fn_mesh.getUVAtPoint(vert_pos, om.MSpace.kWorld)

    # Build follicle
    fol_shape = cmds.createNode('follicle',
                                n=prefix + '_scalp_FOLShape')
    fol_xform = cmds.listRelatives(fol_shape, parent=True)[0]
    fol_xform = cmds.rename(fol_xform, prefix + '_scalp_FOL')

    mesh_shape = cmds.listRelatives(mesh, shapes=True,
                                    noIntermediate=True)[0]
    cmds.connectAttr(mesh_shape + '.worldMatrix[0]',
                     fol_shape + '.inputWorldMatrix')
    cmds.connectAttr(mesh_shape + '.outMesh',
                     fol_shape + '.inputMesh')
    cmds.connectAttr(fol_shape + '.outTranslate', fol_xform + '.translate')
    cmds.connectAttr(fol_shape + '.outRotate',    fol_xform + '.rotate')
    cmds.setAttr(fol_shape + '.parameterU', u)
    cmds.setAttr(fol_shape + '.parameterV', v)

    # Snap rig root to follicle then parentConstraint it
    rig_root = prefix + '_NoTransform000_GRP'
    fol_pos  = cmds.xform(fol_xform, q=True, ws=True, t=True)
    cmds.xform(rig_root, ws=True, t=fol_pos)
    cmds.parentConstraint(fol_xform, rig_root, mo=True)

    return mesh, fol_xform


# ── button 4: bake and build FK ──────────────────────────────────────────────

def bake_and_clean(prefix, scalp_mesh, scalp_fol, skin_cluster,
                   pointNumber, tip_count):
    """
    Bake SKL joints to their current world pose, delete the spine/tip rig and
    skin cluster, then build a lightweight FK daisy-chain rig over the SKL
    chain parented under the scalp follicle.
    """
    skl_joints = get_skl_joints(prefix, pointNumber, tip_count)

    # Record world matrices before deleting anything
    world_matrices = {}
    for skl in skl_joints:
        world_matrices[skl] = cmds.xform(skl, q=True, ws=True, matrix=True)

    # Delete skinCluster (so geo isn't dragged around)
    if cmds.objExists(skin_cluster):
        cmds.delete(skin_cluster)

    # Delete spine/tip rig — scalp follicle is kept as FK rig parent
    rig_root = prefix + '_NoTransform000_GRP'
    if cmds.objExists(rig_root):
        cmds.delete(rig_root)

    # Bake: clear constraints then restore world transforms root-to-tip
    for skl in skl_joints:
        for con in (cmds.listRelatives(skl, type='constraint') or []):
            cmds.delete(con)
    for skl in skl_joints:
        if cmds.objExists(skl):
            cmds.xform(skl, ws=True, matrix=world_matrices[skl])

    # Build FK daisy-chain rig over the baked SKL joints
    _build_fk_chain(prefix, skl_joints, scalp_fol)


def _build_fk_chain(prefix, skl_joints, scalp_fol):
    """
    Build a FK daisy-chain CTL for every SKL joint and parent the chain
    under scalp_fol.  Each GRP is parentConstrained to the previous CTL
    (mo=True) so the chain inherits pose naturally.  Each SKL is
    parentConstrained to its matching CTL (mo=False).
    """
    fk_root = prefix + '_FKRig_GRP'
    cmds.group(em=True, name=fk_root)
    cmds.parent(fk_root, scalp_fol)
    cmds.setAttr(fk_root + '.translate', 0, 0, 0)
    cmds.setAttr(fk_root + '.rotate', 0, 0, 0)

    prev_ctl = None
    for i, skl in enumerate(skl_joints):
        idx = str(i).zfill(3)
        grp = prefix + '_FK_' + idx + '_GRP'
        ctl = prefix + '_FK_' + idx + '_CTL'

        world_pos = cmds.xform(skl, q=True, ws=True, t=True)

        cmds.group(em=True, name=grp)
        cmds.parent(grp, fk_root)
        cmds.xform(grp, ws=True, t=world_pos)

        if prev_ctl is not None:
            cmds.parentConstraint(prev_ctl, grp, mo=True)

        cmds.select(clear=True)
        cmds.circle(radius=2, nr=(0, 1, 0), c=(0, 0, 0), name=ctl, ch=False)
        cmds.parent(ctl, grp)
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)
        for attr in ('.sx', '.sy', '.sz', '.v'):
            cmds.setAttr(ctl + attr, lock=True, keyable=False)
        ctl_shape = cmds.listRelatives(ctl, shapes=True)[0]
        cmds.setAttr(ctl_shape + '.overrideEnabled', 1)
        cmds.setAttr(ctl_shape + '.overrideColor', 22)

        cmds.parentConstraint(ctl, skl, mo=False)

        prev_ctl = ctl

    cmds.select(clear=True)


# ── button 5: snap base to surface ───────────────────────────────────────────

def snap_base_to_surface(scalp_mesh):
    """
    Snap selected base edge loop vertices to the closest point on *scalp_mesh*.
    Call with the edge loop selected.
    """
    sel = cmds.ls(sl=True, fl=True)
    if not sel:
        raise RuntimeError('Nothing selected. Select the base edge loop first.')

    verts = cmds.filterExpand(
        cmds.polyListComponentConversion(sel, toVertex=True),
        selectionMask=31) or []
    if not verts:
        raise RuntimeError('Could not resolve vertices from selection.')

    # Build MFnMesh for closest-point queries
    msel = om.MSelectionList()
    msel.add(scalp_mesh)
    dag = msel.getDagPath(0)
    fn  = om.MFnMesh(dag)

    for vert in verts:
        pos  = cmds.xform(vert, q=True, ws=True, t=True)
        mpt  = om.MPoint(pos[0], pos[1], pos[2])
        cpt, _ = fn.getClosestPoint(mpt, om.MSpace.kWorld)
        cmds.xform(vert, ws=True, t=(cpt.x, cpt.y, cpt.z))


# ── button 6: reskin ──────────────────────────────────────────────────────────

def reskin_hair(geo, prefix, pointNumber, tip_count):
    """Fresh skinCluster binding after base snap."""
    # Remove any existing skinCluster on this geo
    existing = (cmds.ls(cmds.listHistory(geo) or [], type='skinCluster') or [])
    for sc in existing:
        cmds.delete(sc)
    skl = get_skl_joints(prefix, pointNumber, tip_count)
    sc  = cmds.skinCluster(skl + [geo], toSelectedBones=True,
                           n=prefix + '_Hair_SKN')[0]
    return sc

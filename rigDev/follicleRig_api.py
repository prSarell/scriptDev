import math
import re

import maya.cmds as cmds
import maya.api.OpenMaya as om


class FollicleRigError(Exception):
    pass


# ── naming helpers ────────────────────────────────────────────────────────────

def stripNamespace(name):
    short = name.split('|')[-1]
    return short.rsplit(':', 1)[-1]


def resolveBaseName(sourceNode, customName=None):
    name = customName if customName else stripNamespace(sourceNode)
    name = re.sub(r'[^A-Za-z0-9_]', '_', name)
    if name and name[0].isdigit():
        name = '_' + name
    return name


# ── shape helpers ─────────────────────────────────────────────────────────────

def getFollicleShape(node):
    if cmds.nodeType(node) == 'follicle':
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == 'follicle':
            return shape
    raise FollicleRigError(node + ' has no follicle shape')


def getSurfaceShape(node):
    if cmds.nodeType(node) in ('nurbsSurface', 'mesh'):
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) in ('nurbsSurface', 'mesh'):
            return shape
    raise FollicleRigError(node + ' has no nurbsSurface or mesh shape')


def getCurveShape(node):
    if cmds.nodeType(node) == 'nurbsCurve':
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == 'nurbsCurve':
            return shape
    raise FollicleRigError(node + ' has no nurbsCurve shape')


# ── follicle + joint creation ─────────────────────────────────────────────────

def createFollicle(surface, u, v, name):
    surfaceShape = getSurfaceShape(surface)
    shapeType = cmds.nodeType(surfaceShape)

    cmds.select(clear=True)
    folShape = cmds.createNode('follicle')
    folXform = cmds.listRelatives(folShape, parent=True)[0]

    if shapeType == 'nurbsSurface':
        cmds.connectAttr(surfaceShape + '.local', folShape + '.inputSurface')
    else:
        cmds.connectAttr(surfaceShape + '.outMesh', folShape + '.inputMesh')

    cmds.connectAttr(surfaceShape + '.worldMatrix[0]', folShape + '.inputWorldMatrix')
    cmds.connectAttr(folShape + '.outTranslate', folXform + '.translate', force=True)
    cmds.connectAttr(folShape + '.outRotate', folXform + '.rotate', force=True)

    cmds.setAttr(folShape + '.parameterU', u)
    cmds.setAttr(folShape + '.parameterV', v)

    folXform = cmds.rename(folXform, name + '_FOL')
    folShape = cmds.listRelatives(folXform, shapes=True)[0]
    cmds.rename(folShape, name + '_FOLShape')

    return folXform


def createJointUnderFollicle(follicle, name):
    cmds.select(clear=True)
    joint = cmds.joint(name=name + '_JNT')
    cmds.parent(joint, follicle)
    for attr in ('translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ',
                 'jointOrientX', 'jointOrientY', 'jointOrientZ'):
        cmds.setAttr(joint + '.' + attr, 0)
    return joint


# ── UV helpers ────────────────────────────────────────────────────────────────

def nurbsGridUVs(uCount, vCount):
    if uCount < 1 or vCount < 1:
        raise FollicleRigError('U and V counts must each be at least 1')

    def steps(count):
        if count == 1:
            return [0.5]
        return [i / float(count - 1) for i in range(count)]

    return [(u, v) for v in steps(vCount) for u in steps(uCount)]


def getVertexUV(vertex):
    uvs = cmds.ls(cmds.polyListComponentConversion(vertex, fromVertex=True, toUV=True), flatten=True)
    if not uvs:
        raise FollicleRigError(vertex + ' has no UVs - mesh must be UV mapped')
    return tuple(cmds.polyEditUV(uvs[0], query=True))


def getCurveCVPositions(curve):
    curveShape = getCurveShape(curve)
    cvCount = cmds.getAttr(curveShape + '.degree') + cmds.getAttr(curveShape + '.spans')
    return [tuple(cmds.pointPosition('%s.cv[%d]' % (curve, i), world=True))
            for i in range(cvCount)]


def _transformPoint(transform, attr, point):
    matrix = om.MMatrix(cmds.getAttr(transform + '.' + attr))
    p = om.MPoint(point[0], point[1], point[2]) * matrix
    return (p.x, p.y, p.z)


def closestUVOnSurface(surface, point):
    '''
    One-shot closest-point query: builds a closestPointOnSurface/Mesh node,
    reads back (u, v) and the distance, then deletes the node immediately.
    See original comments for why this is build-time-only.

    NURBS: closestPointOnSurface outputs raw parameter values in the surface's
    native domain (e.g. 0-8 for a default sphere), not 0-1. Follicle
    parameterU/V expects 0-1, so we normalize using minValueU/maxValueU/V.
    Poly: closestPointOnMesh already outputs 0-1 UV values — no normalization.
    '''
    surfaceShape = getSurfaceShape(surface)
    shapeType = cmds.nodeType(surfaceShape)

    if shapeType == 'nurbsSurface':
        node = cmds.createNode('closestPointOnSurface')
        cmds.connectAttr(surfaceShape + '.local', node + '.inputSurface')
        cmds.setAttr(node + '.inPosition', *_transformPoint(surfaceShape, 'worldInverseMatrix[0]', point))
        u_raw = cmds.getAttr(node + '.parameterU')
        v_raw = cmds.getAttr(node + '.parameterV')
        closest = _transformPoint(surfaceShape, 'worldMatrix[0]', cmds.getAttr(node + '.position')[0])
        cmds.delete(node)

        minU = cmds.getAttr(surfaceShape + '.minValueU')
        maxU = cmds.getAttr(surfaceShape + '.maxValueU')
        minV = cmds.getAttr(surfaceShape + '.minValueV')
        maxV = cmds.getAttr(surfaceShape + '.maxValueV')
        u = (u_raw - minU) / (maxU - minU) if (maxU - minU) > 0 else 0.5
        v = (v_raw - minV) / (maxV - minV) if (maxV - minV) > 0 else 0.5
    else:
        node = cmds.createNode('closestPointOnMesh')
        cmds.connectAttr(surfaceShape + '.outMesh', node + '.inMesh')
        cmds.connectAttr(surfaceShape + '.worldMatrix[0]', node + '.inputMatrix')
        cmds.setAttr(node + '.inPosition', *point)
        u = cmds.getAttr(node + '.parameterU')
        v = cmds.getAttr(node + '.parameterV')
        closest = cmds.getAttr(node + '.position')[0]
        cmds.delete(node)

    distance = sum((a - b) ** 2 for a, b in zip(point, closest)) ** 0.5
    return (u, v), distance


# ── rig building ──────────────────────────────────────────────────────────────

def buildFollicleRig(surface, uvList, customName=None, nameSource=None):
    '''
    Creates one follicle + driven joint per (u, v) pair, all under one group.
    Returns (group, [(follicle, joint), ...]).
    '''
    cmds.makeLive(none=True)
    base = resolveBaseName(nameSource if nameSource else surface, customName)

    group = cmds.group(empty=True, name=base + '_FOL_GRP')
    pairs = []
    for index, (u, v) in enumerate(uvList):
        follicleName = base + '_' + str(index).zfill(2)
        follicle = createFollicle(surface, u, v, follicleName)
        joint = createJointUnderFollicle(follicle, follicleName)
        cmds.parent(follicle, group)
        pairs.append((follicle, joint))

    return group, pairs


def createNurbsGridFollicles(surface, uCount, vCount, customName=None):
    surfaceShape = getSurfaceShape(surface)
    if cmds.nodeType(surfaceShape) != 'nurbsSurface':
        raise FollicleRigError(surface + ' is not a NURBS surface')
    uvList = nurbsGridUVs(uCount, vCount)
    return buildFollicleRig(surface, uvList, customName=customName)


def createPolyVertexFollicles(vertices, customName=None):
    if not vertices:
        raise FollicleRigError('No vertices selected')
    meshes = sorted(set(vtx.split('.')[0] for vtx in vertices))
    if len(meshes) > 1:
        raise FollicleRigError('Selected vertices belong to more than one mesh: ' + ', '.join(meshes))
    uvList = [getVertexUV(vtx) for vtx in vertices]
    return buildFollicleRig(meshes[0], uvList, customName=customName)


# ── curve on surface workflow ─────────────────────────────────────────────────

def setupCurveOnSurface(surface):
    '''
    Prepares the scene for curve-on-surface follicle placement.

    NURBS: duplicates the surface, hides the original, makes the duplicate
    live, activates the EP curve tool. The user draws on the duplicate so the
    original stays clean (drawn curves embed under the surface shape node).
    Returns (original, duplicate, None).

    Poly: records existing curve shapes, makes the surface live, activates the
    EP curve tool. No duplicate needed - curves drawn on a live poly go to the
    world root, not embedded under the shape.
    Returns (original, None, frozenset_of_pre_existing_curve_shapes).
    '''
    surfaceShape = getSurfaceShape(surface)
    shapeType = cmds.nodeType(surfaceShape)
    cmds.makeLive(none=True)

    if shapeType == 'nurbsSurface':
        duplicate = cmds.duplicate(surface)[0]
        cmds.hide(surface)
        cmds.makeLive(duplicate)
        return surface, duplicate, None
    else:
        preExisting = frozenset(cmds.ls(type='nurbsCurve') or [])
        cmds.makeLive(surface)
        return surface, None, preExisting


def _cosShapeToNormalizedUVs(cosShape, surfaceShape):
    '''
    Reads CVs from a curveOnSurface shape and returns normalized (0-1) UV pairs.
    COS CVs are stored as (u, v) in the surface's native parameter domain;
    we normalize using the surface's minValue/maxValue attributes.
    '''
    degree = cmds.getAttr(cosShape + '.degree')
    spans = cmds.getAttr(cosShape + '.spans')
    minU = cmds.getAttr(surfaceShape + '.minValueU')
    maxU = cmds.getAttr(surfaceShape + '.maxValueU')
    minV = cmds.getAttr(surfaceShape + '.minValueV')
    maxV = cmds.getAttr(surfaceShape + '.maxValueV')
    rangeU = (maxU - minU) or 1.0
    rangeV = (maxV - minV) or 1.0
    uvList = []
    for i in range(degree + spans):
        raw = cmds.getAttr('%s.cv[%d]' % (cosShape, i))
        u_raw = raw[0][0] if isinstance(raw[0], (list, tuple)) else raw[0]
        v_raw = raw[0][1] if isinstance(raw[0], (list, tuple)) else raw[1]
        uvList.append(((u_raw - minU) / rangeU, (v_raw - minV) / rangeV))
    return uvList


def createFolliclesFromCurveSetup(original, duplicate, preExistingCurves=None):
    '''
    Called after setupCurveOnSurface once the user has drawn their curve.
    Finds the curve, projects its CVs onto the original surface, builds the
    follicle rig, then cleans up (deletes duplicate or drawn curve).
    Returns (group, [(follicle, joint), ...]).
    '''
    cmds.makeLive(none=True)

    if duplicate is not None:
        dupShape = getSurfaceShape(duplicate)
        curveTransform = None
        cosShape = None
        for child in (cmds.listRelatives(dupShape, children=True) or []):
            childShapes = cmds.listRelatives(child, shapes=True, noIntermediate=True) or []
            for s in childShapes:
                if cmds.nodeType(s) in ('nurbsCurve', 'curveOnSurface'):
                    curveTransform = child
                    cosShape = s
                    break
            if curveTransform:
                break

        if curveTransform is None:
            cmds.delete(duplicate)
            cmds.showHidden(original)
            raise FollicleRigError(
                'No curve found on the surface. Draw a curve on it first.')

        nameSource = curveTransform
        origShape = getSurfaceShape(original)
        try:
            if cmds.nodeType(cosShape) == 'curveOnSurface':
                # EP curve tool on a live NURBS surface creates a curveOnSurface
                # node whose CVs are stored in the surface's native UV parameter
                # space — read and normalize directly, no world-space projection.
                uvList = _cosShapeToNormalizedUVs(cosShape, origShape)
            else:
                positions = getCurveCVPositions(curveTransform)
                if not positions:
                    raise FollicleRigError('Curve has no CVs')
                uvList = []
                for index, point in enumerate(positions):
                    uv, distance = closestUVOnSurface(original, point)
                    if distance > 0.01:
                        cmds.warning('cv[%d] is %.4f units from surface' % (index, distance))
                    uvList.append(uv)
            result = buildFollicleRig(original, uvList, nameSource=nameSource)
        finally:
            if cmds.objExists(duplicate):
                cmds.delete(duplicate)
            cmds.showHidden(original)

        return result

    else:
        currentShapes = set(cmds.ls(type='nurbsCurve') or [])
        newShapes = currentShapes - set(preExistingCurves or [])

        if not newShapes:
            raise FollicleRigError('No new curve found. Draw a curve on the surface first.')

        newCurves = []
        seen = set()
        for shape in newShapes:
            parents = cmds.listRelatives(shape, parent=True) or []
            if parents and parents[0] not in seen:
                seen.add(parents[0])
                newCurves.append(parents[0])

        if len(newCurves) > 1:
            raise FollicleRigError(
                '%d new curves found. Undo extra curves and try again.' % len(newCurves))

        curveTransform = newCurves[0]
        positions = getCurveCVPositions(curveTransform)
        if not positions:
            raise FollicleRigError('Curve has no CVs')

        uvList = []
        for index, point in enumerate(positions):
            uv, distance = closestUVOnSurface(original, point)
            if distance > 0.01:
                cmds.warning('cv[%d] is %.4f units from %s' % (index, distance, original))
            uvList.append(uv)

        result = buildFollicleRig(original, uvList, nameSource=curveTransform)
        cmds.delete(curveTransform)
        return result


# ── vertex mode ───────────────────────────────────────────────────────────────

def enterVertexMode(geo):
    getSurfaceShape(geo)
    cmds.select(geo)
    cmds.selectMode(component=True)
    cmds.selectType(vertex=True)


# ── controller helpers ────────────────────────────────────────────────────────

def getSurfaceFromFollicle(follicle):
    folShape = getFollicleShape(follicle)
    src = cmds.listConnections(folShape + '.inputSurface', source=True, destination=False) or []
    if src:
        return src[0]
    src = cmds.listConnections(folShape + '.inputMesh', source=True, destination=False) or []
    if src:
        return src[0]
    raise FollicleRigError('No surface connected to ' + follicle)


def getJointUnderFollicle(follicle):
    children = cmds.listRelatives(follicle, children=True, type='joint') or []
    if not children:
        raise FollicleRigError('No joint found under ' + follicle)
    return children[0]


def resolveToFollicle(node):
    if cmds.nodeType(node) == 'joint':
        parent = (cmds.listRelatives(node, parent=True) or [None])[0]
        if parent:
            try:
                getFollicleShape(parent)
                return parent
            except FollicleRigError:
                pass
        raise FollicleRigError(node + ' is not parented under a follicle')
    try:
        getFollicleShape(node)
        return node
    except FollicleRigError:
        raise FollicleRigError(node + ' is not a follicle or follicle-parented joint')


def addControllersForSelection(nodes):
    '''
    Builds a UV driver control + joint driver control for each unique follicle
    in `nodes`. Accepts follicle transforms and/or their child joints.
    Deduplicates so selecting a follicle and its own child joint counts as one.
    Anchor follicles for UV controls are parented into the same group as
    their driven follicle.
    Returns [(uv_ctrl, jnt_ctrl), ...].
    '''
    follicles = []
    seen = set()
    for node in nodes:
        try:
            fol = resolveToFollicle(node)
        except FollicleRigError:
            cmds.warning('Skipping ' + node + ': not a follicle or follicle-parented joint')
            continue
        if fol not in seen:
            seen.add(fol)
            follicles.append(fol)

    if not follicles:
        raise FollicleRigError('No follicles found in selection')

    results = []
    for follicle in follicles:
        surface = getSurfaceFromFollicle(follicle)
        joint = getJointUnderFollicle(follicle)
        group = (cmds.listRelatives(follicle, parent=True) or [None])[0]

        uvCtrl, anchor = createUVDriverControl(follicle, surface)
        if group:
            cmds.parent(anchor, group)

        jntCtrl = createJointDriverControl(follicle, joint)
        results.append((uvCtrl, jntCtrl))

    return results


# ── UV-driver control ─────────────────────────────────────────────────────────
#
# Fixed convention: control.translateX drives parameterU, translateY drives
# parameterV. The control is built flat in the XY plane (normal +Z) so it
# lies flat in the surface's tangent plane once parented under its anchor
# follicle, where local X = U-tangent and local Y = V-tangent.

def _fourArrowCurve(name):
    tip, shoulder, inner = 1.5, 0.9, 0.3
    points = [
        (0, tip, 0), (inner, shoulder, 0), (inner, inner, 0),
        (shoulder, inner, 0), (tip, 0, 0), (shoulder, -inner, 0),
        (inner, -inner, 0), (inner, -shoulder, 0), (0, -tip, 0),
        (-inner, -shoulder, 0), (-inner, -inner, 0), (-shoulder, -inner, 0),
        (-tip, 0, 0), (-shoulder, inner, 0), (-inner, inner, 0),
        (-inner, shoulder, 0), (0, tip, 0),
    ]
    return cmds.curve(name=name, degree=1, point=points)


def _calibrationSpan(surface, anchorPos, u, v, axis, epsilon=0.01):
    value = u if axis == 'u' else v
    delta = epsilon if value + epsilon <= 1.0 else -epsilon
    sampleU, sampleV = (u + delta, v) if axis == 'u' else (u, v + delta)

    probe = createFollicle(surface, sampleU, sampleV, '_uvCalibrationProbe')
    probePos = cmds.xform(probe, query=True, worldSpace=True, translation=True)
    cmds.delete(probe)

    distance = sum((a - b) ** 2 for a, b in zip(anchorPos, probePos)) ** 0.5
    return max(distance / abs(delta), 1e-6)


def _linearUVChain(controlAttr, axisSpan, startingValue, sensitivityAttr, baseName, axisLabel):
    mdSensitivity = cmds.createNode('multiplyDivide', name=baseName + '_' + axisLabel + 'Sens_MDV')
    cmds.connectAttr(controlAttr, mdSensitivity + '.input1X')
    cmds.connectAttr(sensitivityAttr, mdSensitivity + '.input2X')

    mdSpan = cmds.createNode('multiplyDivide', name=baseName + '_' + axisLabel + 'Span_MDV')
    cmds.setAttr(mdSpan + '.operation', 2)
    cmds.connectAttr(mdSensitivity + '.outputX', mdSpan + '.input1X')
    cmds.setAttr(mdSpan + '.input2X', axisSpan)

    pmaOffset = cmds.createNode('plusMinusAverage', name=baseName + '_' + axisLabel + 'Offset_PMA')
    cmds.connectAttr(mdSpan + '.outputX', pmaOffset + '.input1D[0]')
    cmds.setAttr(pmaOffset + '.input1D[1]', startingValue)

    clamp = cmds.createNode('clamp', name=baseName + '_' + axisLabel + '_CLA')
    cmds.setAttr(clamp + '.maxR', 1)
    cmds.connectAttr(pmaOffset + '.output1D', clamp + '.inputR')

    return clamp + '.outputR'


def createUVDriverControl(follicle, surface, customName=None, sensitivity=1.0, useArrowShape=True):
    '''
    Builds a calibrated UV driver control for the follicle.
    Returns (ctrl, anchor) — the anchor follicle should be parented into the
    rig group by the caller (see addControllersForSelection).
    '''
    cmds.makeLive(none=True)
    base = customName if customName else stripNamespace(follicle)
    if not customName and base.endswith('_FOL'):
        base = base[:-len('_FOL')]

    folShape = getFollicleShape(follicle)
    startU = cmds.getAttr(folShape + '.parameterU')
    startV = cmds.getAttr(folShape + '.parameterV')

    anchor = createFollicle(surface, startU, startV, base + '_uvAnchor')
    anchorPos = cmds.xform(anchor, query=True, worldSpace=True, translation=True)

    spanU = _calibrationSpan(surface, anchorPos, startU, startV, 'u')
    spanV = _calibrationSpan(surface, anchorPos, startU, startV, 'v')

    ctrl = _fourArrowCurve(base + '_uv_CTL') if useArrowShape else \
        cmds.circle(name=base + '_uv_CTL', normal=(0, 0, 1), radius=1, constructionHistory=False)[0]

    cmds.parent(ctrl, anchor)
    cmds.setAttr(ctrl + '.translate', 0, 0, 0)
    cmds.setAttr(ctrl + '.rotate', 0, 0, 0)

    cmds.addAttr(ctrl, longName='sensitivity', attributeType='float', defaultValue=sensitivity, keyable=False)
    cmds.setAttr(ctrl + '.sensitivity', channelBox=True)

    uOut = _linearUVChain(ctrl + '.translateX', spanU, startU, ctrl + '.sensitivity', base, 'u')
    vOut = _linearUVChain(ctrl + '.translateY', spanV, startV, ctrl + '.sensitivity', base, 'v')

    cmds.connectAttr(uOut, folShape + '.parameterU', force=True)
    cmds.connectAttr(vOut, folShape + '.parameterV', force=True)

    for axis in ('X', 'Y', 'Z'):
        cmds.setAttr(ctrl + '.rotate' + axis, lock=True, keyable=False, channelBox=False)

    return ctrl, anchor


# ── joint-driver control ──────────────────────────────────────────────────────

def _stopSignCurve(name, height=2.0, radius=0.6, sides=8):
    pole = cmds.curve(name=name, degree=1, point=[(0, 0, 0), (0, 0, height)])

    angle = 2.0 * math.pi / sides
    points = [(radius * math.cos(i * angle), radius * math.sin(i * angle), height)
              for i in range(sides + 1)]
    sign = cmds.curve(degree=1, point=points)
    signShape = cmds.listRelatives(sign, shapes=True)[0]
    cmds.parent(signShape, pole, relative=True, shape=True)
    cmds.delete(sign)

    return pole


def createJointDriverControl(follicle, joint, customName=None, useStopSignShape=True):
    cmds.makeLive(none=True)
    base = customName if customName else stripNamespace(follicle)
    if not customName and base.endswith('_FOL'):
        base = base[:-len('_FOL')]

    ctrl = _stopSignCurve(base + '_jnt_CTL') if useStopSignShape else \
        cmds.circle(name=base + '_jnt_CTL', normal=(0, 0, 1), radius=0.6, constructionHistory=False)[0]

    cmds.parent(ctrl, follicle)
    cmds.setAttr(ctrl + '.translate', 0, 0, 0)
    cmds.setAttr(ctrl + '.rotate', 0, 0, 0)

    cmds.parentConstraint(ctrl, joint, maintainOffset=False)

    return ctrl

import math

import maya.cmds as cmds
import maya.api.OpenMaya as om


class FollicleRigError(Exception):
    pass


# ── naming helpers ────────────────────────────────────────────────────────────

def stripNamespace(name):
    short = name.split('|')[-1]
    return short.rsplit(':', 1)[-1]


def resolveBaseName(sourceNode, customName=None):
    '''
    Returns the base name to build follicle/joint names from.
    customName always wins; otherwise derive from sourceNode
    (the surface for NURBS/poly modes, the curve for curve-on-surface mode).
    '''
    if customName:
        return customName
    return stripNamespace(sourceNode)


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


# ── follicle + joint creation ─────────────────────────────────────────────────

def createFollicle(surface, u, v, name):
    '''
    Build a follicle on surface at parameterU/V (u, v), wired up the same way
    Maya's own Hair tool wires one, then renamed to <name>_FOL / <name>_FOLShape.
    Returns the follicle transform name.
    '''
    surfaceShape = getSurfaceShape(surface)
    shapeType = cmds.nodeType(surfaceShape)

    folShape = cmds.createNode('follicle')
    folXform = cmds.listRelatives(folShape, parent=True)[0]

    if shapeType == 'nurbsSurface':
        cmds.connectAttr(surfaceShape + '.local', folShape + '.inputSurface')
    else:
        cmds.connectAttr(surfaceShape + '.outMesh', folShape + '.inputMesh')

    cmds.connectAttr(surfaceShape + '.worldMatrix[0]', folShape + '.inputWorldMatrix')
    cmds.connectAttr(folShape + '.outTranslate', folXform + '.translate')
    cmds.connectAttr(folShape + '.outRotate', folXform + '.rotate')

    cmds.setAttr(folShape + '.parameterU', u)
    cmds.setAttr(folShape + '.parameterV', v)

    folXform = cmds.rename(folXform, name + '_FOL')
    folShape = cmds.listRelatives(folXform, shapes=True)[0]
    cmds.rename(folShape, name + '_FOLShape')

    return folXform


def createJointUnderFollicle(follicle, name):
    '''
    Creates a joint, parents it under follicle and zeroes its transforms so it
    sits exactly on the follicle's pivot. Returns the joint name.
    '''
    cmds.select(clear=True)
    joint = cmds.joint(name=name + '_JNT')
    cmds.parent(joint, follicle)
    for attr in ('translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ',
                 'jointOrientX', 'jointOrientY', 'jointOrientZ'):
        cmds.setAttr(joint + '.' + attr, 0)
    return joint


def nurbsGridUVs(uCount, vCount):
    '''
    Evenly spaced (u, v) grid across the full 0-1 surface range, edge to edge,
    in row-major order (each V row scanned left-to-right across U).
    '''
    if uCount < 1 or vCount < 1:
        raise FollicleRigError('U and V counts must each be at least 1')

    def steps(count):
        if count == 1:
            return [0.5]
        return [i / float(count - 1) for i in range(count)]

    uValues = steps(uCount)
    vValues = steps(vCount)

    return [(u, v) for v in vValues for u in uValues]


def createNurbsGridFollicles(surface, uCount, vCount, customName=None):
    '''
    Builds a follicle + driven joint grid (uCount x vCount) across a NURBS
    surface, named from the surface unless customName is given.
    '''
    surfaceShape = getSurfaceShape(surface)
    if cmds.nodeType(surfaceShape) != 'nurbsSurface':
        raise FollicleRigError(surface + ' is not a NURBS surface')

    uvList = nurbsGridUVs(uCount, vCount)
    return buildFollicleRig(surface, uvList, customName=customName)


def getVertexUV(vertex):
    '''
    Returns the (u, v) for a single polygon vertex. If the vertex sits on a
    UV seam and maps to more than one UV, the first is used.
    '''
    uvs = cmds.ls(cmds.polyListComponentConversion(vertex, fromVertex=True, toUV=True), flatten=True)
    if not uvs:
        raise FollicleRigError(vertex + ' has no UVs - mesh must be UV mapped to place follicles on vertices')
    return tuple(cmds.polyEditUV(uvs[0], query=True))


def createPolyVertexFollicles(vertices, customName=None):
    '''
    Builds a follicle + driven joint at each selected polygon vertex's UV
    location, in selection order. All vertices must belong to the same mesh.
    Named from the mesh unless customName is given.
    '''
    if not vertices:
        raise FollicleRigError('No vertices selected')

    meshes = sorted(set(vtx.split('.')[0] for vtx in vertices))
    if len(meshes) > 1:
        raise FollicleRigError('Selected vertices belong to more than one mesh: ' + ', '.join(meshes))

    uvList = [getVertexUV(vtx) for vtx in vertices]
    return buildFollicleRig(meshes[0], uvList, customName=customName)


def getCurveShape(node):
    if cmds.nodeType(node) == 'nurbsCurve':
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == 'nurbsCurve':
            return shape
    raise FollicleRigError(node + ' has no nurbsCurve shape')


def getCurveCVPositions(curve):
    '''Returns world-space CV positions of curve, in CV order.'''
    curveShape = getCurveShape(curve)
    cvCount = cmds.getAttr(curveShape + '.degree') + cmds.getAttr(curveShape + '.spans')
    return [tuple(cmds.xform('%s.cv[%d]' % (curveShape, i), q=True, ws=True, t=True))
            for i in range(cvCount)]


def _transformPoint(transform, attr, point):
    matrix = om.MMatrix(cmds.getAttr(transform + '.' + attr))
    p = om.MPoint(point[0], point[1], point[2]) * matrix
    return (p.x, p.y, p.z)


def closestUVOnSurface(surface, point):
    '''
    One-shot closest-point query: builds a closestPointOnSurface/Mesh node,
    reads back (u, v) and the distance from world-space `point` to that
    closest point, then deletes the node immediately.

    This is deliberately a build-time-only, one-shot use of these nodes -
    left connected and evaluated every frame they are an iterative search
    that can jitter near seams/poles and cost real performance, which is why
    they are not used for the live UV-driver control rig (see [[Tool 5]]).
    Here the node exists just long enough to answer one question and is gone.

    closestPointOnSurface has no inputMatrix (it works in the surface's own
    object space), while closestPointOnMesh does (it works in world space) -
    so the NURBS path converts the query point into object space and the
    result back out to world space for the distance check.
    '''
    surfaceShape = getSurfaceShape(surface)
    shapeType = cmds.nodeType(surfaceShape)

    if shapeType == 'nurbsSurface':
        node = cmds.createNode('closestPointOnSurface')
        cmds.connectAttr(surfaceShape + '.local', node + '.inputSurface')
        cmds.setAttr(node + '.inPosition', *_transformPoint(surfaceShape, 'worldInverseMatrix[0]', point))
        u = cmds.getAttr(node + '.parameterU')
        v = cmds.getAttr(node + '.parameterV')
        closest = _transformPoint(surfaceShape, 'worldMatrix[0]', cmds.getAttr(node + '.position')[0])
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


def createCurveOnSurfaceFollicles(curve, surface, customName=None, tolerance=0.01):
    '''
    Walks curve's CVs in order, finds each one's closest UV on surface
    (one-shot query - see closestUVOnSurface), and builds a follicle + driven
    joint at each, in CV order. Named from the curve (not the surface) unless
    customName is given - so a hand-drawn "battWingPath" curve produces
    battWingPath_00_FOL, battWingPath_01_FOL, etc.

    Warns (without failing) if any CV sits farther than `tolerance` from the
    surface - usually a sign the curve was not drawn live/snapped onto it.
    '''
    positions = getCurveCVPositions(curve)
    if not positions:
        raise FollicleRigError(curve + ' has no CVs')

    uvList = []
    for index, point in enumerate(positions):
        uv, distance = closestUVOnSurface(surface, point)
        if distance > tolerance:
            cmds.warning('%s.cv[%d] is %.4f units from %s - was the curve drawn live on the surface?'
                         % (curve, index, distance, surface))
        uvList.append(uv)

    return buildFollicleRig(surface, uvList, customName=customName, nameSource=curve)


def buildFollicleRig(surface, uvList, customName=None, nameSource=None):
    '''
    Creates one follicle + driven joint per (u, v) pair in uvList.

    surface    - NURBS surface or polygon mesh (transform or shape) to attach to
    uvList     - list of (u, v) tuples, normalized 0-1 parameter coordinates
    customName - optional user override for the base name
    nameSource - node to derive the default base name from when customName is
                 not given (defaults to surface; pass the curve in curve-on-
                 surface mode so follicles are named from the curve, not the surface)

    Returns a list of (follicle, joint) name pairs, in uvList order.
    '''
    base = resolveBaseName(nameSource if nameSource else surface, customName)

    pairs = []
    for index, (u, v) in enumerate(uvList):
        follicleName = base + '_' + str(index).zfill(2)
        follicle = createFollicle(surface, u, v, follicleName)
        joint = createJointUnderFollicle(follicle, follicleName)
        pairs.append((follicle, joint))

    return pairs


# ── UV-driver control ─────────────────────────────────────────────────────────
#
# Fixed convention: control.translateX always drives parameterU and
# control.translateY always drives parameterV; translateZ is left open so the
# control can be lifted off the surface. This matches a follicle transform's
# natural local-axis alignment - local X along the surface's U-tangent, Y
# along its V-tangent, Z along its normal (see [[createUVDriverControl]]) -
# which is why the control is built flat in the XY plane (normal +Z).

def _fourArrowCurve(name):
    '''
    A flat 4-pointed arrow/cross outline in the XY plane (normal +Z) - lies
    flat in the surface's tangent plane once parented under its anchor
    follicle, where local X = U-tangent and local Y = V-tangent.
    '''
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
    '''
    One-shot finite-difference calibration: builds a temporary follicle offset
    by `epsilon` in parameter space along `axis` ('u' or 'v') from (u, v) -
    backing off from the far edge instead when u/v sits within epsilon of 1.0
    - measures the world-space distance from `anchorPos` to it, and divides by
    epsilon to estimate "world units moved per unit change in U or V" at that
    point: exactly the slope the linear remap chain needs so a given drag
    distance maps to a consistent parameter change. Built, queried and deleted
    immediately - a build-time measurement, not a live node, in the same
    one-shot spirit as [[closestUVOnSurface]].

    Sampling through createFollicle (rather than a NURBS-only node such as
    pointOnSurfaceInfo, which has no mesh equivalent) means this works
    identically for NURBS surfaces and polygon meshes.
    '''
    value = u if axis == 'u' else v
    delta = epsilon if value + epsilon <= 1.0 else -epsilon
    sampleU, sampleV = (u + delta, v) if axis == 'u' else (u, v + delta)

    probe = createFollicle(surface, sampleU, sampleV, '_uvCalibrationProbe')
    probePos = cmds.xform(probe, query=True, worldSpace=True, translation=True)
    cmds.delete(probe)

    distance = sum((a - b) ** 2 for a, b in zip(anchorPos, probePos)) ** 0.5
    return max(distance / abs(delta), 1e-6)


def _linearUVChain(controlAttr, axisSpan, startingValue, sensitivityAttr, baseName, axisLabel):
    '''
    Calibrated linear remap chain for one axis. The control sits at local
    origin under its anchor follicle (see [[createUVDriverControl]]), so its
    rest translate is exactly zero and the control's raw value is usable
    directly - no delta-from-rest subtraction needed:

        multiplyDivide (x sensitivity)
          -> multiplyDivide (/ axisSpan - world units per unit U or V at the
             follicle's location, measured via [[_calibrationSpan]])
          -> plusMinusAverage (+ starting U or V)
          -> clamp (0-1)

    Returns the clamp output attribute, ready to drive follicle.parameterU/V.
    '''
    mdSensitivity = cmds.createNode('multiplyDivide', name=baseName + '_' + axisLabel + 'Sens_MDV')
    cmds.connectAttr(controlAttr, mdSensitivity + '.input1X')
    cmds.connectAttr(sensitivityAttr, mdSensitivity + '.input2X')

    mdSpan = cmds.createNode('multiplyDivide', name=baseName + '_' + axisLabel + 'Span_MDV')
    cmds.setAttr(mdSpan + '.operation', 2)  # divide
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
    Builds a control whose translateX/translateY drive a follicle's
    parameterU/parameterV through a calibrated linear remap, so dragging the
    control across surfaces of very different scales still feels 1:1 -
    consistent, not racing ahead of or lagging behind the follicle.
    translateX -> U, translateY -> V always; translateZ is left free so the
    control can be lifted off the surface.

    Orientation is solved by building a second, static "anchor" follicle at
    the driven follicle's exact (u, v) and parenting the control under it at
    local origin. A follicle transform is always oriented with local X along
    the surface's U-tangent, Y along its V-tangent and Z along its normal -
    Maya's own mechanism for keeping groomed hair aligned to a surface as it
    deforms - so the anchor hands the control that frame for free, correctly
    aligned regardless of the surface's own object-space axis layout or world
    orientation. Nothing connects to the anchor's outputs; it exists purely to
    hold this frame, and because the control sits at its local origin, the
    control's rest translate is exactly (0, 0, 0) - which is what lets
    [[_linearUVChain]] use the control's raw translate without first
    subtracting a rest value.

    Per driven axis: multiplyDivide(x sensitivity) -> multiplyDivide(/ a
    calibration span - world units moved per unit change in U or V at the
    follicle's location, measured once at build time via [[_calibrationSpan]])
    -> plusMinusAverage(+ the follicle's starting U or V) -> clamp(0-1) ->
    follicle.parameterU/V. See [[closestUVOnSurface]] for why a per-frame
    closest-point approach was rejected instead (jitter + cost at runtime).

    Rotates are locked, hidden and unkeyable; translateZ is left open.
    `sensitivity` is added as a non-keyable, channel-box-only rigger tuning
    knob - lock and hide it once tuned, before handing off to animators.
    '''
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

    return ctrl


# ── joint-driver control ──────────────────────────────────────────────────────
#
# The chain in a rig like a bat wing: surface drives follicle -> follicle
# drives joint -> joint drives character (e.g. a NURBS wing membrane skinned
# to the rig's wing joints, with follicles scattered across its surface and
# the joints under those follicles managing the membrane's secondary motion).
# This control sits between the follicle and the joint, giving the animator
# extra translate/rotate offset at very low cost - both control and joint
# share the follicle as their parent and coincide with its pivot at rest, so a
# parent constraint simply mirrors the control's local transform onto the
# joint. No remap network, no calibration - nothing fancy happening at all.

def _stopSignCurve(name, height=2.0, radius=0.6, sides=8):
    '''
    A "stop sign on a pole": a straight line from the local origin up along
    local Z (the surface normal once parented under a follicle), capped with
    an octagon lying flat across the top - tall enough to lift it clear of the
    surface and large enough to be an easy, unambiguous click target. Built as
    two curve shapes parented under one transform, so either part selects the
    control.
    '''
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
    '''
    Builds a control that drives `joint` through a parent constraint, parented
    as a sibling of the joint under `follicle` and sitting at its local origin
    - so at rest, control and joint coincide exactly with the follicle's pivot
    and orientation, and the constraint reduces to a plain mirror of the
    control's local transform onto the joint's. All channels (translate and
    rotate) are left open, keyable and unlocked - there is no calibration math
    here, the animator just grabs the control and moves/rotates it.
    '''
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

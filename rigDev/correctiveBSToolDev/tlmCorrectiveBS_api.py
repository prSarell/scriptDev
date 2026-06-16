import maya.cmds as cmds


class CorrectiveBSError(Exception):
    pass


# ── mesh helpers ──────────────────────────────────────────────────────────────

def getMeshShape(node):
    if cmds.nodeType(node) == 'mesh':
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == 'mesh':
            return shape
    raise CorrectiveBSError(node + ' has no mesh shape')


def getSkinCluster(mesh):
    shape = getMeshShape(mesh)
    for node in (cmds.listHistory(shape, pruneDagObjects=True) or []):
        if cmds.nodeType(node) == 'skinCluster':
            return node
    return None


def getBlendShapeNode(mesh):
    short = mesh.split('|')[-1].split(':')[-1]
    candidates = cmds.ls(short + '_correctiveBS', type='blendShape') or []
    return candidates[0] if candidates else None


# ── vertex position helpers ───────────────────────────────────────────────────

def getVertexPositions(mesh, worldSpace=True):
    vtx_count = cmds.polyEvaluate(mesh, vertex=True)
    return [
        tuple(cmds.xform('%s.vtx[%d]' % (mesh, i),
                         query=True, worldSpace=worldSpace, translation=True))
        for i in range(vtx_count)
    ]


def setVertexPositions(mesh, positions, worldSpace=True):
    for i, pos in enumerate(positions):
        cmds.xform('%s.vtx[%d]' % (mesh, i),
                   worldSpace=worldSpace, translation=pos)


# ── deformer management ───────────────────────────────────────────────────────

_DEFORMER_TYPES = frozenset((
    'skinCluster', 'blendShape', 'tweak', 'cluster',
    'wire', 'nonLinear', 'deltaMush', 'softMod',
))


def _muteDeformers(mesh):
    """Mute all deformers in mesh history. Returns {node: envelope} for restore."""
    shape = getMeshShape(mesh)
    history = cmds.listHistory(shape, pruneDagObjects=True) or []
    envelopes = {}
    for node in history:
        if cmds.nodeType(node) in _DEFORMER_TYPES:
            try:
                envelopes[node] = cmds.getAttr(node + '.envelope')
                cmds.setAttr(node + '.envelope', 0)
            except Exception:
                pass
    return envelopes


def _restoreDeformers(envelopes):
    for node, val in envelopes.items():
        try:
            cmds.setAttr(node + '.envelope', val)
        except Exception:
            pass


# ── deformation stack inspection ─────────────────────────────────────────────

def getDeformationStack(mesh):
    """
    Return deformer nodes in processing order (original geometry → output).
    Returns list of (node_name, node_type) tuples.
    """
    shape = getMeshShape(mesh)
    history = cmds.listHistory(shape, pruneDagObjects=True) or []
    return [
        (node, cmds.nodeType(node))
        for node in reversed(history)
        if cmds.nodeType(node) in _DEFORMER_TYPES
    ]


# ── blendshape state capture ──────────────────────────────────────────────────

def captureBlendShapeStates(mesh):
    """
    Return list of (attr_path, value) for all non-zero blendShape weights on
    the mesh, excluding the corrective node itself.
    Captured at the problem pose and used later to wire the SDK driver.
    """
    shape = getMeshShape(mesh)
    history = cmds.listHistory(shape, pruneDagObjects=True) or []
    corrective_node = getBlendShapeNode(mesh)

    states = []
    for node in history:
        if cmds.nodeType(node) != 'blendShape':
            continue
        if node == corrective_node:
            continue
        weight_count = cmds.blendShape(node, query=True, weightCount=True) or 0
        for idx in range(weight_count):
            attr = '%s.weight[%d]' % (node, idx)
            val = cmds.getAttr(attr)
            if abs(val) > 1e-4:
                states.append((attr, val))

    return states


# ── pose capture ──────────────────────────────────────────────────────────────

def startCorrection(mesh, target_name):
    """
    Step 1. Call with the rig at the problem pose.

    Creates two clean duplicates of the deformed mesh:
      dup_b  — stays in the mesh's parent hierarchy, hidden. Reference snapshot.
      dup_a  — unparented to world, visible. Artist sculpts on this.

    Also captures active blendShape weights for SDK wiring.
    Returns (dup_a, dup_b, bs_states).
    """
    if not cmds.objExists(mesh):
        raise CorrectiveBSError('Mesh not found: ' + mesh)
    getMeshShape(mesh)

    bs_states = captureBlendShapeStates(mesh)

    def _cleanDup(name):
        dup = cmds.duplicate(mesh, name=name)[0]
        cmds.delete(dup, constructionHistory=True)
        for s in (cmds.listRelatives(dup, shapes=True) or []):
            if cmds.getAttr(s + '.intermediateObject'):
                cmds.delete(s)
        return dup

    # DupB: hidden reference, stays in hierarchy so it shares the parent frame
    dup_b = _cleanDup(target_name + '_poseRef')
    cmds.setAttr(dup_b + '.visibility', 0)
    cmds.addAttr(dup_b, longName='correctiveFrame', attributeType='long')
    cmds.setAttr(dup_b + '.correctiveFrame', int(cmds.currentTime(query=True)))

    # DupA: sculpt target, unparented to world, transforms unlocked
    dup_a = _cleanDup(target_name + '_sculpt')
    if cmds.listRelatives(dup_a, parent=True):
        dup_a = cmds.parent(dup_a, world=True)[0]
    for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
        cmds.setAttr(dup_a + '.' + attr, lock=False)

    return dup_a, dup_b, bs_states


# ── delta extraction ──────────────────────────────────────────────────────────

def extractDelta(mesh, sculpted_mesh, posed_mesh):
    """
    Compute corrective blendshape target vertex positions.

      T[i] = Q[i] + (S[i] - P[i])

      Q[i]  pre-skin vertex — skin cluster muted, blendShapes active (world space)
      S[i]  sculpted vertex from dup_a (LOCAL space — invariant to user translation)
      P[i]  posed snapshot vertex from dup_b (world space, skin included)

    S is read in local space so that moving dup_a away from the rig for
    visibility does not corrupt the delta.  dup_a was unparented to world
    origin at creation, so its local frame equals the original world frame;
    the user-applied translate lives only on the transform node and vanishes
    when we read vertices locally.  P is still read in world space because
    dup_b sits in the rig hierarchy and its local == world at capture time.
    (S - P) therefore isolates the pure sculpt correction.
    """
    sculpted_pos = getVertexPositions(sculpted_mesh, worldSpace=False)
    posed_pos    = getVertexPositions(posed_mesh,    worldSpace=True)
    vtx_count    = cmds.polyEvaluate(mesh, vertex=True)

    if len(sculpted_pos) != vtx_count:
        raise CorrectiveBSError(
            'Vertex count mismatch: mesh %d, sculpt %d' % (vtx_count, len(sculpted_pos)))
    if len(posed_pos) != vtx_count:
        raise CorrectiveBSError(
            'Vertex count mismatch: mesh %d, pose ref %d' % (vtx_count, len(posed_pos)))

    sc = getSkinCluster(mesh)
    if sc:
        old_env = cmds.getAttr(sc + '.envelope')
        cmds.setAttr(sc + '.envelope', 0)
    try:
        pre_skin_pos = getVertexPositions(mesh, worldSpace=True)
    finally:
        if sc:
            cmds.setAttr(sc + '.envelope', old_env)

    return [
        (q[0] + s[0] - p[0],
         q[1] + s[1] - p[1],
         q[2] + s[2] - p[2])
        for q, s, p in zip(pre_skin_pos, sculpted_pos, posed_pos)
    ]


# ── blendshape target building ────────────────────────────────────────────────

def _buildTargetMesh(mesh, target_positions, name):
    """
    Duplicate mesh at bind pose (all deformers muted) and set vertices to
    target_positions (world space). Caller is responsible for deleting after use.
    """
    envelopes = _muteDeformers(mesh)
    try:
        tmp = cmds.duplicate(mesh, name=name)[0]
        cmds.delete(tmp, constructionHistory=True)
        for s in (cmds.listRelatives(tmp, shapes=True) or []):
            if cmds.getAttr(s + '.intermediateObject'):
                cmds.delete(s)
    finally:
        _restoreDeformers(envelopes)

    setVertexPositions(tmp, target_positions, worldSpace=True)
    return tmp


# ── deformer insertion ────────────────────────────────────────────────────────

def _insertBeforeSkin(bs_node, sc):
    """
    Rewire bs_node so it sits immediately upstream of sc.

    Maya always appends a new blendShape AFTER the last deformer (at the shape
    input), so after cmds.blendShape() the chain is:

        ... → skinCluster → bs_node → outputShape

    We manually swap it to:

        ... → bs_node → skinCluster → outputShape
    """
    a_plugs = cmds.listConnections(
        bs_node + '.ip[0].ig', source=True, destination=False, plugs=True) or []
    b_plugs = cmds.listConnections(
        sc + '.ip[0].ig', source=True, destination=False, plugs=True) or []
    c_plugs = cmds.listConnections(
        bs_node + '.og[0]', source=False, destination=True, plugs=True) or []

    if not (a_plugs and b_plugs and c_plugs):
        return

    a = a_plugs[0]  # skinCluster.og[0]
    b = b_plugs[0]  # whatever fed into skinCluster (e.g. blendShape1.og[0])
    c = c_plugs[0]  # outputShape.inMesh

    cmds.disconnectAttr(a, bs_node + '.ip[0].ig')
    cmds.disconnectAttr(b, sc + '.ip[0].ig')
    cmds.disconnectAttr(bs_node + '.og[0]', c)

    cmds.connectAttr(b, bs_node + '.ip[0].ig', force=True)
    cmds.connectAttr(bs_node + '.og[0]', sc + '.ip[0].ig', force=True)
    cmds.connectAttr(a, c, force=True)


# ── blendshape operations ─────────────────────────────────────────────────────

def addCorrectiveTarget(mesh, target_positions, target_name):
    """
    Add a corrective blendshape target. Creates the blendShape node pre-skin
    if one doesn't exist. Returns (blendshape_node, target_index).
    """
    bs_node  = getBlendShapeNode(mesh)
    tmp_mesh = _buildTargetMesh(mesh, target_positions, target_name + '_tmp')

    try:
        if bs_node is None:
            sc    = getSkinCluster(mesh)
            short = mesh.split('|')[-1].split(':')[-1]
            bs_node      = cmds.blendShape(tmp_mesh, mesh,
                                           name=short + '_correctiveBS',
                                           origin='local')[0]
            target_index = 0
            if sc:
                _insertBeforeSkin(bs_node, sc)
                # The delta was computed while the BS was still post-skin.
                # Re-add the target now that the BS is pre-skin so Maya
                # recomputes the delta against the correct pre-skin input.
                cmds.blendShape(bs_node, edit=True,
                                target=(mesh, target_index, tmp_mesh, 1.0))
        else:
            target_index = cmds.blendShape(bs_node, query=True, weightCount=True) or 0
            cmds.blendShape(bs_node, edit=True,
                            target=(mesh, target_index, tmp_mesh, 1.0))
        cmds.aliasAttr(target_name, '%s.weight[%d]' % (bs_node, target_index))
    finally:
        if cmds.objExists(tmp_mesh):
            cmds.delete(tmp_mesh)

    return bs_node, target_index


def updateCorrectiveTarget(mesh, target_name, target_positions):
    """Replace vertex data for an existing target without touching SDK wiring."""
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        raise CorrectiveBSError(mesh + ' has no corrective blendShape node')
    target_index = _resolveTargetIndex(bs_node, target_name)
    tmp_mesh     = _buildTargetMesh(mesh, target_positions, target_name + '_tmp')
    try:
        cmds.blendShape(bs_node, edit=True,
                        target=(mesh, target_index, tmp_mesh, 1.0))
    finally:
        if cmds.objExists(tmp_mesh):
            cmds.delete(tmp_mesh)


def listCorrectiveTargets(mesh):
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        return []
    aliases = cmds.aliasAttr(bs_node, query=True) or []
    return [aliases[k] for k in range(0, len(aliases), 2)]


def removeCorrectiveTarget(mesh, target_name):
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        raise CorrectiveBSError(mesh + ' has no corrective blendShape node')
    target_index = _resolveTargetIndex(bs_node, target_name)
    cmds.blendShape(bs_node, edit=True,
                    remove=True,
                    target=(mesh, target_index, mesh, 1.0))


def _resolveTargetIndex(bs_node, target_name):
    aliases = cmds.aliasAttr(bs_node, query=True) or []
    for k in range(0, len(aliases), 2):
        if aliases[k] == target_name:
            return int(aliases[k + 1].split('[')[1].rstrip(']'))
    raise CorrectiveBSError(
        'Target "%s" not found on %s' % (target_name, bs_node))


# ── SDK driver wiring ─────────────────────────────────────────────────────────

def wireSDKDrivers(bs_node, target_index, bs_states):
    """
    Wire a Set Driven Key from the dominant blendShape weight in bs_states
    to the corrective weight. bs_states is the list returned by startCorrection().

    Uses driverValue/value flags so setAttr on the driver is never needed —
    safe even if the driver is already connected to an animation curve.
    """
    if not bs_states:
        return

    driven_attr       = '%s.weight[%d]' % (bs_node, target_index)
    driver_attr, peak = max(bs_states, key=lambda x: x[1])

    cmds.setDrivenKeyframe(driven_attr,
                            currentDriver=driver_attr,
                            driverValue=0.0,
                            value=0.0)
    cmds.setDrivenKeyframe(driven_attr,
                            currentDriver=driver_attr,
                            driverValue=peak,
                            value=1.0)

    curves = cmds.listConnections(driven_attr, source=True, type='animCurveUU') or []
    if curves:
        cmds.keyTangent(curves[0], inTangentType='flat', outTangentType='flat')


# ── high-level operations ─────────────────────────────────────────────────────

def bakeCorrection(mesh, sculpted_mesh, posed_mesh, target_name, bs_states):
    """
    Step 2. Call with the rig still at the same pose as startCorrection().

    Extracts the delta, creates the blendShape target, wires the SDK.
    Returns (blendshape_node, target_index).
    """
    for obj in (mesh, sculpted_mesh, posed_mesh):
        if not cmds.objExists(obj):
            raise CorrectiveBSError('Object not found: ' + obj)
        getMeshShape(obj)

    target_positions      = extractDelta(mesh, sculpted_mesh, posed_mesh)
    bs_node, target_index = addCorrectiveTarget(mesh, target_positions, target_name)
    wireSDKDrivers(bs_node, target_index, bs_states)

    return bs_node, target_index

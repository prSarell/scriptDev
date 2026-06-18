import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2


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


# ── skin matrix computation ──────────────────────────────────────────────────

def _computeSkinMatrices(mesh):
    """
    Per-vertex composite skin matrix via OpenMaya 2.

    For vertex i:  W_i = Σ( weight_ij * bindPreMatrix_j * worldMatrix_j )

    Returns list of MMatrix (one per vertex), or None if no skin cluster.
    """
    sc = getSkinCluster(mesh)
    if sc is None:
        return None

    shape = getMeshShape(mesh)

    sel = om2.MSelectionList()
    sel.add(sc)
    fn_skin = oma2.MFnSkinCluster(sel.getDependNode(0))

    sel_mesh = om2.MSelectionList()
    sel_mesh.add(shape)
    mesh_dag = sel_mesh.getDagPath(0)

    influences = fn_skin.influenceObjects()
    num_inf = len(influences)

    bind_pre = []
    for i in range(num_inf):
        mat = cmds.getAttr('%s.bindPreMatrix[%d]' % (sc, i))
        bind_pre.append(om2.MMatrix(mat))

    world_mats = [inf.inclusiveMatrix() for inf in influences]

    joint_flat = []
    for j in range(num_inf):
        jm = bind_pre[j] * world_mats[j]
        flat = []
        for r in range(4):
            for c in range(4):
                flat.append(jm.getElement(r, c))
        joint_flat.append(flat)

    vtx_count = cmds.polyEvaluate(mesh, vertex=True)
    fn_comp = om2.MFnSingleIndexedComponent()
    comp_obj = fn_comp.create(om2.MFn.kMeshVertComponent)
    fn_comp.setCompleteData(vtx_count)

    weights, inf_count = fn_skin.getWeights(mesh_dag, comp_obj)

    matrices = []
    for vi in range(vtx_count):
        result = [0.0] * 16
        base = vi * inf_count
        for ji in range(inf_count):
            w = weights[base + ji]
            if w < 1e-10:
                continue
            jf = joint_flat[ji]
            for k in range(16):
                result[k] += w * jf[k]
        matrices.append(om2.MMatrix(result))

    return matrices


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


# ── driver auto-detection ────────────────────────────────────────────────────

def _getJointDrivers(mesh, threshold=1.0):
    """Return skin-influence joints whose rotations are off bind pose."""
    sc = getSkinCluster(mesh)
    if sc is None:
        return []
    influences = cmds.skinCluster(sc, query=True, influence=True) or []
    drivers = []
    for joint in influences:
        if cmds.nodeType(joint) != 'joint':
            continue
        for axis in ('rotateX', 'rotateY', 'rotateZ'):
            val = cmds.getAttr(joint + '.' + axis)
            if abs(val) > threshold:
                drivers.append((joint + '.' + axis, val))
    drivers.sort(key=lambda x: abs(x[1]), reverse=True)
    return drivers


def detectDriverMode(mesh):
    """
    Auto-detect what's driving the current pose.
    Returns (mode, data):
      ('blendshape', [(attr, value), ...])
      ('joint', [(attr, value), ...])
      ('attribute', None)
    """
    bs_states = captureBlendShapeStates(mesh)
    active_bs = [(attr, val) for attr, val in bs_states if abs(val) > 1e-4]
    if active_bs:
        return 'blendshape', active_bs

    joint_drivers = _getJointDrivers(mesh)
    if joint_drivers:
        return 'joint', joint_drivers

    return 'attribute', None


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

def extractDelta(mesh, sculpted_mesh):
    """
    Compute corrective blendshape target positions via per-vertex
    skin-matrix inversion.

    For each vertex i the skin cluster computes:
      world[i] = preskin[i] * W_i
    where W_i = Σ( weight_ij * bindPreMatrix_j * worldMatrix_j )

    Inverting gives the pre-skin position that produces a desired world
    output:  preskin_target[i] = sculpted[i] * W_i⁻¹

    This is exact regardless of joint rotation.

    The sculpt mesh is read in local space so that moving it away from
    the rig for visibility does not corrupt the result (dup_a was
    unparented to world origin at creation).

    Falls back to raw sculpted positions when no skin cluster exists.
    """
    sculpted_pos = getVertexPositions(sculpted_mesh, worldSpace=False)
    vtx_count    = cmds.polyEvaluate(mesh, vertex=True)

    if len(sculpted_pos) != vtx_count:
        raise CorrectiveBSError(
            'Vertex count mismatch: mesh %d, sculpt %d' % (vtx_count, len(sculpted_pos)))

    matrices = _computeSkinMatrices(mesh)
    if matrices is None:
        return sculpted_pos

    result = []
    for i, (sx, sy, sz) in enumerate(sculpted_pos):
        pt = om2.MPoint(sx, sy, sz) * matrices[i].inverse()
        result.append((pt.x, pt.y, pt.z))

    return result


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
            bs_node = cmds.blendShape(mesh, name=short + '_correctiveBS',
                                      origin='local')[0]
            target_index = 0
            if sc:
                _insertBeforeSkin(bs_node, sc)
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


def updateCorrectiveTarget(mesh, target_name, sculpted_mesh):
    """Replace vertex data for an existing target without touching SDK wiring."""
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        raise CorrectiveBSError(mesh + ' has no corrective blendShape node')
    target_index = _resolveTargetIndex(bs_node, target_name)
    _writeTargetDeltas(mesh, bs_node, target_index, sculpted_mesh)


def _writeTargetDeltas(mesh, bs_node, target_index, sculpted_mesh):
    """
    Write corrective deltas into the blendShape node's ipt/ict using
    skin-matrix inversion.

    For each vertex the stored delta is:
      delta[i] = W_i⁻¹ * sculpted[i]  -  base[i]

    where base is the mesh with all deformers muted (the blendShape's
    upstream input at bind pose).

    Falls back to sculpted_local - base when no skin cluster exists.
    """
    sculpted_pos = getVertexPositions(sculpted_mesh, worldSpace=False)

    matrices = _computeSkinMatrices(mesh)

    sc = getSkinCluster(mesh)
    saved = {}
    if sc:
        saved[sc] = cmds.getAttr(sc + '.envelope')
        cmds.setAttr(sc + '.envelope', 0)
    saved[bs_node] = cmds.getAttr(bs_node + '.envelope')
    cmds.setAttr(bs_node + '.envelope', 0)
    try:
        base_pos = getVertexPositions(mesh, worldSpace=True)
    finally:
        for node, val in saved.items():
            cmds.setAttr(node + '.envelope', val)

    ipt_attr = (bs_node + '.inputTarget[0].inputTargetGroup[%d]'
                '.inputTargetItem[6000].inputPointsTarget') % target_index
    ict_attr = (bs_node + '.inputTarget[0].inputTargetGroup[%d]'
                '.inputTargetItem[6000].inputComponentsTarget') % target_index

    threshold = 1e-5
    deltas     = []
    components = []
    for i, (s, b) in enumerate(zip(sculpted_pos, base_pos)):
        if matrices is not None:
            pt = om2.MPoint(s[0], s[1], s[2]) * matrices[i].inverse()
            tx, ty, tz = pt.x, pt.y, pt.z
        else:
            tx, ty, tz = s

        dx, dy, dz = tx - b[0], ty - b[1], tz - b[2]
        if abs(dx) > threshold or abs(dy) > threshold or abs(dz) > threshold:
            deltas.append((dx, dy, dz))
            components.append(i)

    n = len(deltas)
    if n:
        pts_str  = ' '.join('%.10g %.10g %.10g 1' % d for d in deltas)
        comp_str = ' '.join('"vtx[%d]"' % i for i in components)
        mel.eval('setAttr -type "pointArray" "%s" %d %s' % (ipt_attr, n, pts_str))
        mel.eval('setAttr -type "componentList" "%s" %d %s' % (ict_attr, n, comp_str))
    else:
        mel.eval('setAttr -type "pointArray" "%s" 0' % ipt_attr)
        mel.eval('setAttr -type "componentList" "%s" 0' % ict_attr)


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

def _buildMultiDriverNetwork(bs_node, target_index, bs_states):
    """
    Build a setRange + floatMath multiply network for multi-driver face correctives.

    Each BS driver is normalised to 0-1 using a setRange node (mapping
    0→peak to 0→1), then all normalised signals are multiplied together.
    The product drives the corrective weight — it reaches 1 only when every
    driver is simultaneously at its captured value, and degrades gracefully
    when any driver backs off.
    """
    valid = [(attr, peak) for attr, peak in bs_states if abs(peak) > 1e-4]
    if not valid:
        return

    driven_attr = '%s.weight[%d]' % (bs_node, target_index)
    base        = '%s_%d' % (bs_node, target_index)

    sr_outputs = []
    for k, (driver_attr, peak) in enumerate(valid):
        sr = cmds.createNode('setRange', name='%s_sr%d' % (base, k))
        cmds.setAttr(sr + '.oldMinX', 0.0)
        cmds.setAttr(sr + '.oldMaxX', peak)
        cmds.setAttr(sr + '.minX',    0.0)
        cmds.setAttr(sr + '.maxX',    1.0)
        cmds.connectAttr(driver_attr, sr + '.valueX', force=True)
        sr_outputs.append(sr + '.outValueX')

    if len(sr_outputs) == 1:
        cmds.connectAttr(sr_outputs[0], driven_attr, force=True)
        return

    prev_out = sr_outputs[0]
    for k, sr_out in enumerate(sr_outputs[1:]):
        fm = cmds.createNode('floatMath', name='%s_fm%d' % (base, k))
        cmds.setAttr(fm + '.operation', 2)  # multiply
        cmds.connectAttr(prev_out, fm + '.floatA', force=True)
        cmds.connectAttr(sr_out,   fm + '.floatB', force=True)
        prev_out = fm + '.outFloat'

    cmds.connectAttr(prev_out, driven_attr, force=True)


def _wireCustomDriver(bs_node, target_index, driver_attr, driver_value):
    """
    Wire a single SDK from any attribute (joint rotation, control slider, etc.)
    to the corrective weight.  0→0, driver_value→1.

    Uses driverValue/value flags so setAttr on the driver is never needed —
    safe even when the driver attribute is already connected.
    """
    driven_attr = '%s.weight[%d]' % (bs_node, target_index)

    cmds.setDrivenKeyframe(driven_attr,
                           currentDriver=driver_attr,
                           driverValue=0.0,
                           value=0.0)
    cmds.setDrivenKeyframe(driven_attr,
                           currentDriver=driver_attr,
                           driverValue=driver_value,
                           value=1.0)

    curves = cmds.listConnections(driven_attr, source=True, type='animCurveUU') or []
    if curves:
        cmds.keyTangent(curves[0], inTangentType='flat', outTangentType='flat')


# ── high-level operations ─────────────────────────────────────────────────────

def bakeCorrection(mesh, sculpted_mesh, target_name,
                   bs_states=None, custom_driver_attr=None, custom_driver_value=None):
    """
    Step 2. Call with the rig still at the same pose as startCorrection().

    Driver wiring is determined by which kwargs are supplied:
      bs_states             → multi-driver setRange/multiply network (face correctives)
      custom_driver_attr    → single SDK from any attribute (joints, controls, breathing)
    Returns (blendshape_node, target_index).
    """
    for obj in (mesh, sculpted_mesh):
        if not cmds.objExists(obj):
            raise CorrectiveBSError('Object not found: ' + obj)
        getMeshShape(obj)

    target_positions      = extractDelta(mesh, sculpted_mesh)
    bs_node, target_index = addCorrectiveTarget(mesh, target_positions, target_name)

    if custom_driver_attr and custom_driver_value is not None:
        _wireCustomDriver(bs_node, target_index, custom_driver_attr, custom_driver_value)
    elif bs_states:
        _buildMultiDriverNetwork(bs_node, target_index, bs_states)

    return bs_node, target_index

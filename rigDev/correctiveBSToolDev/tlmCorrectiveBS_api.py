import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma


class CorrectiveBSError(Exception):
    pass


# ── mesh / deformer helpers ───────────────────────────────────────────────────

def getMeshShape(node):
    """Return the mesh shape node from a transform or shape."""
    if cmds.nodeType(node) == 'mesh':
        return node
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == 'mesh':
            return shape
    raise CorrectiveBSError(node + ' has no mesh shape')


def getSkinCluster(mesh):
    """Return the first skinCluster in the mesh history, or None."""
    shape = getMeshShape(mesh)
    for node in (cmds.listHistory(shape, pruneDagObjects=True) or []):
        if cmds.nodeType(node) == 'skinCluster':
            return node
    return None


def getBlendShapeNode(mesh):
    """
    Return the corrective blendShape node — the one upstream of the skinCluster
    (before it in deformation order). When history is walked upstream the
    skinCluster appears first; the corrective blendShape appears after it.
    Falls back to the first blendShape found when there is no skinCluster.
    """
    shape = getMeshShape(mesh)
    history = cmds.listHistory(shape, pruneDagObjects=True) or []
    sc_found = False
    for node in history:
        nt = cmds.nodeType(node)
        if nt == 'skinCluster':
            sc_found = True
        elif nt == 'blendShape' and sc_found:
            return node
    if not sc_found:
        for node in history:
            if cmds.nodeType(node) == 'blendShape':
                return node
    return None


def getUpstreamSkinCluster(mesh):
    """
    Return the skinCluster the corrective blendShape feeds into.
    In the corrective stack (blendShape -> skinCluster -> output) the
    skinCluster appears BEFORE the blendShape when walking history upstream,
    so the first skinCluster found is always the right one.
    """
    return getSkinCluster(mesh)


# ── vertex position helpers ───────────────────────────────────────────────────

def getVertexPositions(mesh, worldSpace=True):
    """Return all vertex positions as a list of (x, y, z) tuples."""
    vtx_count = cmds.polyEvaluate(mesh, vertex=True)
    return [
        tuple(cmds.xform('%s.vtx[%d]' % (mesh, i),
                         query=True, worldSpace=worldSpace, translation=True))
        for i in range(vtx_count)
    ]


def setVertexPositions(mesh, positions, worldSpace=True):
    """Set vertex positions on a mesh from a list of (x, y, z) tuples."""
    for i, pos in enumerate(positions):
        cmds.xform('%s.vtx[%d]' % (mesh, i),
                   worldSpace=worldSpace, translation=pos)


# ── pose capture ──────────────────────────────────────────────────────────────

def duplicatePosedMesh(mesh, name=None):
    """
    Duplicate the mesh at its current deformed state, ready for export to an
    external sculpting app. The duplicate has no history and no intermediate
    shapes — a clean mesh the student can export and sculpt on.
    Returns the name of the duplicate transform.
    """
    dup = cmds.duplicate(mesh, name=name or (mesh + '_sculptTarget'))[0]
    cmds.delete(dup, constructionHistory=True)
    for shape in (cmds.listRelatives(dup, shapes=True) or []):
        if cmds.getAttr(shape + '.intermediateObject'):
            cmds.delete(shape)
    return dup


# ── delta extraction ──────────────────────────────────────────────────────────

def _buildSkinMatrices(skin_fn, mesh_dag, vtx_count):
    """
    Pre-compute all per-vertex skin deformation matrices in one pass.
    Returns a list of om.MMatrix, one per vertex.

    Maya row-vector convention: p_deformed_ws = p_bind_ws * S
    where S = sum over influences j: w_j * bind_pre_matrix_j * joint_world_matrix_j

    bind_pre_matrix   = inverse of joint's world matrix at bind time (stored in SC)
    joint_world_matrix = joint's current world matrix
    """
    all_comp_fn = om.MFnSingleIndexedComponent()
    all_vtx = all_comp_fn.create(om.MFn.kMeshVertComponent)
    all_comp_fn.setCompleteData(vtx_count)
    all_weights, n_influences = skin_fn.getWeights(mesh_dag, all_vtx)

    influences = skin_fn.influenceObjects()
    eff_mats = [
        list(skin_fn.getBindPreMatrix(j) * influences[j].inclusiveMatrix())
        for j in range(n_influences)
    ]

    matrices = []
    for i in range(vtx_count):
        offset = i * n_influences
        accum = [0.0] * 16
        for j in range(n_influences):
            w = all_weights[offset + j]
            if w < 1e-6:
                continue
            m = eff_mats[j]
            for k in range(16):
                accum[k] += w * m[k]
        matrices.append(om.MMatrix(accum))

    return matrices


def extractDelta(mesh, sculpted_mesh):
    """
    Compute corrective blendshape target vertex positions.

    Given the skinned `mesh` at its current pose and a `sculpted_mesh`
    showing the desired corrected result at that same pose, returns a list
    of (x, y, z) world-space positions for the blendshape target.

    When a skin cluster is present each sculpted vertex is back-transformed
    through the inverse of its per-vertex skin matrix so that after skinning
    it lands exactly at the sculpted position.  When no skin cluster exists
    (e.g. a pure blendshape face rig) the sculpted positions are returned
    directly.
    """
    sc = getUpstreamSkinCluster(mesh)
    sculpted_pos = getVertexPositions(sculpted_mesh, worldSpace=True)

    if sc is None:
        return sculpted_pos

    vtx_count = cmds.polyEvaluate(mesh, vertex=True)
    if len(sculpted_pos) != vtx_count:
        raise CorrectiveBSError(
            'Vertex count mismatch: %s has %d vertices, sculpted mesh has %d'
            % (mesh, vtx_count, len(sculpted_pos)))

    sel = om.MSelectionList()
    sel.add(sc)
    skin_fn = oma.MFnSkinCluster(sel.getDependNode(0))

    sel2 = om.MSelectionList()
    sel2.add(getMeshShape(mesh))
    mesh_dag = sel2.getDagPath(0)

    skin_matrices = _buildSkinMatrices(skin_fn, mesh_dag, vtx_count)

    target_positions = []
    for i in range(vtx_count):
        sp = sculpted_pos[i]
        tp = om.MPoint(sp[0], sp[1], sp[2]) * skin_matrices[i].inverse()
        target_positions.append((tp.x, tp.y, tp.z))

    return target_positions


# ── blendshape target building ────────────────────────────────────────────────

def _getBaseMeshForTarget(mesh):
    """
    Return the mesh transform that represents the base shape for blendshape
    target creation. When a skin cluster exists this is a duplicate of the
    intermediate (pre-skin) shape so the target is in bind-pose space.
    When there is no skin cluster the mesh itself is duplicated.
    """
    sc = getSkinCluster(mesh)
    if sc is None:
        dup = cmds.duplicate(mesh)[0]
        cmds.delete(dup, constructionHistory=True)
        return dup

    all_shapes = cmds.listRelatives(mesh, shapes=True, allDescendents=False) or []
    orig_shape = None
    for s in all_shapes:
        if cmds.getAttr(s + '.intermediateObject'):
            orig_shape = s
            break

    if orig_shape is None:
        raise CorrectiveBSError('Could not find intermediate shape on ' + mesh)

    parent = cmds.listRelatives(orig_shape, parent=True)[0]
    dup = cmds.duplicate(parent)[0]
    cmds.delete(dup, constructionHistory=True)
    for s in (cmds.listRelatives(dup, shapes=True) or []):
        if cmds.getAttr(s + '.intermediateObject'):
            cmds.delete(s)
    return dup


def _buildTargetMesh(mesh, target_positions, name):
    """
    Create a temporary mesh for use as a blendshape target.
    Vertices are set to target_positions (world space).
    Caller is responsible for deleting after use.
    """
    tmp = _getBaseMeshForTarget(mesh)
    tmp = cmds.rename(tmp, name)
    setVertexPositions(tmp, target_positions, worldSpace=True)
    return tmp


# ── blendshape operations ─────────────────────────────────────────────────────

def addCorrectiveTarget(mesh, target_positions, target_name):
    """
    Add a corrective blendshape target to the mesh.
    If no blendShape node exists one is created before the skin cluster.
    Returns (blendshape_node_name, target_index).
    """
    bs_node = getBlendShapeNode(mesh)
    tmp_mesh = _buildTargetMesh(mesh, target_positions, target_name + '_tmp')

    try:
        if bs_node is None:
            sc = getSkinCluster(mesh)
            kwargs = {'before': True} if sc else {}
            result = cmds.blendShape(tmp_mesh, mesh,
                                     name=mesh + '_correctiveBS', **kwargs)
            bs_node = result[0]
            target_index = 0
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
    """
    Replace the vertex data for an existing corrective target without touching
    the blendShape node name or any SDK wiring on its weight attribute.
    """
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        raise CorrectiveBSError(mesh + ' has no blendShape node')

    target_index = _resolveTargetIndex(bs_node, target_name)
    tmp_mesh = _buildTargetMesh(mesh, target_positions, target_name + '_tmp')
    try:
        cmds.blendShape(bs_node, edit=True,
                        target=(mesh, target_index, tmp_mesh, 1.0))
    finally:
        if cmds.objExists(tmp_mesh):
            cmds.delete(tmp_mesh)


def listCorrectiveTargets(mesh):
    """Return a list of blendshape target names on the mesh, or an empty list."""
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        return []
    aliases = cmds.aliasAttr(bs_node, query=True) or []
    return [aliases[k] for k in range(0, len(aliases), 2)]


def removeCorrectiveTarget(mesh, target_name):
    """Remove a blendshape target by name."""
    bs_node = getBlendShapeNode(mesh)
    if bs_node is None:
        raise CorrectiveBSError(mesh + ' has no blendShape node')
    target_index = _resolveTargetIndex(bs_node, target_name)
    cmds.blendShape(bs_node, edit=True,
                    remove=True,
                    target=(mesh, target_index, mesh, 1.0))


def _resolveTargetIndex(bs_node, target_name):
    """Return the weight index for a named blendshape target."""
    aliases = cmds.aliasAttr(bs_node, query=True) or []
    for k in range(0, len(aliases), 2):
        if aliases[k] == target_name:
            return int(aliases[k + 1].split('[')[1].rstrip(']'))
    raise CorrectiveBSError(
        'Target "%s" not found on %s' % (target_name, bs_node))


# ── SDK driver wiring ─────────────────────────────────────────────────────────

def wireSDKDriver(bs_node, target_index, driver_attr, drive_range):
    """
    Create a Set Driven Key driving blendShape weight[target_index] from
    0 to 1 as driver_attr moves across drive_range.

    driver_attr   full attribute path, e.g. 'L_shoulder_JNT.rotateZ'
    drive_range   (start_value, end_value), e.g. (0, 90) or (0.0, 1.0)

    Flat tangents are applied at both keyframes to prevent overshoot.
    The driver attribute is reset to drive_range[0] on completion.
    """
    driven_attr = '%s.weight[%d]' % (bs_node, target_index)

    cmds.setAttr(driver_attr, drive_range[0])
    cmds.setAttr(driven_attr, 0.0)
    cmds.setDrivenKeyframe(driven_attr, currentDriver=driver_attr)

    cmds.setAttr(driver_attr, drive_range[1])
    cmds.setAttr(driven_attr, 1.0)
    cmds.setDrivenKeyframe(driven_attr, currentDriver=driver_attr)

    anim_curves = cmds.listConnections(driven_attr, source=True,
                                        type='animCurve') or []
    if anim_curves:
        cmds.keyTangent(anim_curves[0],
                        inTangentType='flat', outTangentType='flat')

    cmds.setAttr(driver_attr, drive_range[0])


# ── high-level operations ─────────────────────────────────────────────────────

def startCorrection(mesh, target_name):
    """
    Step 1 of the corrective workflow. Call this with the rig at the problem
    pose. Duplicates the deformed mesh ready for sculpting and returns the
    duplicate name.

    The returned mesh is what the student sculpts on (in Maya or externally).
    It should be passed back to bakeCorrection() once sculpting is done.
    """
    if not cmds.objExists(mesh):
        raise CorrectiveBSError('Mesh not found: ' + mesh)
    getMeshShape(mesh)
    return duplicatePosedMesh(mesh, name=target_name + '_sculpt')


def bakeCorrection(mesh, sculpted_mesh, target_name):
    """
    Step 2 of the corrective workflow. Call this with the rig still at the
    same pose as when startCorrection() was called, passing in the sculpted
    mesh. Extracts the delta, creates the blendshape target, and returns
    (blendshape_node, target_index) ready for wireSDKDriver().
    """
    if not cmds.objExists(mesh):
        raise CorrectiveBSError('Mesh not found: ' + mesh)
    if not cmds.objExists(sculpted_mesh):
        raise CorrectiveBSError('Sculpted mesh not found: ' + sculpted_mesh)
    getMeshShape(mesh)
    getMeshShape(sculpted_mesh)

    target_positions = extractDelta(mesh, sculpted_mesh)
    return addCorrectiveTarget(mesh, target_positions, target_name)

"""
dsfr_api.py — Double Skin Face Rig API
Builds a face rig using two stacked skin clusters with a blendShape layer
between them. Surface joints ride the face mesh via uvPin nodes.

Deformer stack:  SK1 (coarse skeleton)  →  blendShape  →  SK2 (surface joints)
"""

import maya.cmds as cmds


# ── Name helpers ──────────────────────────────────────────────────────────────

_LOC_SUFFIXES = ('_LOC', '_loc', '_Loc', '_locator', '_Locator')


def _base_name(node):
    short = node.split('|')[-1].rsplit(':', 1)[-1]
    for s in _LOC_SUFFIXES:
        if short.endswith(s):
            return short[:-len(s)]
    return short


# ── Mesh helpers ──────────────────────────────────────────────────────────────

def _get_shape(transform, intermediate=False):
    for s in (cmds.listRelatives(transform, shapes=True) or []):
        if bool(cmds.getAttr(s + '.intermediateObject')) == intermediate:
            return s
    return None


def _closest_uv(face_mesh, world_pos):
    shape = _get_shape(face_mesh)
    node = cmds.createNode('closestPointOnMesh')
    try:
        cmds.connectAttr(shape + '.outMesh', node + '.inMesh')
        cmds.connectAttr(shape + '.worldMatrix[0]', node + '.inputMatrix')
        cmds.setAttr(node + '.inPosition', *world_pos)
        return cmds.getAttr(node + '.parameterU'), cmds.getAttr(node + '.parameterV')
    finally:
        cmds.delete(node)


# ── Static orig mesh for uvPin.originalGeometry ───────────────────────────────

def _create_orig_mesh(face_mesh, parent_grp):
    """Hidden static duplicate — used only for uvPin UV-to-face lookups."""
    dup = cmds.duplicate(face_mesh, name=face_mesh + '_dsfrOrig')[0]
    cmds.parent(dup, parent_grp, relative=False)
    cmds.setAttr(dup + '.inheritsTransform', False)
    cmds.setAttr(dup + '.visibility', False)
    return dup


# ── uvPin node ────────────────────────────────────────────────────────────────

def _create_uvpin(face_mesh, orig_mesh):
    shape = _get_shape(face_mesh)
    orig_shape = _get_shape(orig_mesh)
    pin = cmds.createNode('uvPin', name=face_mesh + '_uvPin')
    cmds.setAttr(pin + '.normalAxis', 1)   # Y = surface normal
    cmds.setAttr(pin + '.tangentAxis', 0)  # X = U tangent
    cmds.connectAttr(shape + '.worldMesh[0]', pin + '.deformedGeometry')
    cmds.connectAttr(orig_shape + '.outMesh', pin + '.originalGeometry')
    return pin


# ── Control shape ─────────────────────────────────────────────────────────────

def _make_circle_ctrl(name, radius):
    ctl = cmds.circle(name=name, normal=(0, 1, 0), radius=radius, ch=False)[0]
    shape = cmds.listRelatives(ctl, shapes=True)[0]
    cmds.setAttr(shape + '.overrideEnabled', True)
    cmds.setAttr(shape + '.overrideColor', 17)  # yellow
    return ctl


# ── Phase 1 — Surface joints ──────────────────────────────────────────────────

def create_surface_joints(face_mesh, locators, ctrl_radius=0.5):
    """
    For each locator: find UV on face_mesh, create a uvPin-pinned PIN_GRP,
    a circle CTL and a JNT (parentConstrained to CTL) under it.

    Returns (top_grp, uvpin_node, [(pin_grp, ctl, jnt), ...]).
    """
    if not cmds.objExists(face_mesh):
        raise RuntimeError('Face mesh not found: {}'.format(face_mesh))
    missing = [l for l in locators if not cmds.objExists(l)]
    if missing:
        raise RuntimeError('Locators not found: {}'.format(', '.join(missing)))

    # Top-level groups
    top_grp = cmds.group(empty=True, name='DSFR_GRP')
    jnts_grp = cmds.group(empty=True, name='DSFR_surfaceJoints_GRP', parent=top_grp)
    rig_grp = cmds.group(empty=True, name='DSFR_rig_GRP', parent=top_grp)
    cmds.setAttr(rig_grp + '.visibility', False)

    orig_mesh = _create_orig_mesh(face_mesh, rig_grp)
    uvpin = _create_uvpin(face_mesh, orig_mesh)

    results = []
    for i, loc in enumerate(locators):
        base = _base_name(loc)
        world_pos = cmds.xform(loc, query=True, worldSpace=True, translation=True)
        u, v = _closest_uv(face_mesh, world_pos)

        # Set UV coordinate on uvPin array
        cmds.setAttr('{}.coordinateU[{}]'.format(uvpin, i), u)
        cmds.setAttr('{}.coordinateV[{}]'.format(uvpin, i), v)

        # PIN_GRP driven by uvPin output matrix
        pin_grp = cmds.group(empty=True, name=base + '_PIN_GRP', parent=jnts_grp)
        cmds.connectAttr('{}.outputMatrix[{}]'.format(uvpin, i),
                         pin_grp + '.offsetParentMatrix')
        for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
            cmds.setAttr(pin_grp + '.' + attr, 0)

        # Circle control — sibling of joint under PIN_GRP
        ctl = _make_circle_ctrl(base + '_CTL', ctrl_radius)
        cmds.parent(ctl, pin_grp)
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)

        # Joint — zeroed, parentConstrained to CTL
        cmds.select(clear=True)
        jnt = cmds.joint(name=base + '_JNT')
        cmds.parent(jnt, pin_grp)
        for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz',
                     'jointOrientX', 'jointOrientY', 'jointOrientZ'):
            cmds.setAttr(jnt + '.' + attr, 0)
        cmds.parentConstraint(ctl, jnt, maintainOffset=False)

        results.append((pin_grp, ctl, jnt))

    return top_grp, uvpin, results


# ── Phase 2 — Coarse bind (SK1) ───────────────────────────────────────────────

def bind_coarse(face_mesh, skeleton_joints):
    """Bind face_mesh to skeleton_joints with a standard skinCluster (SK1)."""
    missing = [j for j in skeleton_joints if not cmds.objExists(j)]
    if missing:
        raise RuntimeError('Joints not found: {}'.format(', '.join(missing)))
    sc = cmds.skinCluster(
        skeleton_joints, face_mesh,
        toSelectedBones=True,
        bindMethod=0,
        skinMethod=0,
        normalizeWeights=1,
        name=face_mesh + '_SK1',
    )[0]
    return sc


# ── Phase 3 — BlendShape layer ────────────────────────────────────────────────

def add_blendshape(face_mesh, target_meshes, sk1_node):
    """
    Create a blendShape from target_meshes on face_mesh, then reorder it
    to sit after sk1_node in the deformer stack.
    """
    missing = [t for t in target_meshes if not cmds.objExists(t)]
    if missing:
        raise RuntimeError('Target meshes not found: {}'.format(', '.join(missing)))
    bs = cmds.blendShape(
        target_meshes, face_mesh,
        name=face_mesh + '_BS',
        frontOfChain=True,
    )[0]
    # Place blendShape AFTER sk1 so stack reads: SK1 → BS → (SK2)
    cmds.reorderDeformers(sk1_node, bs, face_mesh)
    return bs


# ── Phase 4 — Fine bind (SK2) ─────────────────────────────────────────────────

def bind_surface_joints(face_mesh, uvpin_node):
    """
    Gather all JNT nodes under the uvPin hierarchy, bind them as SK2
    (multi=True), then wire JNT.parentInverseMatrix[0] → SK2.bindPreMatrix[i]
    for each influence to prevent double transformation.

    Returns sk2_node.
    """
    surface_joints = _collect_surface_joints(uvpin_node)
    if not surface_joints:
        raise RuntimeError('No surface joints found under uvPin: {}'.format(uvpin_node))

    sc2 = cmds.skinCluster(
        surface_joints + [face_mesh],
        multi=True,
        toSelectedBones=True,
        bindMethod=0,
        skinMethod=0,
        normalizeWeights=1,
        name=face_mesh + '_SK2',
    )[0]

    # Live bindPreMatrix: only the joint's LOCAL offset (from animator) fires SK2.
    # Surface tracking (PIN_GRP world movement) cancels out automatically.
    influences = cmds.skinCluster(sc2, query=True, influence=True) or []
    for i, jnt in enumerate(influences):
        cmds.connectAttr(
            jnt + '.parentInverseMatrix[0]',
            '{}.bindPreMatrix[{}]'.format(sc2, i),
            force=True,
        )

    return sc2


def _collect_surface_joints(uvpin_node):
    """Return JNTs that are children of groups driven by uvpin_node.outputMatrix."""
    driven_grps = cmds.listConnections(
        uvpin_node + '.outputMatrix',
        destination=True,
        type='transform',
    ) or []
    joints = []
    for grp in driven_grps:
        joints += cmds.listRelatives(grp, children=True, type='joint') or []
    return joints


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_rig_nodes(face_mesh):
    """
    Return dict of existing DSFR rig nodes on face_mesh.
    Keys: sk1, bs, sk2, uvpin  (None if not yet built).
    """
    history = cmds.listHistory(face_mesh, pruneDagObjects=True) or []
    sk_nodes = [n for n in history if cmds.nodeType(n) == 'skinCluster']
    bs_nodes = [n for n in history if cmds.nodeType(n) == 'blendShape']

    # listHistory returns most-recently-applied deformers first
    sk2 = sk_nodes[0]  if len(sk_nodes) >= 2 else None
    sk1 = sk_nodes[-1] if sk_nodes else None

    shape = _get_shape(face_mesh)
    uvpin = None
    if shape:
        pins = cmds.listConnections(shape + '.worldMesh[0]', type='uvPin') or []
        uvpin = pins[0] if pins else None

    return {
        'sk1':   sk1,
        'bs':    bs_nodes[0] if bs_nodes else None,
        'sk2':   sk2,
        'uvpin': uvpin,
    }


def find_face_mesh():
    """Try to auto-detect the face mesh from selection or scene."""
    sel = cmds.ls(selection=True, transforms=True)
    if sel:
        return sel[0]
    for name in ('head_lod0_mesh', 'Face_mesh', 'face_mesh', 'Head_mesh'):
        if cmds.objExists(name):
            return name
    return None

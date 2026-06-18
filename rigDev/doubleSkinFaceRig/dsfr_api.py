"""
dsfr_api.py — Double Skin Face Rig API

Two-mesh follicle-based architecture matching the jack.ma reference:
  - Original mesh keeps SK1 + existing blendShapes (hidden)
  - Duplicate mesh gets a wrap blendShape + SK2 (render mesh)
  - Follicles ride the original mesh surface (no feedback loop)
  - ParentConstraint: follicle → GRP, hierarchy: GRP → CTL → JNT
  - GRP.inverseMatrix → SK2.bindPreMatrix cancels surface tracking
"""

import maya.cmds as cmds
import follicleRig_api as fol


# ── Constants ────────────────────────────────────────────────────────────────

_MASTER_GRP = 'DSFR_GRP'
_FOLLICLE_GRP = 'DSFR_follicle_GRP'
_ROOT_GRP = 'DSFR_rootJnt_GRP'
_ROOT_JNT = 'DSFR_rootJnt'
_PREFIX = 'DSFR'


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_shape(transform):
    shapes = cmds.listRelatives(
        transform, shapes=True, noIntermediate=True) or []
    return shapes[0] if shapes else None


def _lock_hide(node):
    for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz'):
        cmds.setAttr(node + '.' + attr, lock=True)
    cmds.setAttr(node + '.visibility', False, lock=True)


def _make_circle_ctrl(name, radius=5.0):
    ctl = cmds.circle(name=name, normal=(0, 1, 0), radius=radius, ch=False)[0]
    shape = cmds.listRelatives(ctl, shapes=True)[0]
    cmds.setAttr(shape + '.overrideEnabled', True)
    cmds.setAttr(shape + '.overrideColor', 17)
    return ctl


def _next_index():
    existing = cmds.ls(_PREFIX + '_*_GRP', type='transform') or []
    indices = []
    for name in existing:
        part = name.replace(_PREFIX + '_', '').replace('_GRP', '')
        try:
            indices.append(int(part))
        except ValueError:
            pass
    return (max(indices) + 1) if indices else 1


def _component_to_uv(original_mesh, component):
    comp_type = component.split('.')[-1] if '.' in component else ''

    if comp_type.startswith('vtx['):
        return fol.getVertexUV(component)

    if comp_type.startswith('f[') or comp_type.startswith('e['):
        if comp_type.startswith('f['):
            verts = cmds.polyListComponentConversion(
                component, fromFace=True, toVertex=True)
        else:
            verts = cmds.polyListComponentConversion(
                component, fromEdge=True, toVertex=True)
        verts = cmds.ls(verts, flatten=True)
        if not verts:
            raise RuntimeError('Cannot convert {} to vertices'.format(component))
        positions = [cmds.pointPosition(v, world=True) for v in verts]
        center = [
            sum(p[0] for p in positions) / len(positions),
            sum(p[1] for p in positions) / len(positions),
            sum(p[2] for p in positions) / len(positions),
        ]
        (u, v), _ = fol.closestUVOnSurface(original_mesh, center)
        return (u, v)

    raise RuntimeError('Unsupported component type: {}'.format(component))


# ── Detect existing setup ────────────────────────────────────────────────────

def detect_existing_setup(mesh):
    """
    Check if a DSFR setup exists involving this mesh (as original or duplicate).
    Returns dict with keys: original, duplicate, master_grp, root_jnt,
    follicle_grp, sk2, wrap_bs.  Values are None if not found.
    """
    result = {
        'original': None, 'duplicate': None, 'master_grp': None,
        'root_jnt': None, 'follicle_grp': None, 'sk2': None,
        'wrap_bs': None,
    }

    if cmds.objExists(_MASTER_GRP):
        result['master_grp'] = _MASTER_GRP
    if cmds.objExists(_ROOT_JNT):
        result['root_jnt'] = _ROOT_JNT
    if cmds.objExists(_FOLLICLE_GRP):
        result['follicle_grp'] = _FOLLICLE_GRP

    render_name = mesh + '_DSFR_render'
    wrap_name = mesh + '_DSFR_wrap'

    if cmds.objExists(render_name):
        result['original'] = mesh
        result['duplicate'] = render_name
        if cmds.objExists(wrap_name):
            result['wrap_bs'] = wrap_name

        history = cmds.listHistory(render_name, pruneDagObjects=True) or []
        for node in history:
            if cmds.nodeType(node) == 'skinCluster':
                result['sk2'] = node
                break
    elif mesh.endswith('_DSFR_render'):
        orig = mesh.replace('_DSFR_render', '')
        if cmds.objExists(orig):
            result['original'] = orig
            result['duplicate'] = mesh
            wrap_name = orig + '_DSFR_wrap'
            if cmds.objExists(wrap_name):
                result['wrap_bs'] = wrap_name
            history = cmds.listHistory(mesh, pruneDagObjects=True) or []
            for node in history:
                if cmds.nodeType(node) == 'skinCluster':
                    result['sk2'] = node
                    break

    return result


# ── Prep rig ─────────────────────────────────────────────────────────────────

def prep_rig(mesh):
    """
    Set up the two-mesh architecture.  Idempotent — if setup already
    exists, returns the existing nodes without changing anything.
    """
    setup = detect_existing_setup(mesh)
    if setup['master_grp'] and setup['duplicate']:
        return setup

    if not cmds.objExists(mesh):
        raise RuntimeError('Mesh not found: {}'.format(mesh))

    duplicate = cmds.duplicate(mesh, name=mesh + '_DSFR_render')[0]

    wrap_bs = cmds.blendShape(
        mesh, duplicate,
        name=mesh + '_DSFR_wrap',
        frontOfChain=True,
        weight=(0, 1.0),
    )[0]

    cmds.setAttr(mesh + '.visibility', False)

    master_grp = cmds.group(empty=True, name=_MASTER_GRP)
    for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz'):
        cmds.setAttr(master_grp + '.' + attr, lock=True)

    fol_grp = cmds.group(empty=True, name=_FOLLICLE_GRP, parent=master_grp)

    root_grp = cmds.group(empty=True, name=_ROOT_GRP, parent=master_grp)
    _lock_hide(root_grp)

    cmds.select(clear=True)
    root_jnt = cmds.joint(name=_ROOT_JNT)
    cmds.parent(root_jnt, root_grp)
    for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz',
                 'jointOrientX', 'jointOrientY', 'jointOrientZ'):
        cmds.setAttr(root_jnt + '.' + attr, 0)
    _lock_hide(root_jnt)

    return {
        'original': mesh,
        'duplicate': duplicate,
        'master_grp': master_grp,
        'root_jnt': root_jnt,
        'follicle_grp': fol_grp,
        'sk2': None,
        'wrap_bs': wrap_bs,
    }


# ── Add follicle joints ─────────────────────────────────────────────────────

def add_follicle_joint(original_mesh, components, setup_dict, ctrl_radius=5.0):
    """
    Create one follicle/GRP/CTL/JNT per component (face/edge/vert).
    Follicles ride the original mesh.  GRP/CTL/JNT live under DSFR_GRP.
    """
    fol_grp = setup_dict['follicle_grp']
    master_grp = setup_dict['master_grp']

    idx = _next_index()
    results = []

    for comp in components:
        u, v = _component_to_uv(original_mesh, comp)
        name = '{}_{}'.format(_PREFIX, idx)

        follicle = fol.createFollicle(original_mesh, u, v, name)
        cmds.parent(follicle, fol_grp)

        grp = cmds.group(empty=True, name=name + '_GRP', parent=master_grp)
        cmds.parentConstraint(follicle, grp, maintainOffset=False)

        ctl = _make_circle_ctrl(name + '_CTL', ctrl_radius)
        cmds.parent(ctl, grp)
        cmds.setAttr(ctl + '.translate', 0, 0, 0)
        cmds.setAttr(ctl + '.rotate', 0, 0, 0)

        cmds.select(clear=True)
        jnt = cmds.joint(name=name + '_JNT')
        cmds.parent(jnt, ctl)
        for attr in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz',
                     'jointOrientX', 'jointOrientY', 'jointOrientZ'):
            cmds.setAttr(jnt + '.' + attr, 0)

        results.append((follicle, grp, ctl, jnt))
        idx += 1

    return results


# ── Resolve selection to GRP ──────────────────────────────────────────────────

def resolve_to_grp(node):
    """
    Given any part of a DSFR follicle rig (GRP, CTL, JNT, follicle, or
    parentConstraint), walk up to find the GRP under DSFR_GRP.
    Returns the GRP name or None.
    """
    if not cmds.objExists(node):
        return None

    current = node
    for _ in range(10):
        parent = cmds.listRelatives(current, parent=True)
        if not parent:
            break
        if parent[0] == _MASTER_GRP:
            return current
        current = parent[0]

    if cmds.objectType(node) == 'parentConstraint':
        parent = cmds.listRelatives(node, parent=True)
        if parent:
            return resolve_to_grp(parent[0])

    if cmds.objectType(node, isAType='transform'):
        shape = cmds.listRelatives(node, shapes=True, type='follicle')
        if shape:
            constraints = cmds.listConnections(
                node + '.translate', destination=True,
                type='parentConstraint') or []
            for con in constraints:
                con_parent = cmds.listRelatives(con, parent=True)
                if con_parent:
                    return resolve_to_grp(con_parent[0])

    return None


# ── Remove follicle joint ────────────────────────────────────────────────────

def remove_follicle_joint(setup_dict, grp):
    """Remove a single follicle/GRP/CTL/JNT setup."""
    jnts = cmds.listRelatives(grp, allDescendents=True, type='joint') or []

    if setup_dict.get('sk2') and jnts:
        sk2 = setup_dict['sk2']
        influences = cmds.skinCluster(sk2, query=True, influence=True) or []
        for jnt in jnts:
            if jnt in influences:
                cmds.skinCluster(sk2, edit=True, removeInfluence=jnt)

    constraints = cmds.listRelatives(
        grp, children=True, type='parentConstraint') or []
    follicle = None
    for con in constraints:
        targets = cmds.parentConstraint(con, query=True, targetList=True) or []
        if targets:
            follicle = targets[0]

    cmds.delete(grp)

    if follicle and cmds.objExists(follicle):
        cmds.delete(follicle)


# ── List follicle joints ─────────────────────────────────────────────────────

def list_follicle_joints(setup_dict):
    """
    Find all GRP/JNT pairs under the master group.
    Works on fresh file open — no in-memory state needed.
    """
    master_grp = setup_dict.get('master_grp')
    if not master_grp or not cmds.objExists(master_grp):
        return []

    children = cmds.listRelatives(master_grp, children=True,
                                  type='transform') or []
    results = []
    for child in children:
        if child in (_FOLLICLE_GRP, _ROOT_GRP):
            continue
        jnts = cmds.listRelatives(child, allDescendents=True,
                                  type='joint') or []
        if jnts:
            results.append((child, jnts[0]))

    return results


# ── Build rig ────────────────────────────────────────────────────────────────

def build_rig(setup_dict):
    """
    Create or update SK2 on the duplicate mesh.

    First build: all joints get default weights.
    Adding to existing: new joints added with zero weight.
    """
    duplicate = setup_dict.get('duplicate')
    root_jnt = setup_dict.get('root_jnt')
    sk2 = setup_dict.get('sk2')

    if not duplicate or not cmds.objExists(duplicate):
        raise RuntimeError('Duplicate mesh not found. Run Prep My Rig first.')

    pairs = list_follicle_joints(setup_dict)
    if not pairs:
        raise RuntimeError('No follicle joints found. Add some first.')

    all_jnts = [jnt for _, jnt in pairs]

    if sk2 and cmds.objExists(sk2):
        existing_infs = cmds.skinCluster(sk2, query=True,
                                         influence=True) or []
        new_jnts = [j for j in all_jnts if j not in existing_infs]
        if not new_jnts:
            raise RuntimeError('All joints are already in SK2.')

        for jnt in new_jnts:
            cmds.skinCluster(sk2, edit=True, addInfluence=jnt, weight=0.0)

        infs = cmds.skinCluster(sk2, query=True, influence=True) or []
        for jnt in new_jnts:
            i = infs.index(jnt)
            grp = cmds.listRelatives(
                cmds.listRelatives(jnt, parent=True)[0],
                parent=True)[0]
            cmds.connectAttr(
                grp + '.inverseMatrix',
                '{}.bindPreMatrix[{}]'.format(sk2, i),
                force=True)

        return sk2

    joints_to_bind = all_jnts + [root_jnt]

    sk2 = cmds.skinCluster(
        joints_to_bind + [duplicate],
        toSelectedBones=True,
        bindMethod=0,
        skinMethod=0,
        normalizeWeights=1,
        name=duplicate + '_SK2',
    )[0]

    influences = cmds.skinCluster(sk2, query=True, influence=True) or []
    for i, jnt in enumerate(influences):
        if jnt == root_jnt:
            cmds.connectAttr(
                _ROOT_GRP + '.inverseMatrix',
                '{}.bindPreMatrix[{}]'.format(sk2, i),
                force=True)
        else:
            ctl = cmds.listRelatives(jnt, parent=True)[0]
            grp = cmds.listRelatives(ctl, parent=True)[0]
            cmds.connectAttr(
                grp + '.inverseMatrix',
                '{}.bindPreMatrix[{}]'.format(sk2, i),
                force=True)

    # Flood all weight to root joint — student paints surface joints manually
    vtx_count = cmds.polyEvaluate(duplicate, vertex=True)
    for i, jnt in enumerate(influences):
        value = 1.0 if jnt == root_jnt else 0.0
        cmds.skinPercent(sk2, '{}.vtx[0:{}]'.format(duplicate, vtx_count - 1),
                         transformValue=(jnt, value))

    setup_dict['sk2'] = sk2
    return sk2

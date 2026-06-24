import maya.cmds as cmds


def _next_rig_index():
    existing = cmds.ls('aimRig_*_master_grp_01')
    if not existing:
        return 1
    indices = []
    for name in existing:
        parts = name.split('_')
        try:
            indices.append(int(parts[1]))
        except (IndexError, ValueError):
            pass
    return (max(indices) + 1) if indices else 1


def _next_cluster_index():
    existing = cmds.ls('aimRigCluster_*', transforms=True) or []
    indices = []
    for name in existing:
        parts = name.split('|')[-1].split('_')
        if len(parts) == 2:
            try:
                indices.append(int(parts[1]))
            except ValueError:
                pass
    return (max(indices) + 1) if indices else 1


def _get_playback_range():
    return (
        int(cmds.playbackOptions(q=True, min=True)),
        int(cmds.playbackOptions(q=True, max=True)),
    )


def _build_single(idx, snap_to=None):
    prefix = 'aimRig_{:02d}'.format(idx)

    master1 = cmds.group(em=True, name=prefix + '_master_grp_01')
    master2 = cmds.group(em=True, name=prefix + '_master_grp_02')
    master3 = cmds.group(em=True, name=prefix + '_master_grp_03')
    cmds.parent(master2, master1)
    cmds.parent(master3, master2)

    up_grp = cmds.group(em=True, name=prefix + '_up_grp')
    up_loc = cmds.spaceLocator(name=prefix + '_up_loc')[0]
    cmds.parent(up_grp, master3)
    cmds.parent(up_loc, up_grp)
    cmds.setAttr(up_grp + '.ty', 5)

    aim_grp = cmds.group(em=True, name=prefix + '_aim_grp')
    aim_loc = cmds.spaceLocator(name=prefix + '_aim_loc')[0]
    cmds.parent(aim_grp, master3)
    cmds.parent(aim_loc, aim_grp)

    target_grp = cmds.group(em=True, name=prefix + '_target_grp')
    target_loc = cmds.spaceLocator(name=prefix + '_target_loc')[0]
    cmds.parent(target_grp, master3)
    cmds.parent(target_loc, target_grp)
    cmds.setAttr(target_grp + '.tz', 10)

    cmds.aimConstraint(
        target_loc, aim_grp,
        aimVector=(0, 0, 1),
        upVector=(0, 1, 0),
        worldUpType='object',
        worldUpObject=up_loc,
        maintainOffset=False,
    )

    # Tag with parent cluster for later lookup (empty = standalone)
    cmds.addAttr(master1, longName='aimCluster', dataType='string')
    cmds.setAttr(master1 + '.aimCluster', '', type='string')

    if snap_to:
        pos = cmds.xform(snap_to, query=True, worldSpace=True, translation=True)
        cmds.xform(master1, worldSpace=True, translation=pos)

    return {'master1': master1, 'target_grp': target_grp, 'aim_loc': aim_loc}


def build_aim_rig():
    sel = cmds.ls(sl=True)

    if not sel:
        idx = _next_rig_index()
        _build_single(idx)
        cmds.inViewMessage(
            amg='<b>Aim Rig:</b> aimRig_{:02d} built at world origin.'.format(idx),
            pos='midCenter', fade=True)
        return

    if len(sel) == 1:
        idx = _next_rig_index()
        rig = _build_single(idx, snap_to=sel[0])
        cmds.parentConstraint(sel[0], rig['master1'], maintainOffset=True)
        cmds.inViewMessage(
            amg='<b>Aim Rig:</b> aimRig_{:02d} snapped to {}.'.format(idx, sel[0]),
            pos='midCenter', fade=True)
        return

    # Multi: build cluster group as org container and selection anchor
    c_idx = _next_cluster_index()
    cluster_name = 'aimRigCluster_{:02d}'.format(c_idx)
    cluster = cmds.group(em=True, name=cluster_name)
    pos = cmds.xform(sel[0], query=True, worldSpace=True, translation=True)
    cmds.xform(cluster, worldSpace=True, translation=pos)
    cmds.parentConstraint(sel[0], cluster, maintainOffset=True)

    start_idx = _next_rig_index()
    for i, obj in enumerate(sel):
        idx = start_idx + i
        rig = _build_single(idx, snap_to=obj)
        cmds.setAttr(rig['master1'] + '.aimCluster', cluster_name, type='string')
        cmds.parent(rig['master1'], cluster)
        cmds.parentConstraint(obj, rig['master1'], maintainOffset=True)
        if i + 1 < len(sel):
            cmds.pointConstraint(sel[i + 1], rig['target_grp'], maintainOffset=False)

    cmds.inViewMessage(
        amg='<b>Aim Rig:</b> {} — {} rigs built.'.format(cluster_name, len(sel)),
        pos='midCenter', fade=True)


# ---------------------------------------------------------------------------
# Helpers shared by bake_and_flip and bake_aim
# ---------------------------------------------------------------------------

def _find_master_grps(node):
    """Return master_grp_01 nodes for the given cluster or single rig."""
    short = node.split('|')[-1]
    if '_master_grp_01' in short:
        return [node]
    # Children still inside the cluster
    children = cmds.listRelatives(node, children=True, type='transform') or []
    grps = [c for c in children if '_master_grp_01' in c]
    if grps:
        return grps
    # After bake_and_flip master_grps are lifted to world — find by tag
    all_grps = cmds.ls('aimRig_*_master_grp_01') or []
    result = []
    for grp in all_grps:
        if cmds.attributeQuery('aimCluster', node=grp, exists=True):
            if cmds.getAttr(grp + '.aimCluster') == short:
                result.append(grp)
    return result


def _parent_constraint_target(node):
    cons = cmds.listRelatives(node, children=True, type='parentConstraint') or []
    if not cons:
        return None
    targets = cmds.parentConstraint(cons[0], q=True, targetList=True) or []
    return targets[0] if targets else None


# ---------------------------------------------------------------------------
# Bake & Flip
# ---------------------------------------------------------------------------

def bake_and_flip():
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.inViewMessage(
            amg='<b>Bake & Flip:</b> Select a cluster or aim rig master_grp_01.',
            pos='midCenter', fade=True)
        return

    node = sel[0]
    short = node.split('|')[-1]
    is_cluster = '_master_grp_01' not in short
    master_grps = _find_master_grps(node)

    if not master_grps:
        cmds.inViewMessage(
            amg='<b>Bake & Flip:</b> No aim rig groups found under selection.',
            pos='midCenter', fade=True)
        return

    # 1. Collect joint targets and target_grps before touching any constraints
    joint_map = {}
    target_grps = []
    for master in master_grps:
        joint = _parent_constraint_target(master)
        if joint:
            joint_map[master] = joint
        prefix = master.split('|')[-1].replace('_master_grp_01', '')
        tg = prefix + '_target_grp'
        if cmds.objExists(tg):
            pc = cmds.listRelatives(tg, type='pointConstraint') or []
            if pc:
                target_grps.append(tg)

    t_min, t_max = _get_playback_range()

    # 2. Bake cluster + masters + target_grps together with constraints active
    nodes_to_bake = ([node] + master_grps) if is_cluster else list(master_grps)
    nodes_to_bake += target_grps
    cmds.bakeResults(
        nodes_to_bake,
        t=(t_min, t_max),
        simulation=True,
        sampleBy=1,
        disableImplicitControl=False,
        preserveOutsideKeys=True,
    )

    # 3. Delete all parent and point constraints
    for n in nodes_to_bake:
        for con_type in ('parentConstraint', 'pointConstraint'):
            cons = cmds.listRelatives(n, children=True, type=con_type) or []
            for c in cons:
                cmds.delete(c)

    # 4. Flip: aim_loc now drives each original joint
    flipped = []
    for master, joint in joint_map.items():
        prefix = master.split('|')[-1].replace('_master_grp_01', '')
        aim_loc = prefix + '_aim_loc'
        if cmds.objExists(aim_loc):
            cmds.parentConstraint(aim_loc, joint, maintainOffset=True)
            flipped.append(joint)

    cmds.inViewMessage(
        amg='<b>Bake & Flip:</b> {} rig(s) flipped — joints now driven by aim_loc.'.format(len(flipped)),
        pos='midCenter', fade=True)


# ---------------------------------------------------------------------------
# Bake Aim
# ---------------------------------------------------------------------------

def bake_aim(to_layer=False, delete_rig=False):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.inViewMessage(
            amg='<b>Bake Aim:</b> Select a cluster or aim rig master_grp_01.',
            pos='midCenter', fade=True)
        return

    node = sel[0]
    short = node.split('|')[-1]
    is_cluster = '_master_grp_01' not in short
    master_grps = _find_master_grps(node)

    if not master_grps:
        cmds.inViewMessage(
            amg='<b>Bake Aim:</b> No aim rig groups found.',
            pos='midCenter', fade=True)
        return

    # Find driven joints via parentConstraints connected from each aim_loc
    driven_joints = []
    for master in master_grps:
        prefix = master.split('|')[-1].replace('_master_grp_01', '')
        aim_loc = prefix + '_aim_loc'
        if not cmds.objExists(aim_loc):
            continue
        cons = cmds.listConnections(aim_loc, type='parentConstraint', destination=True, source=False) or []
        for con in cons:
            parent = cmds.listRelatives(con, parent=True)
            if parent:
                driven_joints.append(parent[0])

    if not driven_joints:
        cmds.inViewMessage(
            amg='<b>Bake Aim:</b> No driven objects found — run Bake & Flip first.',
            pos='midCenter', fade=True)
        return

    t_min, t_max = _get_playback_range()

    if to_layer:
        layer_name = short + '_bakeLayer'
        if not cmds.objExists(layer_name):
            cmds.animLayer(layer_name)
        cmds.select(driven_joints)
        cmds.animLayer(layer_name, edit=True, addSelectedObjects=True)
        cmds.bakeResults(
            driven_joints,
            t=(t_min, t_max),
            simulation=True,
            sampleBy=1,
            destinationLayer=layer_name,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
        )
    else:
        cmds.bakeResults(
            driven_joints,
            t=(t_min, t_max),
            simulation=True,
            sampleBy=1,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
        )

    # Remove parent constraints from driven joints
    for joint in driven_joints:
        cons = cmds.listRelatives(joint, type='parentConstraint') or []
        for c in cons:
            cmds.delete(c)

    if delete_rig:
        for master in master_grps:
            if cmds.objExists(master):
                cmds.delete(master)
        if is_cluster and cmds.objExists(node):
            cmds.delete(node)

    cmds.inViewMessage(
        amg='<b>Bake Aim:</b> {} object(s) baked.{}'.format(
            len(driven_joints),
            ' Rig deleted.' if delete_rig else ''),
        pos='midCenter', fade=True)

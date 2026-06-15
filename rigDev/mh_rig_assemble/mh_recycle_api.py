"""
Metahuman Rig Recycle — API
Cleanup and export functions for stripping the Metahuman plugin dependency
after blendshape baking is complete.
"""

import os
import sys

import maya.cmds as cmds

try:
    from mh_bs_bake_api import find_face_mesh
except ImportError:
    _BAKE_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'mh_bs_bake')
    )
    if _BAKE_DIR not in sys.path:
        sys.path.insert(0, _BAKE_DIR)
    from mh_bs_bake_api import find_face_mesh


BS_BASE_NAME = 'mh_bs_base'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_bs_base():
    """Return mh_bs_base transform if it exists in the scene, else None."""
    if cmds.objExists(BS_BASE_NAME):
        return BS_BASE_NAME
    matches = cmds.ls('*mh_bs_base*', type='transform')
    return matches[0] if matches else None


# Name patterns used when the Metahuman plugin is not loaded (or rigLogic has
# already been deleted). Covers all standard MH mesh names.
_MH_MESH_PATTERNS = (
    '*head_lod*_mesh',
    '*teeth_lod0_mesh*',
    '*tongue_lod0_mesh*',
    '*saliva_lod0_mesh*',
    '*eyeLeft_lod0_mesh*',
    '*eyeRight_lod0_mesh*',
)


def _find_rl_meshes():
    """
    Return all transform nodes whose mesh shape is driven by a rigLogic node,
    directly (head LODs, eyes, saliva) or via joint-driven skinClusters (teeth,
    tongue).

    When the Metahuman plugin is not loaded (rigLogic nodes appear as unknownPlugin
    or have already been removed), falls back to searching by standard MH mesh
    name patterns so that Preview Comparison still works.
    """
    rl_nodes = cmds.ls(type='rigLogic') or []
    meshes = set()

    if rl_nodes:
        for rl in rl_nodes:
            future = cmds.listHistory(rl, future=True, pruneDagObjects=False) or []
            shapes = cmds.ls(future, type='mesh') or []
            for shape in shapes:
                parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
                meshes.update(parents)
            # Teeth / tongue / saliva are joint-driven and missed by listHistory.
            ns = (rl.rsplit(':', 1)[0] + ':') if ':' in rl else ''
            for pattern in (ns + '*teeth*lod0*', ns + '*tongue*lod0*', ns + '*saliva*lod0*'):
                for m in (cmds.ls(pattern, type='transform') or []):
                    meshes.add(m)
    else:
        # Plugin not loaded or rigLogic already removed — use name patterns.
        for pattern in _MH_MESH_PATTERNS:
            for m in (cmds.ls(pattern, type='transform') or []):
                meshes.add(m)

    return list(meshes)


def _find_display_layers_for_meshes(meshes):
    """Return display layers (excluding defaultLayer) connected to any of the meshes
    or their shape nodes."""
    layers = set()
    for mesh in meshes:
        nodes = [mesh] + (cmds.listRelatives(mesh, shapes=True, fullPath=True) or [])
        for node in nodes:
            try:
                conns = cmds.listConnections(
                    node + '.drawOverride', type='displayLayer', source=True
                ) or []
                for layer in conns:
                    if layer != 'defaultLayer':
                        layers.add(layer)
            except Exception:
                pass
    return list(layers)


# ---------------------------------------------------------------------------
# Button 1 — Preview Comparison (toggle)
# ---------------------------------------------------------------------------

_TARGET_GRPS = ('mhBsTargets_GRP', 'mhBsTeethTargets_GRP')


def toggle_comparison():
    """
    Toggle template display on all RL-driven face meshes using transform.template —
    a standard DAG attribute that is never connected or locked by display layers.
    Also hides/shows the bake target groups so only the templated original and
    mh_bs_base are visible during comparison.
    Returns True if comparison is now ON, False if OFF.
    """
    all_meshes = [m for m in _find_rl_meshes() if cmds.objExists(m)]
    if not all_meshes:
        raise RuntimeError('No RigLogic-driven meshes found in scene.')
    meshes = [m for m in all_meshes if 'eye' not in m.lower()]

    currently_on = any(cmds.getAttr(m + '.template') for m in meshes)
    for mesh in meshes:
        cmds.setAttr(mesh + '.template', not currently_on)

    for grp in _TARGET_GRPS:
        if cmds.objExists(grp):
            cmds.setAttr(grp + '.visibility', currently_on)  # hide on, show off

    return not currently_on


def comparison_is_on():
    """Return True if any RL mesh transform is currently templated."""
    return any(
        cmds.objExists(m) and cmds.getAttr(m + '.template')
        for m in _find_rl_meshes()
        if 'eye' not in m.lower()
    )


# ---------------------------------------------------------------------------
# Button 2 — Delete Original Face Meshes
# ---------------------------------------------------------------------------

def delete_rl_meshes():
    """
    Delete all RigLogic-driven face meshes and any associated display layers.
    Returns (mesh_count, layer_count).
    """
    meshes = [m for m in _find_rl_meshes() if 'eye' not in m.lower()]
    layers = _find_display_layers_for_meshes(meshes)

    mesh_count = 0
    for mesh in meshes:
        if cmds.objExists(mesh):
            cmds.delete(mesh)
            mesh_count += 1

    layer_count = 0
    for layer in layers:
        if cmds.objExists(layer):
            cmds.delete(layer)
            layer_count += 1

    return mesh_count, layer_count


# ---------------------------------------------------------------------------
# Button 3 — Remove RigLogic Nodes
# ---------------------------------------------------------------------------

def remove_rl_nodes():
    """
    Delete all rigLogic, embeddedNodeRL4, and dnaFileNode plugin nodes.
    Returns list of deleted node names.
    """
    deleted = []
    for node_type in ('rigLogic', 'embeddedNodeRL4', 'dnaFileNode'):
        nodes = cmds.ls(type=node_type) or []
        for node in nodes:
            if cmds.objExists(node):
                cmds.delete(node)
                deleted.append(node)
    return deleted


# ---------------------------------------------------------------------------
# Button 4 — Delete Face Joints
# ---------------------------------------------------------------------------

def delete_face_joints(namespace=':'):
    """
    Delete all FACIAL_ joints except eye joints (head, neck, body and eye
    joints are unaffected). Returns count of deleted joints.
    """
    prefix = '' if namespace in (':', '') else namespace
    all_joints = cmds.ls('{}FACIAL_*'.format(prefix), type='joint') or []
    to_keep = [j for j in all_joints if 'eye' in j.lower()]
    to_delete = [j for j in all_joints if 'eye' not in j.lower()]

    # Unparent eye joints to world before deletion — without this, any eye
    # joint whose parent is in to_delete would be taken with it.
    if to_keep:
        cmds.parent(to_keep, world=True)

    if to_delete:
        cmds.delete(to_delete)
    return len(to_delete)


# ---------------------------------------------------------------------------
# Button 5 — Export Standalone Scene
# ---------------------------------------------------------------------------

def export_standalone(export_path):
    """
    Export all nodes in the current scene to a new .ma file without
    changing the current scene's name or save state.
    """
    cmds.file(export_path, exportAll=True, type='mayaAscii', force=True)


# ---------------------------------------------------------------------------
# Button 5 — Delete Bake Targets
# ---------------------------------------------------------------------------

def delete_bake_targets():
    """
    Delete all mhBs*Targets_GRP groups (face, teeth, tongue, etc.)
    and their child baked target meshes. Returns count of groups deleted.
    """
    grps = cmds.ls('mhBs*Targets_GRP') or []
    count = 0
    for grp in grps:
        if cmds.objExists(grp):
            cmds.delete(grp)
            count += 1
    return count

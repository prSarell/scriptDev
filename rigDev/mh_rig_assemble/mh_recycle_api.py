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
_COMPARE_MARKER = '_mhCompareActive'


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

def toggle_comparison():
    """
    Toggle template display on ALL RL-driven face meshes (head LODs, teeth,
    eyes, etc.) so they overlay mh_bs_base as grey wireframes simultaneously.

    Works on shape-node overrides rather than transform overrides so that
    display-layer connections on the transforms are not disturbed.
    Uses a marker attribute on each shape to track toggle state reliably.

    Returns True if comparison is now ON, False if OFF.
    """
    meshes = _find_rl_meshes()
    if not meshes:
        raise RuntimeError('No RigLogic-driven meshes found in scene.')

    shapes = []
    for mesh in meshes:
        shapes += cmds.listRelatives(mesh, shapes=True) or []

    currently_on = any(cmds.objExists(s + '.' + _COMPARE_MARKER) for s in shapes)

    modified = 0
    for shape in shapes:
        try:
            if currently_on:
                cmds.setAttr(shape + '.overrideEnabled', False)
                cmds.setAttr(shape + '.overrideDisplayType', 0)
                if cmds.objExists(shape + '.' + _COMPARE_MARKER):
                    cmds.deleteAttr(shape + '.' + _COMPARE_MARKER)
            else:
                cmds.setAttr(shape + '.overrideEnabled', True)
                cmds.setAttr(shape + '.overrideDisplayType', 1)  # Template
                if not cmds.objExists(shape + '.' + _COMPARE_MARKER):
                    cmds.addAttr(shape, longName=_COMPARE_MARKER, attributeType='bool')
            modified += 1
        except Exception:
            # Shape has a connected or locked override (e.g. MH visibility switching).
            # Skip it — the visible LOD0 meshes are the ones that matter.
            pass

    if modified == 0:
        raise RuntimeError(
            'Could not modify overrides on any mesh shape — all are locked or connected.'
        )
    return not currently_on


def comparison_is_on():
    """Return True if comparison mode is active (marker attribute present on any RL shape)."""
    for mesh in _find_rl_meshes():
        for shape in (cmds.listRelatives(mesh, shapes=True) or []):
            if cmds.objExists(shape + '.' + _COMPARE_MARKER):
                return True
    return False


# ---------------------------------------------------------------------------
# Button 2 — Delete Original Face Meshes
# ---------------------------------------------------------------------------

def delete_rl_meshes():
    """
    Delete all RigLogic-driven face meshes and any associated display layers.
    Returns (mesh_count, layer_count).
    """
    meshes = _find_rl_meshes()
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
    to_delete = [j for j in all_joints if 'eye' not in j.lower()]
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

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
_COMPARISON_ATTR = 'overrideDisplayType'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_bs_base():
    """Return mh_bs_base transform if it exists in the scene, else None."""
    if cmds.objExists(BS_BASE_NAME):
        return BS_BASE_NAME
    matches = cmds.ls('*mh_bs_base*', type='transform')
    return matches[0] if matches else None


def _find_rl_meshes():
    """
    Return all transform nodes whose mesh shape has a rigLogic node in its
    deformer history. Catches all head LODs, teeth, eyes, saliva, etc.
    """
    rl_nodes = cmds.ls(type='rigLogic') or []
    meshes = set()
    for rl in rl_nodes:
        future = cmds.listHistory(rl, future=True, pruneDagObjects=False) or []
        shapes = cmds.ls(future, type='mesh') or []
        for shape in shapes:
            parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            meshes.update(parents)
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

def toggle_comparison(face_mesh):
    """
    Toggle template display on the RL face mesh so it overlays mh_bs_base
    as a grey wireframe. Returns True if comparison is now ON, False if OFF.
    """
    if not cmds.objExists(face_mesh):
        raise RuntimeError('Face mesh not found: {}'.format(face_mesh))

    currently_on = (
        cmds.getAttr(face_mesh + '.overrideEnabled') and
        cmds.getAttr(face_mesh + '.overrideDisplayType') == 1
    )

    if currently_on:
        cmds.setAttr(face_mesh + '.overrideEnabled', False)
        cmds.setAttr(face_mesh + '.overrideDisplayType', 0)
        return False
    else:
        cmds.setAttr(face_mesh + '.overrideEnabled', True)
        cmds.setAttr(face_mesh + '.overrideDisplayType', 1)  # Template
        return True


def comparison_is_on(face_mesh):
    """Return True if the face mesh is currently templated for comparison."""
    if not cmds.objExists(face_mesh):
        return False
    return (
        cmds.getAttr(face_mesh + '.overrideEnabled') and
        cmds.getAttr(face_mesh + '.overrideDisplayType') == 1
    )


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

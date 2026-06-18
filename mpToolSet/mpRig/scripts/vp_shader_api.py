"""
Virtual Pancakes Shader API
Auto-assigns colour-coded Lambert shaders to VP selection sets.

For each VP combined region, the boundary edge loop is converted to a ring of
faces and stored as a new objectSet (*_boundary).  Shaders are then layered:

  Full VP region  → warm tan  (shows the region extent)
  Boundary ring   → orange    (marks the actual joint position)
  Structural      → blue      (combined_main, combined_innerMouth)
  Secondary       → grey      (eyes, teeth, eyelashes)
"""

import maya.cmds as cmds

SHADER_CRITICAL   = 'vp_critical_mat'
SHADER_REGION     = 'vp_region_mat'
SHADER_STRUCTURAL = 'vp_structural_mat'
SHADER_SECONDARY  = 'vp_secondary_mat'

_STRUCTURAL_BASES = frozenset(('combined_main', 'combined_innerMouth'))
_COMBINED_SFX     = '_pgcombined'
_BOUNDARY_SFX     = '_boundary'
_SECONDARY_SFXS   = ('_pgeyes', '_pgteeth', '_pgeyelashes')
_ALL_VP_SFXS      = (_COMBINED_SFX,) + _SECONDARY_SFXS


def find_vp_sets():
    """Return all objectSet nodes in the scene with a VP suffix."""
    return [s for s in (cmds.ls(type='objectSet') or [])
            if any(s.split(':')[-1].endswith(sfx) for sfx in _ALL_VP_SFXS)]


def _category(set_name):
    base = set_name.split(':')[-1]
    if any(base.endswith(sfx) for sfx in _SECONDARY_SFXS):
        return 'secondary'
    base_no_sfx = base[:-len(_COMBINED_SFX)]
    return 'structural' if base_no_sfx in _STRUCTURAL_BASES else 'region'


def _ensure_shader(mat_name, rgb):
    sg_name = mat_name + 'SG'
    if not cmds.objExists(mat_name):
        cmds.shadingNode('lambert', name=mat_name, asShader=True)
        cmds.setAttr(mat_name + '.color', rgb[0], rgb[1], rgb[2], type='double3')
    if not cmds.objExists(sg_name):
        cmds.sets(name=sg_name, renderable=True, noSurfaceShader=True, empty=True)
        cmds.connectAttr(mat_name + '.outColor', sg_name + '.surfaceShader', force=True)
    return sg_name


def _build_boundary_set(vp_set):
    """
    Find the faces in vp_set that touch its perimeter edge loop, store them as
    a new objectSet, and return its name.  Returns None if nothing found.
    """
    members = cmds.sets(vp_set, query=True) or []
    if not members:
        return None

    border_edges = cmds.polyListComponentConversion(
        members, fromFace=True, toEdge=True, border=True)
    if not border_edges:
        return None

    adj_faces = cmds.polyListComponentConversion(
        border_edges, fromEdge=True, toFace=True)
    if not adj_faces:
        return None

    members_expanded = set(cmds.filterExpand(members, selectionMask=34) or [])
    boundary_faces = [f for f in (cmds.filterExpand(adj_faces, selectionMask=34) or [])
                      if f in members_expanded]
    if not boundary_faces:
        return None

    # Strip namespace, swap suffix
    base = vp_set.split(':')[-1]
    set_name = base[:-len(_COMBINED_SFX)] + _BOUNDARY_SFX
    if cmds.objExists(set_name):
        cmds.delete(set_name)
    cmds.sets(boundary_faces, name=set_name)
    return set_name


def apply_shaders():
    """
    Build boundary sets and assign colour-coded shaders to all VP sets.
    Returns (boundary_sets_created, vp_sets_total).
    """
    vp_sets = find_vp_sets()
    if not vp_sets:
        raise RuntimeError('No Virtual Pancakes selection sets found in scene.')

    sg_critical   = _ensure_shader(SHADER_CRITICAL,   (1.0,  0.40, 0.0))
    sg_region     = _ensure_shader(SHADER_REGION,      (0.75, 0.65, 0.55))
    sg_structural = _ensure_shader(SHADER_STRUCTURAL,  (0.2,  0.50, 0.8))
    sg_secondary  = _ensure_shader(SHADER_SECONDARY,   (0.4,  0.40, 0.4))

    cat_to_sg = {
        'region':     sg_region,
        'structural': sg_structural,
        'secondary':  sg_secondary,
    }

    # Pass 1 — assign full-region shaders to every VP set
    for vp_set in vp_sets:
        members = cmds.sets(vp_set, query=True) or []
        if members:
            cmds.sets(members, edit=True, forceElement=cat_to_sg[_category(vp_set)])

    # Pass 2 — build boundary rings and override with orange
    boundary_count = 0
    for vp_set in vp_sets:
        if _category(vp_set) != 'region':
            continue
        bset = _build_boundary_set(vp_set)
        if bset:
            boundary_faces = cmds.sets(bset, query=True) or []
            if boundary_faces:
                cmds.sets(boundary_faces, edit=True, forceElement=sg_critical)
            boundary_count += 1

    return boundary_count, len(vp_sets)


def remove_shaders():
    """Delete VP shaders, their SGs, and all *_boundary objectSets."""
    deleted = []
    for name in (SHADER_CRITICAL, SHADER_REGION, SHADER_STRUCTURAL, SHADER_SECONDARY):
        for node in (name + 'SG', name):
            if cmds.objExists(node):
                cmds.delete(node)
                deleted.append(node)
    for s in (cmds.ls(type='objectSet') or []):
        if s.split(':')[-1].endswith(_BOUNDARY_SFX):
            cmds.delete(s)
            deleted.append(s)
    return deleted

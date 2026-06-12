"""mh_body_clean_api.py — Metahuman body scene cleanup: LODs, lights, textures."""
import os
import glob as _glob
import maya.cmds as cmds

# ── constants ─────────────────────────────────────────────────────────────────

_LOD_GRP     = 'body_lod{}_grp'
_LOD_COUNT   = 5   # 0 through 4
_LIGHTS_GRP  = 'Lights'

_TEX_KEYS = {
    'eyes':  'Eyes_Color',
    'head':  'Head_Basecolor',
    'teeth': 'Teeth_Color',
    'body':  'Body_Basecolor',
}

_TEX_EXTS = ('*.png', '*.tga', '*.jpg', '*.jpeg', '*.exr', '*.tif', '*.tiff')

# Mesh name patterns used when assigning textures (wildcards for cmds.ls)
_MESH_PATTERNS = {
    'head':  ['head_lod0_mesh', '*head*lod0*mesh*'],
    'eyes':  ['eyeLeft_lod0_mesh', 'eyeRight_lod0_mesh',
               '*eye*lod0*mesh*', '*eyeshell*lod0*'],
    'teeth': ['teeth_lod0_mesh', '*teeth*lod0*mesh*'],
}

# ── LODs ──────────────────────────────────────────────────────────────────────

def find_lods():
    """Return dict {lod_index: exists} for LOD 0-4."""
    return {i: cmds.objExists(_LOD_GRP.format(i)) for i in range(_LOD_COUNT)}


def _display_layers_for_group(grp):
    """Return set of display layer names that *grp* or any descendant belongs to."""
    layers = set()
    all_nodes = [grp] + (cmds.listRelatives(grp, allDescendents=True,
                                             fullPath=True) or [])
    for node in all_nodes:
        if not cmds.objExists(node):
            continue
        try:
            conns = cmds.listConnections(node + '.drawOverride',
                                         type='displayLayer') or []
            layers.update(conns)
        except Exception:
            pass
    layers.discard('defaultLayer')
    return layers


def delete_lods(lods_to_delete):
    """
    Delete the given LOD indices (list of ints).
    Also deletes any display layers that were exclusively used by those groups.
    Returns list of deleted group names.
    """
    deleted = []
    orphan_layers = set()

    for idx in lods_to_delete:
        grp = _LOD_GRP.format(idx)
        if not cmds.objExists(grp):
            continue
        orphan_layers |= _display_layers_for_group(grp)
        cmds.delete(grp)
        deleted.append(grp)

    # Only delete layers that no longer have any members
    for layer in list(orphan_layers):
        if not cmds.objExists(layer):
            continue
        try:
            members = cmds.editDisplayLayerMembers(layer, query=True) or []
            if not members:
                cmds.delete(layer)
        except Exception:
            pass

    return deleted


# ── lights ────────────────────────────────────────────────────────────────────

def delete_lights():
    """Delete the Unreal 'Lights' group and its contents. Returns True if found."""
    if cmds.objExists(_LIGHTS_GRP):
        cmds.delete(_LIGHTS_GRP)
        return True
    return False


# ── texture discovery ─────────────────────────────────────────────────────────

def _find_rl4_node():
    """Locate the embeddedNodeRL4 (or dnaFileNode) in the scene."""
    if cmds.objExists('head_lod0_mesh'):
        history = cmds.listHistory('head_lod0_mesh', pruneDagObjects=True) or []
        for node in history:
            if cmds.nodeType(node) == 'embeddedNodeRL4':
                return node
    nodes = cmds.ls(type='embeddedNodeRL4') or []
    if nodes:
        return nodes[0]
    nodes = cmds.ls(type='dnaFileNode') or []
    return nodes[0] if nodes else None


def _get_dna_path(node):
    """Return the DNA file path string from the RL4 node, or ''."""
    for attr in ('dnaFilePath', 'inputDna', 'dna', 'filePath'):
        try:
            val = cmds.getAttr('{}.{}'.format(node, attr))
            if val:
                return str(val)
        except Exception:
            pass
    return ''


def auto_maps_folder():
    """
    Try to resolve the maps folder automatically from the DNA node.
    DNA is expected at  .../CharacterName/DNA/char.dna
    Maps folder is at  .../CharacterName/maps/
    Returns path string or '' if not found.
    """
    node = _find_rl4_node()
    if not node:
        return ''
    dna_path = _get_dna_path(node)
    if not dna_path:
        return ''
    # Go up two levels from the .dna file: DNA/ → CharacterName/ → maps/
    char_dir  = os.path.dirname(os.path.dirname(dna_path))
    maps_dir  = os.path.join(char_dir, 'maps')
    return maps_dir if os.path.isdir(maps_dir) else ''


def scan_textures(maps_folder):
    """
    Search *maps_folder* for the four base-colour textures.
    Returns dict: {'eyes': path|None, 'head': path|None,
                   'teeth': path|None, 'body': path|None}
    """
    results = {k: None for k in _TEX_KEYS}
    if not maps_folder or not os.path.isdir(maps_folder):
        return results

    # Build a flat list of all image files in the folder
    all_files = []
    for ext in _TEX_EXTS:
        all_files += _glob.glob(os.path.join(maps_folder, ext))
        all_files += _glob.glob(os.path.join(maps_folder, ext.upper()))

    for key, keyword in _TEX_KEYS.items():
        for path in all_files:
            if keyword.lower() in os.path.basename(path).lower():
                results[key] = path
                break

    return results


# ── texture assignment ────────────────────────────────────────────────────────

def _find_meshes(key):
    """Return list of mesh transform names to assign *key* textures to."""
    if key == 'body':
        grp = _LOD_GRP.format(0)
        if not cmds.objExists(grp):
            return []
        meshes = []
        for node in (cmds.listRelatives(grp, allDescendents=True,
                                         type='mesh') or []):
            xform = (cmds.listRelatives(node, parent=True) or [node])[0]
            if xform not in meshes:
                meshes.append(xform)
        return meshes

    found = []
    for pattern in _MESH_PATTERNS.get(key, []):
        matches = cmds.ls(pattern, type='transform') or []
        for m in matches:
            if m not in found:
                found.append(m)
        if found:
            break
    return found


def _make_shader(name, texture_path):
    """Create a lambert + file texture node. Returns (shader, sg)."""
    shader = name + '_MAT'
    sg     = name + '_SG'
    fn     = name + '_COL'
    p2d    = name + '_P2D'

    if cmds.objExists(shader):
        cmds.delete(shader)
    if cmds.objExists(sg):
        cmds.delete(sg)

    shader_node = cmds.shadingNode('lambert', asShader=True, name=shader)
    sg_node     = cmds.sets(renderable=True, noSurfaceShader=True,
                             empty=True, name=sg)
    cmds.connectAttr(shader_node + '.outColor', sg_node + '.surfaceShader')

    file_node = cmds.shadingNode('file', asTexture=True, isColorManaged=True,
                                 name=fn)
    cmds.setAttr(file_node + '.fileTextureName', texture_path, type='string')
    cmds.connectAttr(file_node + '.outColor', shader_node + '.color')

    p2d_node = cmds.shadingNode('place2dTexture', asUtility=True, name=p2d)
    for src, dst in (
        ('coverage',        'coverage'),
        ('translateFrame',  'translateFrame'),
        ('rotateFrame',     'rotateFrame'),
        ('mirrorU',         'mirrorU'),
        ('mirrorV',         'mirrorV'),
        ('stagger',         'stagger'),
        ('wrapU',           'wrapU'),
        ('wrapV',           'wrapV'),
        ('repeatUV',        'repeatUV'),
        ('offset',          'offset'),
        ('rotateUV',        'rotateUV'),
        ('noiseUV',         'noiseUV'),
        ('outUV',           'uv'),
        ('outUvFilterSize', 'uvFilterSize'),
    ):
        try:
            cmds.connectAttr(p2d_node + '.' + src, file_node + '.' + dst)
        except Exception:
            pass

    return shader_node, sg_node


def assign_textures(texture_map):
    """
    Create lambert shaders and assign them to scene geometry.
    *texture_map* is the dict returned by scan_textures().
    Returns dict {key: {'shader': name, 'meshes': [...]}} for each assigned key.
    """
    report = {}
    for key, tex_path in texture_map.items():
        if not tex_path:
            continue
        shader_name = 'mh_{}_preview'.format(key)
        shader, sg  = _make_shader(shader_name, tex_path)
        meshes      = _find_meshes(key)
        assigned    = []
        for mesh in meshes:
            try:
                cmds.sets(mesh, edit=True, forceElement=sg)
                assigned.append(mesh)
            except Exception:
                pass
        report[key] = {'shader': shader, 'meshes': assigned}
    return report

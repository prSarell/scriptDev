"""
Eucalyptus Leaf Generator
Manual, curve-by-curve leaf decoration tool for trees built by eucalyptusGen.

Workflow (see eucalyptusLeaves_ui.py for the interactive version):
    1. Select tree curves, call select_curves_and_cvs() to switch to CV
       component mode with every CV on those curves selected.
    2. reduce_selection_to_tip(curves, keep_count) narrows the selection to
       the last `keep_count` CVs (counting from the tip) on each curve, so
       leaves can be placed only near branch/twig ends.
    3. generate_leaves() reads whatever CVs are currently selected and drops
       a random number of low-poly leaves at each one, oriented off the
       curve's local tangent, species leaf-inclination, and phyllotaxis.

Species leaf dimensions/colour below are reasonable artist estimates —
eucalyptus_growth_research.md has phyllotaxis and inclination data but no
per-species leaf morphometrics. Tune LEAF_PARAMS directly as needed.
"""

import math
import random

import maya.cmds as cmds

import eucalyptusGen


LEAF_PARAMS = {
    'citriodora': {
        'length': (10.0, 17.0),   # cm, long narrow lanceolate
        'width_ratio': 0.12,
        'curl': 0.15,
        'color': (0.55, 0.68, 0.35),
    },
    'pauciflora': {
        'length': (5.0, 10.0),    # shorter, broader
        'width_ratio': 0.30,
        'curl': 0.10,
        'color': (0.45, 0.60, 0.42),
    },
    'regnans': {
        'length': (9.0, 14.0),    # falcate/sickle
        'width_ratio': 0.20,
        'curl': 0.20,
        'color': (0.30, 0.55, 0.28),
    },
    'camaldulensis': {
        'length': (8.0, 22.0),    # long, drooping, very narrow
        'width_ratio': 0.10,
        'curl': 0.30,
        'color': (0.40, 0.58, 0.32),
    },
}

STEM_LENGTH_RATIO = 0.12
STEM_RADIUS_RATIO = 0.06


# ---------------------------------------------------------------------------
# Curve / CV selection helpers
# ---------------------------------------------------------------------------

def _cv_count(curve):
    shapes = cmds.listRelatives(curve, shapes=True, fullPath=True) or []
    if not shapes:
        raise ValueError('{} has no shape'.format(curve))
    spans = cmds.getAttr(shapes[0] + '.spans')
    degree = cmds.getAttr(shapes[0] + '.degree')
    return spans + degree


def _resolve_transform(node):
    if cmds.objExists(node) and cmds.nodeType(node) == 'transform':
        return node
    parents = cmds.listRelatives(node, parent=True, fullPath=True)
    return parents[0] if parents else node


def select_curves_and_cvs():
    """Step 1: switch the current curve selection to CV component mode with
    every CV selected. Returns the list of curve transforms selected."""
    sel = cmds.ls(selection=True, type='transform') or []
    curves = [s for s in sel
              if cmds.listRelatives(s, shapes=True, type='nurbsCurve')]
    if not curves:
        raise ValueError('Select one or more tree curves first.')

    cmds.select(clear=True)
    for c in curves:
        n = _cv_count(c)
        cmds.select('{}.cv[0:{}]'.format(c, n - 1), add=True)
    return curves


def reduce_selection_to_tip(curves, keep_count):
    """Step 2: narrow the selection on each curve to its last `keep_count`
    CVs (counting from the tip backward)."""
    cmds.select(clear=True)
    for c in curves:
        if not cmds.objExists(c):
            continue
        n = _cv_count(c)
        k = max(1, min(keep_count, n))
        cmds.select('{}.cv[{}:{}]'.format(c, n - k, n - 1), add=True)


def get_selected_cvs():
    """Return {curve_transform: sorted [cv indices]} from the current
    component selection."""
    sel = cmds.ls(selection=True, flatten=True) or []
    by_curve = {}
    for item in sel:
        if '.cv[' not in item:
            continue
        node, rest = item.split('.cv[')
        idx = int(rest.rstrip(']'))
        curve = _resolve_transform(node)
        by_curve.setdefault(curve, []).append(idx)
    for c in by_curve:
        by_curve[c] = sorted(set(by_curve[c]))
    return by_curve


def _infer_species(curve):
    paths = cmds.ls(curve, long=True)
    if not paths:
        return None
    for part in paths[0].split('|'):
        if part.endswith('_tree_GRP'):
            prefix = part[:-len('_tree_GRP')]
            species = prefix.split('_')[0]
            if species in eucalyptusGen.SPECIES:
                return species
    return None


# ---------------------------------------------------------------------------
# Orientation
# ---------------------------------------------------------------------------

def _leaf_basis(tangent, azimuth_deg, tilt_deg):
    """Build a local (x=width, y=petiole->tip, z=front-face-normal) basis
    for a leaf that hangs generally downward (eucalyptus foliage is
    documented as pendulous) with per-leaf random variation.

    The leaf's long axis starts at straight-down (gravity) and is tilted
    `tilt_deg` off vertical toward the `azimuth_deg` compass direction
    around the stem (phyllotaxis). Keeping tilt_deg comfortably below 90
    guarantees every leaf still trends downward — it can lean and scatter
    around the stem but never swing up past horizontal.
    """
    perp = eucalyptusGen._perp_vec(tangent)
    compass = eucalyptusGen._vnorm(
        eucalyptusGen._rotate_vec(perp, tangent, math.radians(azimuth_deg)))

    down = (0.0, -1.0, 0.0)
    tilt_axis = eucalyptusGen._vcross(down, compass)
    if eucalyptusGen._vlen(tilt_axis) < 1e-6:
        tilt_axis = perp
    y_axis = eucalyptusGen._vnorm(
        eucalyptusGen._rotate_vec(down, tilt_axis, math.radians(tilt_deg)))

    z_raw = eucalyptusGen._vsub(
        compass, eucalyptusGen._vscale(y_axis, eucalyptusGen._vdot(compass, y_axis)))
    if eucalyptusGen._vlen(z_raw) < 1e-6:
        z_raw = eucalyptusGen._perp_vec(y_axis)
    z_axis = eucalyptusGen._vnorm(z_raw)
    x_axis = eucalyptusGen._vnorm(eucalyptusGen._vcross(y_axis, z_axis))
    z_axis = eucalyptusGen._vnorm(eucalyptusGen._vcross(x_axis, y_axis))
    return x_axis, y_axis, z_axis, compass


def _to_world(attach, x_axis, y_axis, z_axis, local):
    return eucalyptusGen._vadd(attach, eucalyptusGen._vadd(
        eucalyptusGen._vscale(x_axis, local[0]),
        eucalyptusGen._vadd(eucalyptusGen._vscale(y_axis, local[1]),
                            eucalyptusGen._vscale(z_axis, local[2]))))


# ---------------------------------------------------------------------------
# Geometry builders (low-poly)
# ---------------------------------------------------------------------------

def _leaf_template(length, width, curl):
    hw = width / 2.0
    base = (0.0, 0.0, 0.0)
    row1 = (hw * 0.75, length * 0.32, curl * length * 0.04)
    row1b = (-hw * 0.75, length * 0.32, curl * length * 0.04)
    row2 = (hw, length * 0.62, curl * length * 0.10)
    row2b = (-hw, length * 0.62, curl * length * 0.10)
    tip = (0.0, length, curl * length * 0.04)
    return base, row1, row1b, row2, row2b, tip


def _build_poly_leaf(attach, x_axis, y_axis, z_axis, length, width, curl, name):
    """3-face (1 tri, 1 quad, 1 tri) lanceolate leaf blade — well under the
    10-poly budget."""
    base, row1, row1b, row2, row2b, tip = _leaf_template(length, width, curl)
    w = {}
    for key, local in (('base', base), ('row1', row1), ('row1b', row1b),
                        ('row2', row2), ('row2b', row2b), ('tip', tip)):
        w[key] = _to_world(attach, x_axis, y_axis, z_axis, local)

    f1 = cmds.polyCreateFacet(p=[w['base'], w['row1'], w['row1b']], ch=False)[0]
    f2 = cmds.polyCreateFacet(
        p=[w['row1'], w['row2'], w['row2b'], w['row1b']], ch=False)[0]
    f3 = cmds.polyCreateFacet(p=[w['row2'], w['tip'], w['row2b']], ch=False)[0]
    mesh = cmds.polyUnite(f1, f2, f3, ch=False, mergeUVSets=True)[0]
    cmds.polyMergeVertex(mesh + '.vtx[*]', distance=0.01, ch=False)
    return cmds.rename(mesh, name)


def _build_card_leaf(attach, x_axis, y_axis, z_axis, length, width, name):
    """Single quad (2 tris) for alpha-cutout billboard leaves."""
    hw = width / 2.0
    corners = [(-hw, 0.0, 0.0), (hw, 0.0, 0.0),
              (hw, length, 0.0), (-hw, length, 0.0)]
    pts = [_to_world(attach, x_axis, y_axis, z_axis, c) for c in corners]
    mesh = cmds.polyCreateFacet(p=pts, ch=False)[0]
    return cmds.rename(mesh, name)


def _build_stem(p0, p1, x_axis, z_axis, radius, name, sides=4):
    """Thin low-poly prism connecting the twig surface to the leaf base."""
    length = eucalyptusGen._vlen(eucalyptusGen._vsub(p1, p0))
    if length < 1e-4:
        return None

    ring0, ring1 = [], []
    for i in range(sides):
        ang = 2.0 * math.pi * i / sides
        offset = eucalyptusGen._vadd(
            eucalyptusGen._vscale(x_axis, math.cos(ang) * radius),
            eucalyptusGen._vscale(z_axis, math.sin(ang) * radius))
        ring0.append(eucalyptusGen._vadd(p0, offset))
        ring1.append(eucalyptusGen._vadd(p1, offset))

    faces = []
    for i in range(sides):
        j = (i + 1) % sides
        faces.append(cmds.polyCreateFacet(
            p=[ring0[i], ring0[j], ring1[j], ring1[i]], ch=False)[0])
    mesh = cmds.polyUnite(*faces, ch=False, mergeUVSets=True)[0] \
        if len(faces) > 1 else faces[0]
    cmds.polyMergeVertex(mesh + '.vtx[*]', distance=0.01, ch=False)
    return cmds.rename(mesh, name)


# ---------------------------------------------------------------------------
# Shading
# ---------------------------------------------------------------------------

def _get_leaf_shader(species, mode):
    """Cached per species+mode aiStandardSurface. Card mode wires up a file
    texture (path left empty — connect your own leaf alpha texture in
    Hypershade) driving both colour and cutout opacity."""
    name = 'eucLeaf_{}_{}_mtl'.format(species, mode)
    sg_name = name + 'SG'
    if cmds.objExists(sg_name):
        return sg_name

    shader = cmds.shadingNode('aiStandardSurface', asShader=True, name=name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                   name=sg_name)
    cmds.connectAttr(shader + '.outColor', sg + '.surfaceShader')

    color = LEAF_PARAMS[species]['color']
    cmds.setAttr(shader + '.baseColor', *color, type='double3')
    cmds.setAttr(shader + '.specular', 0.25)
    cmds.setAttr(shader + '.specularRoughness', 0.45)

    if mode == 'card':
        file_node = cmds.shadingNode('file', asTexture=True, name=name + '_tex')
        place = cmds.shadingNode('place2dTexture', asUtility=True,
                                 name=name + '_place2d')
        cmds.connectAttr(place + '.outUV', file_node + '.uvCoord')
        cmds.connectAttr(place + '.outUvFilterSize', file_node + '.uvFilterSize')
        cmds.connectAttr(file_node + '.outColor', shader + '.baseColor')
        cmds.connectAttr(file_node + '.outTransparency', shader + '.opacity')
        cmds.setAttr(shader + '.thinWalled', 1)

    return sg


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_leaves(min_count=1, max_count=3, mode='poly', stems=True,
                    scale=1.0):
    """Generate leaves at every currently-selected curve CV.

    Args:
        min_count, max_count: random leaf count range per CV.
        mode: 'poly' (low-poly 3D blade) or 'card' (single alpha-cut quad).
        stems: build a thin connecting stem between the twig and each leaf.
        scale: size multiplier — match whatever scale the tree was
               generated at.

    Returns:
        List of created mesh transform names.
    """
    if mode not in ('poly', 'card'):
        raise ValueError('mode must be "poly" or "card"')
    lo, hi = sorted((min_count, max_count))

    by_curve = get_selected_cvs()
    if not by_curve:
        raise ValueError('No curve CVs selected — use Select Curves first.')

    created = []
    leaf_count = 0
    skipped_curves = []
    # Salted per call so repeated Generate clicks on the same curve(s) never
    # collide with names from a previous run — a name collision would get
    # silently renamed on cmds.parent(), leaving the returned name stale.
    call_salt = random.randint(1000, 9999)

    for curve, indices in by_curve.items():
        if not cmds.attributeQuery('radiusData', node=curve, exists=True):
            skipped_curves.append(curve)
            continue
        species = _infer_species(curve)
        if species is None or species not in LEAF_PARAMS:
            skipped_curves.append(curve)
            continue

        params = LEAF_PARAMS[species]
        min_fork_r = eucalyptusGen.SPECIES[species]['min_fork_radius']

        radii = cmds.getAttr(curve + '.radiusData')
        n_cvs = _cv_count(curve)
        positions = [cmds.pointPosition('{}.cv[{}]'.format(curve, i),
                                        world=True)
                    for i in range(n_cvs)]

        for idx in indices:
            if idx >= len(positions) or idx >= len(radii):
                continue
            cv_pos = tuple(positions[idx])
            local_r = radii[idx]

            if idx == 0:
                tangent = eucalyptusGen._vnorm(
                    eucalyptusGen._vsub(positions[1], positions[0]))
            elif idx == n_cvs - 1:
                tangent = eucalyptusGen._vnorm(
                    eucalyptusGen._vsub(positions[-1], positions[-2]))
            else:
                tangent = eucalyptusGen._vnorm(
                    eucalyptusGen._vsub(positions[idx + 1], positions[idx - 1]))

            size_mult = max(0.5, min(1.3, local_r / max(min_fork_r * 2.0, 0.1)))
            n_leaves = random.randint(lo, hi)
            phyllotaxis_offset = random.uniform(0, 360)

            for i in range(n_leaves):
                azimuth = (phyllotaxis_offset + i * eucalyptusGen.GOLDEN_ANGLE
                          + random.gauss(0, 15))
                # Random lean off straight-down, capped well below 90 so
                # leaves always favor gravity and never swing up.
                tilt = random.uniform(15.0, 55.0)
                x_axis, y_axis, z_axis, radial = _leaf_basis(
                    tangent, azimuth, tilt)

                length = random.uniform(*params['length']) * size_mult * scale
                width = length * params['width_ratio']
                curl = params['curl'] * random.uniform(0.7, 1.3)

                surface_pos = eucalyptusGen._vadd(
                    cv_pos, eucalyptusGen._vscale(radial, local_r))

                if stems:
                    stem_len = length * STEM_LENGTH_RATIO
                    attach_pos = eucalyptusGen._vadd(
                        surface_pos, eucalyptusGen._vscale(radial, stem_len))
                else:
                    attach_pos = surface_pos

                leaf_count += 1
                base_name = '{}_leaf{}_{:04d}'.format(
                    curve.rsplit('|', 1)[-1], call_salt, leaf_count)

                sg = _get_leaf_shader(species, mode)
                if mode == 'poly':
                    leaf_mesh = _build_poly_leaf(
                        attach_pos, x_axis, y_axis, z_axis,
                        length, width, curl, base_name)
                else:
                    leaf_mesh = _build_card_leaf(
                        attach_pos, x_axis, y_axis, z_axis,
                        length, width, base_name)
                cmds.sets(leaf_mesh, edit=True, forceElement=sg)
                cmds.parent(leaf_mesh, curve)
                created.append(leaf_mesh)

                if stems:
                    stem_radius = width * STEM_RADIUS_RATIO
                    stem_mesh = _build_stem(
                        surface_pos, attach_pos, x_axis, z_axis,
                        stem_radius, base_name + '_stem')
                    if stem_mesh:
                        cmds.sets(stem_mesh, edit=True, forceElement=sg)
                        cmds.parent(stem_mesh, curve)
                        created.append(stem_mesh)

    if skipped_curves:
        print('[eucalyptusLeaves] skipped (no tree data / unknown species): {}'
             .format(', '.join(c.rsplit('|', 1)[-1] for c in skipped_curves)))
    print('[eucalyptusLeaves] created {} leaves ({} nodes) on {} curve(s)'
         .format(leaf_count, len(created), len(by_curve) - len(skipped_curves)))
    return created

"""
Smooth Tool — API
Reconstructs and smooths a transform's world-space motion by tracking three
points (mesh vertices, NURBS curve CVs, or synthesized control-space points),
filtering their paths with a zero-phase Butterworth low-pass, and baking the
corrected transform back onto the rig control.
"""

import math
import maya.cmds as cmds
import maya.api.OpenMaya as om


# ---------------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------------

def _butter2_coeffs(cutoff_norm):
    """Return (b, a) for a 2nd-order Butterworth low-pass filter.

    cutoff_norm: normalised cutoff frequency  0 < Wn < 1  (1 = Nyquist).
    """
    cutoff_norm = max(0.001, min(cutoff_norm, 0.999))
    C = 1.0 / math.tan(math.pi * cutoff_norm / 2.0)
    C2 = C * C
    s2 = math.sqrt(2.0)
    a0 = 1.0 + s2 * C + C2
    b = [1.0 / a0, 2.0 / a0, 1.0 / a0]
    a = [1.0, (2.0 - 2.0 * C2) / a0, (1.0 - s2 * C + C2) / a0]
    return b, a


def _lfilter(b, a, x):
    """Direct-form II transposed IIR filter (single pass)."""
    n = len(x)
    y = [0.0] * n
    z1 = z2 = 0.0
    for i in range(n):
        y[i] = b[0] * x[i] + z1
        z1 = b[1] * x[i] - a[1] * y[i] + z2
        z2 = b[2] * x[i] - a[2] * y[i]
    return y


def _settling_length(a, epsilon=1e-4):
    """Samples needed for the filter's dominant pole to decay to *epsilon*.

    A fixed pad of 3*order (the classic default) only holds for moderate
    cutoffs. At the low cutoffs used for high smoothing strength the pole
    radius approaches 1 and the filter needs far more run-up, otherwise
    the reflected padding hasn't settled by the time it reaches the real
    data and the ends ring/overshoot.
    """
    pole_radius = min(0.999, math.sqrt(max(a[-1], 1e-6)))
    if pole_radius <= 1e-6:
        return 3 * len(a)
    return int(math.ceil(math.log(epsilon) / math.log(pole_radius)))


def _filtfilt(b, a, x):
    """Zero-phase digital filtering (forward–backward).

    Pads with reflected samples to suppress edge transients.
    """
    n = len(x)
    if n < 6:
        return list(x)
    pad = min(max(3 * max(len(a), len(b)), _settling_length(a)), n - 1)
    front = [2.0 * x[0] - x[i] for i in range(pad, 0, -1)]
    back = [2.0 * x[-1] - x[-(i + 2)] for i in range(pad)]
    padded = front + list(x) + back
    fwd = _lfilter(b, a, padded)
    rev = _lfilter(b, a, fwd[::-1])[::-1]
    return rev[pad: pad + n]


def _strength_to_cutoff(strength):
    """Map the artist-facing 0-5 strength slider to a Butterworth cutoff.

    Higher strength → lower cutoff → more smoothing.
    """
    return max(0.01, 0.8 * math.exp(-strength * 0.55))


def smooth_channel(data, strength):
    """Apply a zero-phase Butterworth low-pass to a single channel."""
    if strength <= 0.0 or len(data) < 4:
        return list(data)
    cutoff = _strength_to_cutoff(strength)
    b, a = _butter2_coeffs(cutoff)
    return _filtfilt(b, a, data)


# ---------------------------------------------------------------------------
# Falloff
# ---------------------------------------------------------------------------

def compute_falloff_weights(count, ratio=0.2):
    """Cosine ramp from 0 at edges to 1 at centre.

    ratio: fraction of the total range used for the ramp at each end.
    """
    if count < 3:
        return [1.0] * count
    ramp = max(1, int(count * ratio))
    weights = []
    for i in range(count):
        if i < ramp:
            w = 0.5 * (1.0 - math.cos(math.pi * i / ramp))
        elif i >= count - ramp:
            w = 0.5 * (1.0 - math.cos(math.pi * (count - 1 - i) / ramp))
        else:
            w = 1.0
        weights.append(w)
    return weights


# ---------------------------------------------------------------------------
# Vector / matrix helpers
# ---------------------------------------------------------------------------

def _v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _v_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _v_length(a):
    return math.sqrt(_v_dot(a, a))


def _v_normalize(a):
    ln = _v_length(a)
    if ln < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def _triangle_to_basis(p0, p1, p2):
    """Derive a right-handed orthonormal basis from three points.

    Returns (x_axis, y_axis, z_axis, centroid).
    """
    centroid = _v_scale(_v_add(_v_add(p0, p1), p2), 1.0 / 3.0)
    x_raw = _v_sub(p1, p0)
    x_axis = _v_normalize(x_raw)
    v_temp = _v_sub(p2, p0)
    z_axis = _v_normalize(_v_cross(x_axis, v_temp))
    y_axis = _v_cross(z_axis, x_axis)
    return x_axis, y_axis, z_axis, centroid


def _basis_to_mmatrix(x, y, z, pos):
    """Build an MMatrix from orthonormal basis vectors and position."""
    return om.MMatrix([
        x[0], x[1], x[2], 0.0,
        y[0], y[1], y[2], 0.0,
        z[0], z[1], z[2], 0.0,
        pos[0], pos[1], pos[2], 1.0,
    ])


def _mmatrix_from_list(m):
    return om.MMatrix(m)


def _mmatrix_to_list(m):
    return [m.getElement(r, c) for r in range(4) for c in range(4)]


def _unwrap(angle, ref):
    """Shift *angle* by a multiple of 2*pi so it lands closest to *ref*."""
    return angle + 2.0 * math.pi * round((ref - angle) / (2.0 * math.pi))


def _decompose_mmatrix(m, rotate_order=0, prev_euler=None):
    """Decompose an MMatrix into (translate, rotate_degrees, euler).

    Matrix-to-Euler decomposition has more than one valid solution (and
    each axis wraps at +/-180), so decoding every frame in isolation lets
    the picked solution/branch flip frame to frame -- most visibly right
    where a control's baseline rotation sits on the wrap boundary (e.g.
    a constant -180 to flip a character's facing). When *prev_euler* is
    given, pick whichever of the two matrix solutions (see
    MEulerRotation.alternateSolution) unwraps closest to it, keeping the
    baked rotation curve continuous instead of snapping across the seam.
    """
    tm = om.MTransformationMatrix(m)
    t = tm.translation(om.MSpace.kWorld)
    # Maya's .rotateOrder attribute values (0-5) map to these named orders,
    # but reorderIt()/the MEulerRotation constructor below take
    # MEulerRotation's own kXYZ..kZYX constants (0-5) -- a *different*
    # enum from MTransformationMatrix's (1-6). Mixing them silently
    # reorders to the wrong axis order (and kZYX=6 from the wrong enum is
    # out of range for MEulerRotation entirely), corrupting every
    # decomposed frame -- not just an edge case.
    ro_map = {
        0: om.MEulerRotation.kXYZ,
        1: om.MEulerRotation.kYZX,
        2: om.MEulerRotation.kZXY,
        3: om.MEulerRotation.kXZY,
        4: om.MEulerRotation.kYXZ,
        5: om.MEulerRotation.kZYX,
    }
    order = ro_map.get(rotate_order, om.MEulerRotation.kXYZ)
    euler = tm.rotation()
    euler.reorderIt(order)

    if prev_euler is not None:
        candidates = [euler, euler.alternateSolution()]
        unwrapped = [
            (_unwrap(c.x, prev_euler.x),
             _unwrap(c.y, prev_euler.y),
             _unwrap(c.z, prev_euler.z))
            for c in candidates
        ]
        best = min(
            unwrapped,
            key=lambda e: (e[0] - prev_euler.x) ** 2
                        + (e[1] - prev_euler.y) ** 2
                        + (e[2] - prev_euler.z) ** 2)
        euler = om.MEulerRotation(best[0], best[1], best[2], order)

    rx, ry, rz = math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)
    return (t.x, t.y, t.z), (rx, ry, rz), euler


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

class SmoothToolCore:

    def __init__(self):
        self.source_mesh = None
        self.bake_target = None
        self.parent_space_obj = None
        self.vert_indices = []
        self.frames = []

        # Per-frame sampled data
        self.vert_positions = [[], [], []]  # 3 × list of (x,y,z)
        self.ctrl_matrices = []             # list of 16-float lists
        self.parent_matrices = []           # list of 16-float lists

        # Original tracked-triangle transform, decomposed once into
        # continuous translate/euler channels (see _compute_orig_channels).
        self._orig_translate = []           # list of (x,y,z)
        self._orig_euler = []               # list of (rx,ry,rz) degrees
        self._local_offsets = [(0, 0, 0)] * 3

        # Smoothed / blended channel data, in the same (translate, euler)
        # representation, plus the tracked-point positions reconstructed
        # from them for the viewport preview curves.
        self._smoothed_translate = []
        self._smoothed_euler = []
        self._blended_translate = []
        self._blended_euler = []
        self._smoothed = [[], [], []]       # 3 × list of (x,y,z)
        self._blended = [[], [], []]        # 3 × list of (x,y,z)

        # Viewport curves
        self.original_curves = []
        self.smooth_curves = []
        self.blend_curves = []

        # Settings
        self.strength = 1.0
        self.blend = 0.0
        self.falloff = 0.2

    # ------------------------------------------------------------------
    # Frame range
    # ------------------------------------------------------------------

    @staticmethod
    def get_frame_range():
        """Return (start, end) from the timeline selection or playback range."""
        tc = 'timeControl1'
        try:
            if cmds.timeControl(tc, q=True, rangeVisible=True):
                raw = cmds.timeControl(tc, q=True, range=True)
                parts = raw.replace('"', '').split(':')
                return int(float(parts[0])), int(float(parts[1]))
        except Exception:
            pass
        return (int(cmds.playbackOptions(q=True, minTime=True)),
                int(cmds.playbackOptions(q=True, maxTime=True)))

    # ------------------------------------------------------------------
    # Vertex picking
    # ------------------------------------------------------------------

    @staticmethod
    def _find_component_shape(mesh):
        """Return (shape, comp_type) for *mesh* -- a poly mesh ('vtx') or a
        NURBS curve ('cv'). Mesh shapes are preferred if both exist."""
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        shape, comp_type = None, None
        for s in shapes:
            t = cmds.objectType(s)
            if t == 'mesh':
                return s, 'vtx'
            if t == 'nurbsCurve' and shape is None:
                shape, comp_type = s, 'cv'
        return shape, comp_type

    @staticmethod
    def find_spread_vertices(mesh, count=3):
        """Pick *count* maximally-spread vertices/CVs on *mesh*."""
        shape, comp_type = SmoothToolCore._find_component_shape(mesh)
        if shape is None:
            raise RuntimeError(
                '{} has no mesh or NURBS curve shape.'.format(mesh))
        verts = cmds.ls('{}.{}[*]'.format(shape, comp_type), flatten=True)
        if not verts:
            raise RuntimeError('{} has no {}.'.format(
                mesh, 'vertices' if comp_type == 'vtx' else 'CVs'))
        positions = [cmds.xform(v, q=True, t=True, ws=True) for v in verts]
        p0 = positions[0]
        i1 = max(range(len(positions)),
                 key=lambda i: _v_length(_v_sub(positions[i], p0)))
        p1 = positions[i1]
        i2 = max(range(len(positions)),
                 key=lambda i: _v_length(_v_sub(positions[i], p0))
                              + _v_length(_v_sub(positions[i], p1)))
        indices = [0, i1, i2]
        return indices[:count]

    @staticmethod
    def _transform_of(node):
        """Return *node*'s transform if it's a shape, else *node* itself.

        Component selection reports the shape as the owning node for
        NURBS curve CVs but the transform for poly vertices, so this
        normalises both back to the transform the UI fields track.
        """
        if cmds.objectType(node, isAType='shape'):
            parents = cmds.listRelatives(node, parent=True)
            return parents[0] if parents else node
        return node

    @staticmethod
    def indices_from_selection():
        """Read three selected vertices or CVs (not mixed) and return
        (transform, [idx, idx, idx])."""
        sel = cmds.ls(selection=True, flatten=True)
        comp_sel = [s for s in sel if '.vtx[' in s or '.cv[' in s]
        if len(comp_sel) != 3:
            raise RuntimeError('Select exactly 3 vertices or CVs.')
        kinds = set('cv' if '.cv[' in s else 'vtx' for s in comp_sel)
        if len(kinds) != 1:
            raise RuntimeError(
                'Selection mixes vertices and CVs -- pick one type.')
        mesh = SmoothToolCore._transform_of(comp_sel[0].split('.')[0])
        indices = []
        for v in comp_sel:
            idx = int(v.split('[')[1].rstrip(']'))
            indices.append(idx)
        return mesh, indices

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def sample(self, mesh, vert_indices, bake_target, start, end,
               parent=None):
        """Sample tracking-point positions and control matrix per frame."""
        self.source_mesh = mesh
        self.bake_target = bake_target
        self.parent_space_obj = parent
        self.vert_indices = list(vert_indices)
        self.frames = list(range(start, end + 1))

        self.vert_positions = [[], [], []]
        self.ctrl_matrices = []
        self.parent_matrices = []

        shape, comp_type = self._find_component_shape(mesh)
        if shape is None:
            shape, comp_type = mesh, 'vtx'

        for frame in self.frames:
            cmds.currentTime(frame)

            for vi in range(3):
                vtx = '{}.{}[{}]'.format(shape, comp_type, vert_indices[vi])
                pos = cmds.xform(vtx, q=True, t=True, ws=True)
                if parent:
                    pos = self._to_parent_space(pos, parent)
                self.vert_positions[vi].append(tuple(pos))

            m = cmds.xform(bake_target, q=True, matrix=True, ws=True)
            self.ctrl_matrices.append(m)

            if parent:
                pm = cmds.xform(parent, q=True, matrix=True, ws=True)
                self.parent_matrices.append(pm)

        self._compute_orig_channels()

    _VIRTUAL_LOCAL_POINTS = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]

    def sample_control(self, target, start, end, parent=None, size=10.0):
        """Sample a bare control with no mesh to track.

        Builds 3 virtual points rigidly attached to *target* (offset along
        its own local axes) instead of tracking mesh vertices, so a
        control with no geometry can still be run through the same
        triangle-basis reconstruction as the vertex-based path. The point
        spacing (*size*) is arbitrary -- it only needs to be non-zero and
        non-degenerate, since it cancels out in the basis math.
        """
        self.source_mesh = None
        self.bake_target = target
        self.parent_space_obj = parent
        self.vert_indices = []
        self.frames = list(range(start, end + 1))

        self.vert_positions = [[], [], []]
        self.ctrl_matrices = []
        self.parent_matrices = []

        local_pts = [_v_scale(p, size) for p in self._VIRTUAL_LOCAL_POINTS]

        for frame in self.frames:
            cmds.currentTime(frame)

            m = cmds.xform(target, q=True, matrix=True, ws=True)
            wm = om.MMatrix(m)
            for vi in range(3):
                lp = om.MPoint(*local_pts[vi])
                wp = lp * wm
                pos = (wp.x, wp.y, wp.z)
                if parent:
                    pos = self._to_parent_space(pos, parent)
                self.vert_positions[vi].append(pos)

            self.ctrl_matrices.append(m)

            if parent:
                pm = cmds.xform(parent, q=True, matrix=True, ws=True)
                self.parent_matrices.append(pm)

        self._compute_orig_channels()

    @staticmethod
    def _to_parent_space(world_pos, parent):
        """Transform a world-space point into parent's local space."""
        pm = cmds.xform(parent, q=True, matrix=True, ws=True)
        inv = om.MMatrix(pm).inverse()
        pt = om.MPoint(world_pos[0], world_pos[1], world_pos[2])
        local = pt * inv
        return (local.x, local.y, local.z)

    # ------------------------------------------------------------------
    # Rigid transform channels
    #
    # The tracked triangle's per-frame basis is decomposed once into a
    # continuous (translate, euler) pair rather than smoothing each
    # tracked point's raw x/y/z independently. Filtering a rotating
    # rigid body's Cartesian point coordinates per-axis doesn't preserve
    # rigidity -- the triangle silently distorts as smoothing strength
    # rises, and re-deriving a basis from a distorted triangle can yield
    # a rotation far off from the original, worst of all near a Euler
    # singularity. Filtering the continuous Euler channels themselves
    # (same technique already used for translate) is the mathematically
    # sound way to smooth rotation and keeps the delta exactly identity
    # wherever blend/smoothing has no effect.
    # ------------------------------------------------------------------

    @staticmethod
    def _compose_mmatrix(translate, euler_deg):
        """Build a world matrix from a translate + XYZ-euler-degrees pair."""
        ex, ey, ez = (math.radians(a) for a in euler_deg)
        tm = om.MTransformationMatrix()
        tm.setRotation(om.MEulerRotation(ex, ey, ez, om.MEulerRotation.kXYZ))
        tm.setTranslation(om.MVector(*translate), om.MSpace.kWorld)
        return tm.asMatrix()

    def _compute_orig_channels(self):
        """Decompose the tracked triangle into continuous translate/euler
        channels, and the tracked points' average offset in that frame's
        local space (assumed rigid -- exact for a control, an approximation
        for a deforming mesh)."""
        n = len(self.frames)
        self._orig_translate = []
        self._orig_euler = []
        local_accum = [[0.0, 0.0, 0.0] for _ in range(3)]
        prev_euler = None
        for i in range(n):
            x, y, z, c = _triangle_to_basis(
                self.vert_positions[0][i], self.vert_positions[1][i],
                self.vert_positions[2][i])
            m = _basis_to_mmatrix(x, y, z, c)
            t, r, prev_euler = _decompose_mmatrix(m, 0, prev_euler)
            self._orig_translate.append(t)
            self._orig_euler.append(r)

            inv = m.inverse()
            for k in range(3):
                lp = om.MPoint(*self.vert_positions[k][i]) * inv
                local_accum[k][0] += lp.x
                local_accum[k][1] += lp.y
                local_accum[k][2] += lp.z

        if n > 0:
            self._local_offsets = [
                (local_accum[k][0] / n, local_accum[k][1] / n,
                 local_accum[k][2] / n) for k in range(3)]

        self._smoothed_translate = list(self._orig_translate)
        self._smoothed_euler = list(self._orig_euler)
        self._blended_translate = list(self._orig_translate)
        self._blended_euler = list(self._orig_euler)
        self._smoothed = [list(vp) for vp in self.vert_positions]
        self._blended = [list(vp) for vp in self.vert_positions]

    def _positions_from_channels(self, translates, eulers):
        """Reconstruct the 3 tracked-point positions implied by a
        (translate, euler) sequence, for viewport preview curves."""
        out = [[], [], []]
        for t, e in zip(translates, eulers):
            m = self._compose_mmatrix(t, e)
            for k in range(3):
                wp = om.MPoint(*self._local_offsets[k]) * m
                out[k].append((wp.x, wp.y, wp.z))
        return out

    # ------------------------------------------------------------------
    # Viewport curves
    # ------------------------------------------------------------------

    _COLORS = {
        'orig':   (0.5, 0.1, 0.1),
        'smooth': (0.7, 0.7, 0.7),
        'blend':  (0.0, 1.0, 0.0),
    }

    def create_curves(self):
        """Build the original / smooth / blend curve sets.

        When a parent space is set, the curves are built directly from the
        parent-local point data and parented under that object, so their
        shape shows only the local motion (the parent's own motion rides
        along through the DAG rather than being baked into the CVs).
        """
        self.delete_curves()
        for vi in range(3):
            pts = self.vert_positions[vi]
            base = '{}_{}'.format(self.bake_target, vi)

            orig = cmds.curve(p=pts, d=3, name='{}_orig'.format(base))
            smth = cmds.curve(p=pts, d=3, name='{}_smooth'.format(base))
            blnd = cmds.curve(p=pts, d=3, name='{}_blend'.format(base))

            if self.parent_space_obj:
                cmds.parent(orig, smth, blnd, self.parent_space_obj,
                            relative=True)

            self.original_curves.append(orig)
            self.smooth_curves.append(smth)
            self.blend_curves.append(blnd)

            for crv, tag in [(orig, 'orig'), (smth, 'smooth'), (blnd, 'blend')]:
                cmds.setAttr('{}.overrideEnabled'.format(crv), 1)
                cmds.setAttr('{}.overrideRGBColors'.format(crv), 1)
                r, g, b = self._COLORS[tag]
                cmds.setAttr('{}.overrideColorRGB'.format(crv), r, g, b)

    def delete_curves(self):
        for crv in self.original_curves + self.smooth_curves + self.blend_curves:
            if cmds.objExists(crv):
                cmds.delete(crv)
        self.original_curves = []
        self.smooth_curves = []
        self.blend_curves = []

    def _write_curve_positions(self, curve, positions):
        """Update every CV on *curve* with new positions."""
        for j, pos in enumerate(positions):
            cmds.setAttr('{}.cp[{}]'.format(curve, j), *pos)

    # ------------------------------------------------------------------
    # Smooth / blend
    # ------------------------------------------------------------------

    def update_smooth(self, strength):
        """Recompute the smoothed translate/euler channels."""
        self.strength = strength

        txs = [t[0] for t in self._orig_translate]
        tys = [t[1] for t in self._orig_translate]
        tzs = [t[2] for t in self._orig_translate]
        self._smoothed_translate = list(zip(
            smooth_channel(txs, strength),
            smooth_channel(tys, strength),
            smooth_channel(tzs, strength)))

        exs = [e[0] for e in self._orig_euler]
        eys = [e[1] for e in self._orig_euler]
        ezs = [e[2] for e in self._orig_euler]
        self._smoothed_euler = list(zip(
            smooth_channel(exs, strength),
            smooth_channel(eys, strength),
            smooth_channel(ezs, strength)))

        self._smoothed = self._positions_from_channels(
            self._smoothed_translate, self._smoothed_euler)
        for vi in range(3):
            self._write_curve_positions(
                self.smooth_curves[vi], self._smoothed[vi])
        self.update_blend(self.blend)

    def update_blend(self, blend):
        """Crossfade between original and smoothed, applying edge falloff."""
        self.blend = blend
        n = len(self.frames)
        weights = compute_falloff_weights(n, self.falloff)

        blended_t = []
        blended_e = []
        for i in range(n):
            w = weights[i] * blend
            ot, st = self._orig_translate[i], self._smoothed_translate[i]
            blended_t.append(tuple(
                ot[k] + w * (st[k] - ot[k]) for k in range(3)))
            oe, se = self._orig_euler[i], self._smoothed_euler[i]
            blended_e.append(tuple(
                oe[k] + w * (se[k] - oe[k]) for k in range(3)))
        self._blended_translate = blended_t
        self._blended_euler = blended_e

        self._blended = self._positions_from_channels(blended_t, blended_e)
        for vi in range(3):
            self._write_curve_positions(
                self.blend_curves[vi], self._blended[vi])

    def update_falloff(self, falloff):
        """Re-apply blend with new falloff ratio."""
        self.falloff = falloff
        self.update_blend(self.blend)

    # ------------------------------------------------------------------
    # Transform reconstruction
    # ------------------------------------------------------------------

    def _reconstruct_delta(self, frame_idx):
        """Return the MMatrix delta between the original and blended
        (translate, euler) channels -- identity wherever blend has no
        effect, by construction."""
        orig_m = self._compose_mmatrix(
            self._orig_translate[frame_idx], self._orig_euler[frame_idx])
        blend_m = self._compose_mmatrix(
            self._blended_translate[frame_idx], self._blended_euler[frame_idx])
        return orig_m.inverse() * blend_m

    # ------------------------------------------------------------------
    # Baking
    # ------------------------------------------------------------------

    def bake(self, to_layer=True, additive=True):
        """Bake the smoothed transform onto self.bake_target."""
        if not self.bake_target or not cmds.objExists(self.bake_target):
            raise RuntimeError('Bake target does not exist.')

        rot_order = cmds.getAttr('{}.rotateOrder'.format(self.bake_target))
        n = len(self.frames)

        # Pre-compute smoothed world matrices
        smoothed_matrices = []
        for i in range(n):
            delta = self._reconstruct_delta(i)
            if self.parent_space_obj and self.parent_matrices:
                parent_m = _mmatrix_from_list(self.parent_matrices[i])
                delta_world = parent_m.inverse() * delta * parent_m
            else:
                delta_world = delta
            orig_ctrl = _mmatrix_from_list(self.ctrl_matrices[i])
            smoothed_matrices.append(orig_ctrl * delta_world)

        # Pre-sample the bake target's parent world matrices so we can convert
        # world→local without stepping the timeline during the key loop.
        node_parents = cmds.listRelatives(
            self.bake_target, parent=True, fullPath=True)
        parent_node = node_parents[0] if node_parents else None
        bake_parent_matrices = []
        if parent_node:
            for frame in self.frames:
                cmds.currentTime(frame)
                pm = cmds.xform(parent_node, q=True, matrix=True, ws=True)
                bake_parent_matrices.append(_mmatrix_from_list(pm))

        bake_attrs = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']

        # Decompose the *original* local matrices first, chaining continuity
        # frame-to-frame, to get a clean reference Euler branch per frame.
        # The smoothed decomposition below is anchored to this per-frame
        # reference rather than to its own previous output: anchoring to
        # itself would let the branch drift away from the original curve's
        # representation wherever smoothing is heavy, so that even at a
        # zero-blend edge frame (where the smoothed matrix is numerically
        # identical to the original) the wrong branch could get picked --
        # e.g. (rx, ry, rz) vs the equivalent (rx+/-180, 180-ry, rz+/-180).
        # Both represent the same rotation, but an additive anim layer that
        # blends rotation component-wise needs the *matching* branch or the
        # combined result is a real, visibly wrong pose, not just a
        # differently-labelled equivalent one -- which is what produced the
        # "weird angle" snap at the last frame that this anchoring fixes.
        orig_eulers = []
        prev_orig_euler = None
        for i in range(n):
            orig_world = _mmatrix_from_list(self.ctrl_matrices[i])
            if bake_parent_matrices:
                orig_local = orig_world * bake_parent_matrices[i].inverse()
            else:
                orig_local = orig_world
            _, _, prev_orig_euler = _decompose_mmatrix(
                orig_local, rot_order, prev_orig_euler)
            orig_eulers.append(prev_orig_euler)

        cmds.undoInfo(openChunk=True, chunkName='SmoothTool_Bake')
        layer_name = None
        try:
            if to_layer:
                layer_name = '{}_smooth'.format(self.bake_target)
                idx = 1
                while cmds.animLayer(layer_name, q=True, exists=True):
                    layer_name = '{}_smooth_{}'.format(self.bake_target, idx)
                    idx += 1
                # animLayer sanitizes characters like '|' out of the node
                # name it actually creates (bake_target may be a full DAG
                # path when its short name is ambiguous) -- use the name
                # Maya actually assigned, not the one we guessed, or the
                # later -edit -attribute calls can't resolve the layer.
                layer_name = cmds.animLayer(layer_name, override=not additive)
                for attr in bake_attrs:
                    cmds.animLayer(
                        layer_name, e=True,
                        attribute='{}.{}'.format(self.bake_target, attr))

            for i, frame in enumerate(self.frames):
                smooth_world = smoothed_matrices[i]

                if bake_parent_matrices:
                    inv_parent = bake_parent_matrices[i].inverse()
                    smooth_local = smooth_world * inv_parent
                else:
                    smooth_local = smooth_world

                smooth_t, smooth_r, _ = _decompose_mmatrix(
                    smooth_local, rot_order, orig_eulers[i])
                # setKeyframe's animLayer flag wants the absolute combined
                # result, not a pre-computed delta — Maya derives the
                # layer-local (additive) contribution itself.
                vals = list(smooth_t) + list(smooth_r)

                for attr, val in zip(bake_attrs, vals):
                    if layer_name:
                        cmds.setKeyframe(self.bake_target, t=frame,
                                         at=attr, v=val, animLayer=layer_name)
                    else:
                        cmds.setKeyframe(self.bake_target, t=frame,
                                         at=attr, v=val)

            self.delete_curves()

        except Exception:
            raise
        finally:
            cmds.undoInfo(closeChunk=True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def reset(self):
        """Remove all helper objects and clear internal state."""
        self.delete_curves()
        self.source_mesh = None
        self.bake_target = None
        self.parent_space_obj = None
        self.vert_indices = []
        self.frames = []
        self.vert_positions = [[], [], []]
        self.ctrl_matrices = []
        self.parent_matrices = []
        self._orig_translate = []
        self._orig_euler = []
        self._local_offsets = [(0, 0, 0)] * 3
        self._smoothed_translate = []
        self._smoothed_euler = []
        self._blended_translate = []
        self._blended_euler = []
        self._smoothed = [[], [], []]
        self._blended = [[], [], []]

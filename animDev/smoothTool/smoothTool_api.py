"""
Smooth Tool — API
Reconstructs and smooths a transform's world-space motion by tracking three
mesh vertices, filtering their paths with a zero-phase Butterworth low-pass,
and baking the corrected transform back onto the rig control.
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


def _decompose_mmatrix(m, rotate_order=0):
    """Decompose an MMatrix into (translate, rotate_degrees)."""
    tm = om.MTransformationMatrix(m)
    t = tm.translation(om.MSpace.kWorld)
    ro_map = {
        0: om.MTransformationMatrix.kXYZ,
        1: om.MTransformationMatrix.kYZX,
        2: om.MTransformationMatrix.kZXY,
        3: om.MTransformationMatrix.kXZY,
        4: om.MTransformationMatrix.kYXZ,
        5: om.MTransformationMatrix.kZYX,
    }
    euler = tm.rotation()
    euler.reorderIt(ro_map.get(rotate_order, om.MTransformationMatrix.kXYZ))
    rx, ry, rz = math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z)
    return (t.x, t.y, t.z), (rx, ry, rz)


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

        # Smoothed / blended channel data  (3 verts × 3 axes)
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
    def find_spread_vertices(mesh, count=3):
        """Pick *count* maximally-spread vertices on *mesh*."""
        verts = cmds.ls('{}.vtx[*]'.format(mesh), flatten=True)
        if not verts:
            raise RuntimeError('{} has no vertices.'.format(mesh))
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
    def indices_from_selection():
        """Read three selected vertices and return (mesh_transform, [idx, idx, idx])."""
        sel = cmds.ls(selection=True, flatten=True)
        vert_sel = [s for s in sel if '.vtx[' in s]
        if len(vert_sel) != 3:
            raise RuntimeError('Select exactly 3 vertices.')
        mesh = vert_sel[0].split('.')[0]
        indices = []
        for v in vert_sel:
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

        shape = None
        shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        for s in shapes:
            if cmds.objectType(s) == 'mesh':
                shape = s
                break
        if shape is None:
            shape = mesh

        for frame in self.frames:
            cmds.currentTime(frame)

            for vi in range(3):
                vtx = '{}.vtx[{}]'.format(shape, vert_indices[vi])
                pos = cmds.xform(vtx, q=True, t=True, ws=True)
                if parent:
                    pos = self._to_parent_space(pos, parent)
                self.vert_positions[vi].append(tuple(pos))

            m = cmds.xform(bake_target, q=True, matrix=True, ws=True)
            self.ctrl_matrices.append(m)

            if parent:
                pm = cmds.xform(parent, q=True, matrix=True, ws=True)
                self.parent_matrices.append(pm)

        self._smoothed = [list(vp) for vp in self.vert_positions]
        self._blended = [list(vp) for vp in self.vert_positions]

    @staticmethod
    def _to_parent_space(world_pos, parent):
        """Transform a world-space point into parent's local space."""
        pm = cmds.xform(parent, q=True, matrix=True, ws=True)
        inv = om.MMatrix(pm).inverse()
        pt = om.MPoint(world_pos[0], world_pos[1], world_pos[2])
        local = pt * inv
        return (local.x, local.y, local.z)

    # ------------------------------------------------------------------
    # Viewport curves
    # ------------------------------------------------------------------

    _COLORS = {
        'orig':   (0.5, 0.1, 0.1),
        'smooth': (0.7, 0.7, 0.7),
        'blend':  (0.0, 1.0, 0.0),
    }

    def create_curves(self):
        """Build the original / smooth / blend curve sets."""
        self.delete_curves()
        for vi in range(3):
            pts = self.vert_positions[vi]
            if self.parent_space_obj:
                pts = [self._local_to_world(p, fi) for fi, p in enumerate(pts)]
            base = '{}_{}'.format(self.bake_target, vi)

            orig = cmds.curve(p=pts, d=3, name='{}_orig'.format(base))
            smth = cmds.curve(p=pts, d=3, name='{}_smooth'.format(base))
            blnd = cmds.curve(p=pts, d=3, name='{}_blend'.format(base))

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

    def _local_to_world(self, local_pos, frame_index):
        """Convert a parent-space position back to world for display."""
        if not self.parent_matrices:
            return local_pos
        pm = _mmatrix_from_list(self.parent_matrices[frame_index])
        pt = om.MPoint(local_pos[0], local_pos[1], local_pos[2])
        world = pt * pm
        return (world.x, world.y, world.z)

    def _write_curve_positions(self, curve, positions, parent_space=False):
        """Update every CV on *curve* with new positions."""
        for j, pos in enumerate(positions):
            if parent_space:
                pos = self._local_to_world(pos, j)
            cmds.setAttr('{}.cp[{}]'.format(curve, j), *pos)

    # ------------------------------------------------------------------
    # Smooth / blend
    # ------------------------------------------------------------------

    def update_smooth(self, strength):
        """Recompute the smoothed vertex paths."""
        self.strength = strength
        for vi in range(3):
            raw = self.vert_positions[vi]
            xs = [p[0] for p in raw]
            ys = [p[1] for p in raw]
            zs = [p[2] for p in raw]
            sx = smooth_channel(xs, strength)
            sy = smooth_channel(ys, strength)
            sz = smooth_channel(zs, strength)
            self._smoothed[vi] = list(zip(sx, sy, sz))
            self._write_curve_positions(
                self.smooth_curves[vi], self._smoothed[vi],
                parent_space=bool(self.parent_space_obj))
        self.update_blend(self.blend)

    def update_blend(self, blend):
        """Crossfade between original and smoothed, applying edge falloff."""
        self.blend = blend
        n = len(self.frames)
        weights = compute_falloff_weights(n, self.falloff)

        for vi in range(3):
            orig = self.vert_positions[vi]
            smth = self._smoothed[vi]
            blended = []
            for i in range(n):
                w = weights[i] * blend
                bx = orig[i][0] + w * (smth[i][0] - orig[i][0])
                by = orig[i][1] + w * (smth[i][1] - orig[i][1])
                bz = orig[i][2] + w * (smth[i][2] - orig[i][2])
                blended.append((bx, by, bz))
            self._blended[vi] = blended
            self._write_curve_positions(
                self.blend_curves[vi], blended,
                parent_space=bool(self.parent_space_obj))

    def update_falloff(self, falloff):
        """Re-apply blend with new falloff ratio."""
        self.falloff = falloff
        self.update_blend(self.blend)

    # ------------------------------------------------------------------
    # Transform reconstruction
    # ------------------------------------------------------------------

    def _reconstruct_delta(self, frame_idx):
        """Return the MMatrix delta between original and blended triangles."""
        op = self.vert_positions
        bp = self._blended
        ox, oy, oz, oc = _triangle_to_basis(
            op[0][frame_idx], op[1][frame_idx], op[2][frame_idx])
        bx, by, bz, bc = _triangle_to_basis(
            bp[0][frame_idx], bp[1][frame_idx], bp[2][frame_idx])
        orig_m = _basis_to_mmatrix(ox, oy, oz, oc)
        blend_m = _basis_to_mmatrix(bx, by, bz, bc)
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

        cmds.undoInfo(openChunk=True, chunkName='SmoothTool_Bake')
        layer_name = None
        try:
            if to_layer:
                layer_name = '{}_smooth'.format(self.bake_target)
                idx = 1
                while cmds.animLayer(layer_name, q=True, exists=True):
                    layer_name = '{}_smooth_{}'.format(self.bake_target, idx)
                    idx += 1
                cmds.animLayer(layer_name, override=not additive)
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

                smooth_t, smooth_r = _decompose_mmatrix(smooth_local, rot_order)
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
        self._smoothed = [[], [], []]
        self._blended = [[], [], []]

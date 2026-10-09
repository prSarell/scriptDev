"""
Smooth Tool -- FK Chain
Extends Smooth Tool to smooth an entire FK chain's rotations from a single
smoothed tip trajectory: the tip's position is smoothed by the existing
SmoothToolCore engine unchanged, the rest of the chain's positions are
solved per frame with FABRIK back to a pinned base, orientation is derived
via a parallel-transport up-vector chained segment to segment (seeded from
the base's own live rotation, not a fixed rest reference), and the result
is baked as rotate-only keys across every control -- translate is never
touched anywhere in this module, so the base's original position survives
automatically.

Kept as its own module rather than folded into SmoothToolCore -- see
smoothTool_roadmap.md's explicit architectural note that chain-solving is
a different kind of problem (spatial constraint satisfaction, not temporal
signal filtering) and should call back into SmoothToolCore rather than
grow it.
"""

import os
import sys

import maya.cmds as cmds
import maya.api.OpenMaya as om

_DIR = os.path.dirname(__file__)
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from smoothTool_api import (
    SmoothToolCore,
    _v_sub, _v_add, _v_scale, _v_cross, _v_length, _v_normalize,
)


def _v_dist2(a, b):
    d = _v_sub(a, b)
    return d[0] * d[0] + d[1] * d[1] + d[2] * d[2]


# ---------------------------------------------------------------------------
# Chain discovery / ordering
#
# Rigs in practice are a mix of genuinely parented FK hierarchies and
# constraint-driven setups where the controls aren't parented to each
# other at all -- so chain discovery can't assume a DAG walk always works.
# Two independent ways to build the ordered base->tip list are provided;
# the UI offers both and lets the user pick whichever fits the rig.
# ---------------------------------------------------------------------------

def order_chain_from_parent_walk(base, tip):
    """Walk the DAG from *tip* up to *base* and return the ordered
    base->tip chain.

    Only valid for a genuinely parented hierarchy. Walking upward from the
    tip via each node's single parent is inherently unambiguous (a
    transform has at most one parent), so -- unlike a downward walk from
    the root, which needs explicit branching validation -- this needs no
    such check: it either reaches *base* or it doesn't.
    """
    base_long = cmds.ls(base, long=True)[0]
    node = cmds.ls(tip, long=True)[0]
    chain = [node]
    while node != base_long:
        parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if not parents:
            raise RuntimeError(
                '"{}" is not an ancestor of "{}" -- reached the top of the '
                'hierarchy without finding it. This chain may be '
                'constraint-driven rather than parented -- use multi-select '
                '+ Reorder by Arc Length instead.'.format(base, tip))
        node = parents[0]
        chain.append(node)
        if len(chain) > 500:
            raise RuntimeError(
                'Chain walk from "{}" exceeded 500 nodes -- probable cycle '
                'or wrong base/tip pair.'.format(tip))
    chain.reverse()
    return chain


def order_chain_by_arc_length(controls, base, frame=None):
    """Order an arbitrary (possibly unordered) *controls* selection
    base->tip by a base-anchored nearest-neighbour greedy walk through
    their world positions at *frame* (current time if None).

    Works regardless of parenting -- the only requirement is that the
    controls' rest/current positions actually trace the chain's shape.
    The greedy walk doubles as the arc-length order for a roughly linear
    chain, so no separate re-sort against a pre-built reference curve is
    needed (unlike tlmParticleChain._orderControlsAlongChain, which sorts
    against a dedicated rest curve that doesn't exist for arbitrary FK
    controls here).
    """
    if frame is not None:
        cmds.currentTime(frame)

    base_long = cmds.ls(base, long=True)[0]
    all_long = [cmds.ls(c, long=True)[0] for c in controls]
    if base_long not in all_long:
        all_long = [base_long] + all_long

    positions = {c: cmds.xform(c, q=True, ws=True, t=True) for c in all_long}
    pool = [c for c in all_long if c != base_long]

    ordered = [base_long]
    cur = base_long
    while pool:
        cur_pos = positions[cur]
        nxt = min(pool, key=lambda c: _v_dist2(positions[c], cur_pos))
        ordered.append(nxt)
        pool.remove(nxt)
        cur = nxt
    return ordered


def sample_rest_lengths(ordered_chain, frame=None):
    """Per-bone distance between consecutive controls' world positions at
    *frame* (current time if None) -- the fixed lengths FABRIK solves to."""
    if frame is not None:
        cmds.currentTime(frame)
    lengths = []
    for a, b in zip(ordered_chain[:-1], ordered_chain[1:]):
        pa = cmds.xform(a, q=True, ws=True, t=True)
        pb = cmds.xform(b, q=True, ws=True, t=True)
        lengths.append(_v_length(_v_sub(pb, pa)))
    return lengths


# ---------------------------------------------------------------------------
# FABRIK
#
# No existing FABRIK/CCD/chain-IK solver exists anywhere in this repo --
# this is new code. Standard two-pass (backward tip->base, forward
# base->tip) position solve, chosen over CCD per prior design discussion:
# position-space, hands back joint positions directly, doesn't get
# twitchy near-singular configurations the way angle-based CCD can.
# ---------------------------------------------------------------------------

def solve_fabrik(positions, lengths, base_pos, target_pos,
                  iterations=10, tolerance=0.01):
    """Solve chain positions so consecutive points satisfy *lengths*, the
    base sits at *base_pos*, and the tip reaches as close to *target_pos*
    as the chain's total length allows.

    *positions* is the previous frame's (or current scene) configuration,
    used as the starting point for iteration -- warm-starting from the
    last solved frame keeps consecutive frames coherent and avoids
    popping between frames that would come from always starting cold.
    """
    n = len(positions)
    pts = [list(p) for p in positions]
    pts[0] = list(base_pos)

    total_length = sum(lengths)
    dist_to_target = _v_length(_v_sub(target_pos, base_pos))

    if dist_to_target >= total_length:
        # Unreachable -- fully extend in a straight line toward the target.
        direction = _v_normalize(_v_sub(target_pos, base_pos))
        cur = list(base_pos)
        pts[0] = cur
        for i in range(1, n):
            cur = _v_add(cur, _v_scale(direction, lengths[i - 1]))
            pts[i] = cur
        return pts

    for _ in range(iterations):
        if _v_length(_v_sub(pts[-1], target_pos)) < tolerance:
            break

        # Backward: tip -> base.
        pts[-1] = list(target_pos)
        for i in range(n - 2, -1, -1):
            direction = _v_normalize(_v_sub(pts[i], pts[i + 1]))
            pts[i] = _v_add(pts[i + 1], _v_scale(direction, lengths[i]))

        # Forward: base -> tip, re-pinning the base.
        pts[0] = list(base_pos)
        for i in range(1, n):
            direction = _v_normalize(_v_sub(pts[i], pts[i - 1]))
            pts[i] = _v_add(pts[i - 1], _v_scale(direction, lengths[i - 1]))

    return pts


# ---------------------------------------------------------------------------
# Twist / orientation propagation
#
# FABRIK only solves position -- twist/roll around each bone's own axis
# is a free choice it doesn't make for you. Modeled on
# tlmParticleChain._joint_chain_row_matrices's parallel-transport frame
# (rotate the previous segment's up vector by the quaternion between
# consecutive aim vectors) rather than _buildAimChain's DG-node version,
# since FABRIK is necessarily a per-frame Python position solve, not a
# live rig -- the orientation chain should be plain Python too.
#
# One deliberate deviation from _joint_chain_row_matrices: that function
# seeds segment 0 from a constant, appropriate for a sim rig with no
# authored twist to preserve. Here segment 0 seeds from the BASE
# control's own live rotation that frame, since there is real authored
# animation at the base worth keeping.
# ---------------------------------------------------------------------------

def _transport_up(prev_aim, aim, prev_up):
    """Rotate *prev_up* by the minimal-rotation quaternion that takes
    *prev_aim* to *aim* -- true parallel transport, no accumulated twist."""
    q = om.MQuaternion(om.MVector(*prev_aim), om.MVector(*aim))
    rotated = om.MVector(*prev_up).rotateBy(q)
    return (rotated.x, rotated.y, rotated.z)


def build_chain_frames(solved_positions, base_matrix, up_axis=(0.0, 1.0, 0.0)):
    """Derive an orthonormal (aim, up, right, pos) frame per control in
    *solved_positions*.

    *base_matrix* is the base control's current world matrix (an
    om.MMatrix) -- its own local up-axis direction seeds segment 0's up
    vector, re-orthogonalized against the first aim direction. Every
    later segment's up is the previous segment's up transported along the
    chain (see _transport_up). The tip repeats the last real segment's
    orientation, since there's no further aim direction to derive one
    from.
    """
    n = len(solved_positions)
    if n < 2:
        raise RuntimeError('A chain needs at least a base and a tip control.')

    aims = [_v_normalize(_v_sub(solved_positions[i + 1], solved_positions[i]))
            for i in range(n - 1)]

    # Seed segment 0's up from the base's own local up axis, re-
    # orthogonalized against the first aim direction -- but that axis can
    # be parallel to the first aim (cross product degenerates to zero),
    # e.g. a chain running straight up the base's own local Y with the
    # default up_axis. Fall back through the base's other local axes
    # until one gives a non-degenerate cross product.
    for axis in (up_axis, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)):
        axis_vec = om.MVector(*axis) * base_matrix
        axis_world = (axis_vec.x, axis_vec.y, axis_vec.z)
        right0 = _v_cross(axis_world, aims[0])
        if _v_length(right0) > 1e-6:
            right0 = _v_normalize(right0)
            break
    else:
        raise RuntimeError(
            'Could not derive a stable up vector for the base control -- '
            'degenerate basis (all candidate axes parallel to the first '
            'bone direction).')
    up0 = _v_normalize(_v_cross(aims[0], right0))

    frames = []
    prev_aim, prev_up = aims[0], up0
    for i, aim in enumerate(aims):
        up = up0 if i == 0 else _transport_up(prev_aim, aim, prev_up)
        right = _v_normalize(_v_cross(up, aim))
        up = _v_normalize(_v_cross(aim, right))
        frames.append((aim, up, right, solved_positions[i]))
        prev_aim, prev_up = aim, up

    last_aim, last_up, last_right, _ = frames[-1]
    frames.append((last_aim, last_up, last_right, solved_positions[-1]))
    return frames


# ---------------------------------------------------------------------------
# Per-control aim-rig orchestration
#
# Reuses the Bake & Flip *pattern* from animDev/multiTool/mtAimRig.py --
# build a temp aim rig, bake it with its constraint active, flip so the
# real control is driven by the result, bake rotate-only keys, clean up --
# but not its live selection/cluster-building UI path, and not its
# parent-constrain-to-the-original-object trick (that trick makes
# up_loc track the SAME object's own live rotation, appropriate for
# mtAimRig's job of cleaning up one object's own Euler channels in
# isolation; here position/up are already fully solved per frame by
# FABRIK + build_chain_frames, so the rig's job is only to let Maya's own
# aimConstraint -- not our own matrix decomposition -- turn those into a
# clean, continuous rotation).
# ---------------------------------------------------------------------------

def build_segment_aim_rig(name_prefix):
    """Build one segment's minimal aim rig: aim_grp aimed at target_loc,
    world-up taken from up_loc -- both driven per frame by
    drive_rig_chain_per_frame, then baked in one pass by
    bake_and_flip_segment."""
    aim_grp = cmds.group(em=True, name=name_prefix + '_aim_grp')
    up_loc = cmds.spaceLocator(name=name_prefix + '_up_loc')[0]
    target_loc = cmds.spaceLocator(name=name_prefix + '_target_loc')[0]
    cmds.setAttr(up_loc + '.visibility', 0)
    cmds.setAttr(target_loc + '.visibility', 0)

    aim_con = cmds.aimConstraint(
        target_loc, aim_grp,
        aimVector=(0, 0, 1), upVector=(0, 1, 0),
        worldUpType='object', worldUpObject=up_loc,
        maintainOffset=False,
    )[0]

    return {
        'aim_grp': aim_grp,
        'up_loc': up_loc,
        'target_loc': target_loc,
        'aim_constraint': aim_con,
    }


def drive_rig_chain_per_frame(rig_list, positions_by_frame, frames_by_frame, frame_range):
    """Key aim_grp/up_loc/target_loc translate for every rig across
    *frame_range* from the already-solved FABRIK positions + twist
    frames, so bake_and_flip_segment can bake the live aimConstraint's
    rotation output in one pass -- mirrors mtAimRig.bake_and_flip baking
    with constraints active rather than hand-computing rotations."""
    for f_idx, frame in enumerate(frame_range):
        cmds.currentTime(frame)
        positions = positions_by_frame[f_idx]
        frames = frames_by_frame[f_idx]
        for i, rig in enumerate(rig_list):
            pos = positions[i]
            aim, up, _right, _pos = frames[i]

            cmds.xform(rig['aim_grp'], ws=True, t=pos)
            cmds.xform(rig['up_loc'], ws=True, t=_v_add(pos, up))
            cmds.xform(rig['target_loc'], ws=True, t=_v_add(pos, aim))

            cmds.setKeyframe(rig['aim_grp'], at='translate')
            cmds.setKeyframe(rig['up_loc'], at='translate')
            cmds.setKeyframe(rig['target_loc'], at='translate')


def bake_and_flip_segment(rig, control, frame_range):
    """Bake the aim rig's live-constrained rotation, delete the
    constraint, then flip so *control* is driven by the baked result --
    rotation only, translate is left completely alone. Same two-step
    shape as mtAimRig.bake_and_flip, applied to one segment."""
    t_min, t_max = frame_range[0], frame_range[-1]
    cmds.bakeResults(
        rig['aim_grp'],
        t=(t_min, t_max), simulation=True, sampleBy=1,
        disableImplicitControl=False, preserveOutsideKeys=True,
    )
    cmds.delete(rig['aim_constraint'])
    con = cmds.parentConstraint(
        rig['aim_grp'], control, maintainOffset=True,
        skipTranslate=['x', 'y', 'z'],
    )[0]
    return con


def bake_rotate_only(flip_constraints, controls, frame_range, to_layer=True):
    """Bake final rotate-only keys onto *controls* from their flip
    constraints, then remove the constraints -- adapts mtAimRig.bake_aim,
    restricted to rotate channels (translate is never touched anywhere in
    this module, so every control's original position survives)."""
    t_min, t_max = frame_range[0], frame_range[-1]
    rot_attrs = ['rx', 'ry', 'rz']

    layer_name = None
    if to_layer:
        layer_name = 'fkChainSmooth'
        idx = 1
        while cmds.animLayer(layer_name, q=True, exists=True):
            layer_name = 'fkChainSmooth_{}'.format(idx)
            idx += 1
        layer_name = cmds.animLayer(layer_name, override=True)
        for ctrl in controls:
            for attr in rot_attrs:
                cmds.animLayer(
                    layer_name, e=True,
                    attribute='{}.{}'.format(ctrl, attr))

    bake_kwargs = dict(
        t=(t_min, t_max), simulation=True, sampleBy=1,
        preserveOutsideKeys=True, attribute=rot_attrs,
    )
    if layer_name:
        bake_kwargs['destinationLayer'] = layer_name
    cmds.bakeResults(controls, **bake_kwargs)

    for con in flip_constraints:
        if cmds.objExists(con):
            cmds.delete(con)

    return layer_name


def delete_segment_rig(rig):
    for key in ('aim_grp', 'up_loc', 'target_loc'):
        node = rig.get(key)
        if node and cmds.objExists(node):
            cmds.delete(node)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

class FKChainSolver(object):
    """Ties the pieces above into the tab's backing object, mirroring
    SmoothToolCore's role for the single-control tab: set inputs, preview
    live, bake, reset."""

    def __init__(self):
        self.chain = []            # ordered base..tip transform names
        self.tip_core = None       # a SmoothToolCore instance (owned by the UI tab)
        self.frames = []
        self.rest_lengths = []
        self._rigs = []
        self._flip_constraints = []
        self._preview_curves = []
        self._live = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def set_chain(self, ordered_controls):
        if len(ordered_controls) < 2:
            raise RuntimeError('A chain needs at least a base and a tip control.')
        self.chain = list(ordered_controls)

    def set_tip_core(self, core):
        self.tip_core = core

    def sample_rest_pose(self, frame=None):
        if frame is None:
            frame = SmoothToolCore.get_frame_range()[0]
        self.rest_lengths = sample_rest_lengths(self.chain, frame=frame)
        return self.rest_lengths

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------

    @staticmethod
    def _tip_world_matrix(core, frame_idx):
        """Reconstruct the tip control's smoothed WORLD matrix for one
        sampled frame, using the exact delta-reconstruction
        SmoothToolCore.bake() uses internally -- reused rather than
        duplicated, since that math is already correct and tested."""
        orig_m = core._compose_mmatrix(core._orig_translate[frame_idx], core._orig_euler[frame_idx])
        blend_m = core._compose_mmatrix(core._blended_translate[frame_idx], core._blended_euler[frame_idx])
        delta = orig_m.inverse() * blend_m
        if core.parent_space_obj and core.parent_matrices:
            parent_m = om.MMatrix(core.parent_matrices[frame_idx])
            delta = parent_m.inverse() * delta * parent_m
        orig_ctrl = om.MMatrix(core.ctrl_matrices[frame_idx])
        return orig_ctrl * delta

    def _solve_all_frames(self):
        """Re-run FABRIK + twist for every sampled frame from the tip
        core's current blended tip position -- called by both preview()
        and bake() so they always agree."""
        core = self.tip_core
        self.frames = list(core.frames)
        base = self.chain[0]

        positions_by_frame = []
        frames_by_frame = []
        prev_positions = [cmds.xform(c, q=True, ws=True, t=True) for c in self.chain]

        for f_idx, frame in enumerate(self.frames):
            cmds.currentTime(frame)
            base_pos = cmds.xform(base, q=True, ws=True, t=True)
            base_matrix = om.MMatrix(cmds.xform(base, q=True, ws=True, matrix=True))
            tip_matrix = self._tip_world_matrix(core, f_idx)
            tip_pos = (tip_matrix.getElement(3, 0),
                       tip_matrix.getElement(3, 1),
                       tip_matrix.getElement(3, 2))

            solved = solve_fabrik(prev_positions, self.rest_lengths, base_pos, tip_pos)
            prev_positions = solved
            positions_by_frame.append(solved)
            frames_by_frame.append(build_chain_frames(solved, base_matrix))

        return positions_by_frame, frames_by_frame

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(self, strength, blend, falloff):
        core = self.tip_core
        core.falloff = falloff
        core.update_smooth(strength)
        core.update_blend(blend)

        positions_by_frame, _frames_by_frame = self._solve_all_frames()
        self._draw_preview_curves(positions_by_frame)
        self._live = True

    def _draw_preview_curves(self, positions_by_frame):
        self._delete_preview_curves()
        n = len(self.chain)
        for i in range(n):
            pts = [positions_by_frame[f][i] for f in range(len(positions_by_frame))]
            if len(pts) < 2:
                continue
            crv = cmds.curve(
                p=pts, d=3 if len(pts) > 3 else 1,
                name='{}_fkChainPreview'.format(self.chain[i]))
            cmds.setAttr(crv + '.overrideEnabled', 1)
            cmds.setAttr(crv + '.overrideRGBColors', 1)
            cmds.setAttr(crv + '.overrideColorRGB', 0.2, 0.8, 1.0)
            self._preview_curves.append(crv)

    def _delete_preview_curves(self):
        for crv in self._preview_curves:
            if cmds.objExists(crv):
                cmds.delete(crv)
        self._preview_curves = []

    # ------------------------------------------------------------------
    # Bake
    # ------------------------------------------------------------------

    def bake(self, to_layer=True):
        if not self.chain or self.tip_core is None:
            raise RuntimeError('Set a chain and create tip curves before baking.')

        positions_by_frame, frames_by_frame = self._solve_all_frames()
        frame_range = self.frames

        cmds.undoInfo(openChunk=True, chunkName='FKChainSmooth_Bake')
        rigs = [build_segment_aim_rig('{}_fkChain_{:02d}'.format(self.chain[0], i))
                for i in range(len(self.chain))]
        self._rigs = rigs
        layer_name = None
        try:
            drive_rig_chain_per_frame(rigs, positions_by_frame, frames_by_frame, frame_range)

            flip_constraints = []
            for rig, control in zip(rigs, self.chain):
                con = bake_and_flip_segment(rig, control, frame_range)
                flip_constraints.append(con)
            self._flip_constraints = flip_constraints

            layer_name = bake_rotate_only(flip_constraints, self.chain, frame_range, to_layer=to_layer)
        finally:
            for rig in rigs:
                delete_segment_rig(rig)
            self._rigs = []
            self._flip_constraints = []
            cmds.undoInfo(closeChunk=True)

        self.tip_core.delete_curves()
        self._delete_preview_curves()
        self._live = False
        return layer_name

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        self._delete_preview_curves()
        for rig in self._rigs:
            delete_segment_rig(rig)
        self._rigs = []
        for con in self._flip_constraints:
            if cmds.objExists(con):
                cmds.delete(con)
        self._flip_constraints = []
        self._live = False

    def reset(self):
        self.cleanup()
        self.chain = []
        self.tip_core = None
        self.frames = []
        self.rest_lengths = []

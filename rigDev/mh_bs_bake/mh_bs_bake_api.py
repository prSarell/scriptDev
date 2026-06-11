"""
Metahuman Blendshape Baking Pipeline — API
Converts a live Metahuman DNA rig into a portable blendshape-only rig.

Phase 1: bake_single_shapes()
    Poses each face control channel to its extreme, duplicates the face mesh,
    builds a blendShape deformer on a clean duplicate, and wires weights back
    to the controls via set-driven keys.

Phase 2: find_and_apply_correctives()
    Enumerates pairs of active channels, compares vertex positions between the
    original (RigLogic) mesh and the blendshape rig, and for any pair whose
    residual exceeds the threshold bakes a corrective shape and wires it via
    a combinationShape node.

    Corrective math:
        corr_target[i] = neutral[i] + (gt[i] - bs_current[i])
    So that: neutral + (tA-neutral) + (tB-neutral) + (corr-neutral) = gt  ✓
"""

import logging
import os
import sys
from itertools import combinations

import maya.cmds as cmds
from maya.api import OpenMaya as om

# Re-use helpers from the facial transfer port.
# Try direct import first (deployed flat to ~/maya/scripts/), then fall back
# to dev layout (rigDev/mh_bs_bake/ → metahuman_facial_transfer/).
try:
    from metahuman_api_25 import get_face_controls, zero_out_face_controls, strip_namespace
except ImportError:
    _TRANSFER_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'metahuman_facial_transfer')
    )
    if _TRANSFER_DIR not in sys.path:
        sys.path.insert(0, _TRANSFER_DIR)
    from metahuman_api_25 import get_face_controls, zero_out_face_controls, strip_namespace

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD_MM = 0.1  # vertex deviation threshold, millimetres


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_keyable_channels(control):
    """Return [(channel, min_val, max_val)] for settable, keyable tx/ty."""
    channels = []
    for channel, limit_flag in (('tx', 'translationX'), ('ty', 'translationY')):
        attr = '{}.{}'.format(control, channel)
        if cmds.getAttr(attr, settable=True) and cmds.getAttr(attr, keyable=True):
            limits = cmds.transformLimits(control, query=True, **{limit_flag: True})
            if limits:
                channels.append((channel, limits[0], limits[1]))
    return channels


def _force_eval(*meshes):
    for mesh in meshes:
        cmds.dgeval('{}.worldMesh[0]'.format(mesh))


def _get_mesh_points(mesh):
    """Return MPointArray of world-space vertex positions."""
    sel = om.MSelectionList()
    sel.add(mesh)
    fn = om.MFnMesh(sel.getDagPath(0))
    return fn.getPoints(om.MSpace.kWorld)


def _set_mesh_points(mesh, points):
    """Set world-space vertex positions on mesh from MPointArray."""
    sel = om.MSelectionList()
    sel.add(mesh)
    fn = om.MFnMesh(sel.getDagPath(0))
    fn.setPoints(points, om.MSpace.kWorld)
    fn.updateSurface()


def _max_delta_mm(pts_a, pts_b):
    """Return max vertex deviation in mm (Maya default units are cm)."""
    max_d = 0.0
    for pa, pb in zip(pts_a, pts_b):
        d = (pa - pb).length()
        if d > max_d:
            max_d = d
    return max_d * 10.0


def find_face_mesh(namespace=':'):
    """Auto-detect the Metahuman head mesh. Returns transform name or None."""
    candidates = ['head_lod0_mesh', 'Face_mesh', 'face_mesh', 'Head_mesh']
    prefix = '' if namespace in (':', '') else namespace
    for name in candidates:
        full = '{}{}'.format(prefix, name)
        if cmds.objExists(full):
            return full
    rl_nodes = cmds.ls(type='rigLogic') or []
    for rl in rl_nodes:
        future = cmds.listHistory(rl, future=True, pruneDagObjects=False) or []
        meshes = cmds.ls(future, type='mesh') or []
        if meshes:
            parents = cmds.listRelatives(meshes[0], parent=True) or []
            if parents:
                return parents[0]
    return None


def find_teeth_mesh(namespace=':'):
    """Auto-detect the Metahuman teeth mesh. Returns transform name or None."""
    prefix = '' if namespace in (':', '') else namespace
    for name in ('teeth_lod0_mesh', 'teeth_upper_lod0_mesh', 'Teeth_mesh', 'teeth_mesh'):
        full = '{}{}'.format(prefix, name)
        if cmds.objExists(full):
            return full
    return None



def _derive_bs_names(face_mesh):
    """
    Derive blendShape node, base mesh, and targets group names from the
    source mesh name. Preserves legacy names for the head mesh.
    """
    short = strip_namespace(face_mesh).lower()
    if 'head' in short:
        return 'mh_bs_base', 'mhBsRig', 'mhBsTargets_GRP'
    for tag in ('teeth', 'tongue', 'saliva'):
        if tag in short:
            cap = tag.capitalize()
            return 'mh_bs_{}_base'.format(tag), 'mhBs{}Rig'.format(cap), 'mhBs{}Targets_GRP'.format(cap)
    # Generic fallback — derive from mesh name
    tag = short.split('_lod')[0].rstrip('_')
    cap = tag.replace('_', ' ').title().replace(' ', '')
    return 'mh_bs_{}_base'.format(tag), 'mhBs{}Rig'.format(cap), 'mhBs{}Targets_GRP'.format(cap)


# ---------------------------------------------------------------------------
# Phase 1 — single shapes
# ---------------------------------------------------------------------------

def collect_channel_extremes(face_controls):
    """
    Returns [(ctrl, channel, direction, value)] for all keyable channel
    extremes. direction is 'pos' (max > 0) or 'neg' (min < 0).
    """
    extremes = []
    for ctrl in face_controls:
        for channel, min_val, max_val in _get_keyable_channels(ctrl):
            if max_val > 0:
                extremes.append((ctrl, channel, 'pos', max_val))
            if min_val < 0:
                extremes.append((ctrl, channel, 'neg', min_val))
    return extremes


def bake_single_shapes(face_mesh, namespace=':', progress_cb=None):
    """
    Bake all single-control extreme poses into blendshape targets.

    Args:
        face_mesh (str): Metahuman face mesh transform name.
        namespace (str): rig namespace (trailing colon included, or ':').
        progress_cb (callable): optional fn(current, total, label).

    Returns:
        dict with keys:
            bs_node   (str)  — blendShape deformer
            bs_base   (str)  — duplicate mesh with blendshape applied
            extremes  (list) — [(ctrl, channel, direction, value), ...]
    """
    face_controls = get_face_controls(namespace)
    if not face_controls:
        raise RuntimeError('No face controls found in namespace: {}'.format(namespace))

    cmds.undoInfo(stateWithoutFlush=False)
    try:
        return _bake_single_shapes_inner(face_mesh, namespace, face_controls, progress_cb)
    finally:
        cmds.undoInfo(stateWithoutFlush=True)


def _bake_single_shapes_inner(face_mesh, namespace, face_controls, progress_cb):
    bs_base_name, bs_node_name, targets_grp_name = _derive_bs_names(face_mesh)

    zero_out_face_controls(namespace)
    _force_eval(face_mesh)

    bs_base = cmds.duplicate(face_mesh, name=bs_base_name)[0]
    cmds.delete(bs_base, constructionHistory=True)

    extremes = collect_channel_extremes(face_controls)
    total = len(extremes)
    target_meshes = []

    for i, (ctrl, channel, direction, val) in enumerate(extremes):
        if progress_cb:
            label = 'Baking {}.{} ({})'.format(strip_namespace(ctrl), channel, direction)
            progress_cb(i, total, label)

        ctrl_attr = '{}.{}'.format(ctrl, channel)
        cmds.setAttr(ctrl_attr, val)
        _force_eval(face_mesh)

        safe = strip_namespace(ctrl).replace('CTRL_', '').replace(':', '_')
        target_name = 'mhBs_{}_{}_{}'.format(safe, channel, direction)
        target = cmds.duplicate(face_mesh, name=target_name)[0]
        cmds.delete(target, constructionHistory=True)
        target_meshes.append(target)

        cmds.setAttr(ctrl_attr, 0.0)

    zero_out_face_controls(namespace)
    _force_eval(face_mesh)

    if progress_cb:
        progress_cb(total, total, 'Building blendShape node...')

    bs_node = cmds.blendShape(
        target_meshes + [bs_base], name=bs_node_name, frontOfChain=True
    )[0]

    # Group targets at world root, visible and ready for sculpting
    targets_grp = cmds.group(target_meshes, name=targets_grp_name)
    cmds.parent(targets_grp, world=True)

    # Wire each weight to its control channel via set-driven key
    for i, (ctrl, channel, direction, val) in enumerate(extremes):
        ctrl_attr = '{}.{}'.format(ctrl, channel)
        weight_attr = '{}.weight[{}]'.format(bs_node, i)

        cmds.setAttr(ctrl_attr, 0.0)
        cmds.setAttr(weight_attr, 0.0)
        cmds.setDrivenKeyframe(weight_attr, currentDriver=ctrl_attr)

        cmds.setAttr(ctrl_attr, val)
        cmds.setAttr(weight_attr, 1.0)
        cmds.setDrivenKeyframe(weight_attr, currentDriver=ctrl_attr)

        cmds.setAttr(ctrl_attr, 0.0)
        cmds.setAttr(weight_attr, 0.0)

    zero_out_face_controls(namespace)

    logger.info('Phase 1 complete: {} blendshape targets baked.'.format(total))
    if progress_cb:
        progress_cb(total, total, 'Done — {} shapes baked.'.format(total))

    return {'bs_node': bs_node, 'bs_base': bs_base, 'extremes': extremes}


# ---------------------------------------------------------------------------
# Phase 2 — corrective shapes
# ---------------------------------------------------------------------------

def find_and_apply_correctives(
    original_mesh, phase1_result, namespace=':',
    threshold_mm=DEFAULT_THRESHOLD_MM,
    combo_size=2, progress_cb=None
):
    """
    Find combination poses where the blendshape rig deviates from the original
    rig by more than threshold_mm, bake corrective targets, and wire them via
    combinationShape nodes.

    Args:
        original_mesh (str): original Metahuman face mesh (ground truth).
        phase1_result (dict): return value from bake_single_shapes().
        namespace (str): rig namespace.
        threshold_mm (float): vertex deviation threshold in mm.
        combo_size (int): combination depth to test (2 = pairs only).
        progress_cb (callable): optional fn(current, total, label).

    Returns:
        int: number of corrective shapes added.
    """
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        return _find_and_apply_correctives_inner(
            original_mesh, phase1_result, namespace, threshold_mm, combo_size, progress_cb
        )
    finally:
        cmds.undoInfo(stateWithoutFlush=True)


def _find_and_apply_correctives_inner(
    original_mesh, phase1_result, namespace, threshold_mm, combo_size, progress_cb
):
    bs_node = phase1_result['bs_node']
    bs_base = phase1_result['bs_base']
    extremes = phase1_result['extremes']

    # Only test positive-direction channels — these have the most interactions
    pos_extremes = [
        (ctrl, ch, val, idx)
        for idx, (ctrl, ch, direction, val) in enumerate(extremes)
        if direction == 'pos'
    ]

    # Read neutral bs_base positions once (all weights at 0)
    zero_out_face_controls(namespace)
    _force_eval(bs_base)
    neutral_pts = _get_mesh_points(bs_base)

    combos = list(combinations(range(len(pos_extremes)), combo_size))
    total = len(combos)
    corrective_count = 0

    for combo_idx, idx_pair in enumerate(combos):
        ctrl_a, ch_a, val_a, weight_idx_a = pos_extremes[idx_pair[0]]
        ctrl_b, ch_b, val_b, weight_idx_b = pos_extremes[idx_pair[1]]

        if ctrl_a == ctrl_b and ch_a == ch_b:
            continue

        label = '{}.{} + {}.{}'.format(
            strip_namespace(ctrl_a), ch_a, strip_namespace(ctrl_b), ch_b
        )
        if progress_cb:
            progress_cb(combo_idx, total, 'Testing {}'.format(label))

        cmds.setAttr('{}.{}'.format(ctrl_a, ch_a), val_a)
        cmds.setAttr('{}.{}'.format(ctrl_b, ch_b), val_b)
        _force_eval(original_mesh, bs_base)

        gt_pts = _get_mesh_points(original_mesh)
        bs_pts = _get_mesh_points(bs_base)
        delta_mm = _max_delta_mm(gt_pts, bs_pts)

        if delta_mm > threshold_mm:
            # Compute residual corrective: neutral + (gt - bs_current)
            corr_pts = om.MPointArray()
            for k in range(len(gt_pts)):
                residual = gt_pts[k] - bs_pts[k]  # MVector
                corr_pts.append(neutral_pts[k] + residual)

            # Create corrective mesh
            safe_a = strip_namespace(ctrl_a).replace('CTRL_', '')
            safe_b = strip_namespace(ctrl_b).replace('CTRL_', '')
            corr_name = 'mhBsCorr_{}_{}_{}_{}'.format(safe_a, ch_a, safe_b, ch_b)
            corr_mesh = cmds.duplicate(bs_base, name=corr_name)[0]
            cmds.delete(corr_mesh, constructionHistory=True)
            _set_mesh_points(corr_mesh, corr_pts)

            # Add to blendshape then clean up the staging mesh
            new_index = cmds.blendShape(bs_node, query=True, weightCount=True)
            cmds.blendShape(bs_node, edit=True,
                            target=[bs_base, new_index, corr_mesh, 1.0])
            cmds.delete(corr_mesh)

            # Wire via combinationShape — inputs are the single-shape weights
            combo_node = cmds.createNode(
                'combinationShape', name='mhCombo_{}'.format(new_index)
            )
            cmds.connectAttr(
                '{}.weight[{}]'.format(bs_node, weight_idx_a),
                '{}.inputWeight[0]'.format(combo_node)
            )
            cmds.connectAttr(
                '{}.weight[{}]'.format(bs_node, weight_idx_b),
                '{}.inputWeight[1]'.format(combo_node)
            )
            cmds.connectAttr(
                '{}.outputWeight'.format(combo_node),
                '{}.weight[{}]'.format(bs_node, new_index)
            )

            corrective_count += 1
            logger.info('Corrective: {} (delta {:.3f}mm)'.format(corr_name, delta_mm))

        # Reset to neutral for next test
        cmds.setAttr('{}.{}'.format(ctrl_a, ch_a), 0.0)
        cmds.setAttr('{}.{}'.format(ctrl_b, ch_b), 0.0)

    zero_out_face_controls(namespace)

    logger.info('Phase 2 complete: {} correctives added.'.format(corrective_count))
    if progress_cb:
        progress_cb(total, total, 'Done — {} correctives added.'.format(corrective_count))

    return corrective_count

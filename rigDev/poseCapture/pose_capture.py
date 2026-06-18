"""
pose_capture.py — Capture and apply rig poses across Maya scenes.

Discovers animated controls via animCurve connections (naming-convention
agnostic), strips namespaces for portability between shot files and rig
files, and persists to a JSON temp file so data survives file switches.

Shared by DSFR and Corrective BlendShape tools.
"""

import json
import os
import tempfile

import maya.cmds as cmds


_DEFAULT_PATH = os.path.join(tempfile.gettempdir(), 'dsfr_captured_pose.json')

_TRANSFORM_ATTRS = {
    'translateX', 'translateY', 'translateZ',
    'rotateX', 'rotateY', 'rotateZ',
    'scaleX', 'scaleY', 'scaleZ',
}


def _strip_namespace(node):
    return node.rsplit(':', 1)[-1]


def _is_transform(node):
    try:
        return cmds.objectType(node, isAType='transform')
    except Exception:
        return False


def capture_pose():
    """
    Scan every animCurve in the scene, follow output connections to
    discover driven transform attributes, and record current values.

    Returns dict with keys: frame, scene, attributes.
    Attribute keys are namespace-stripped for portability.
    """
    curves = cmds.ls(type='animCurve') or []
    attributes = {}

    for curve in curves:
        connections = cmds.listConnections(
            curve + '.output', destination=True, plugs=True,
            skipConversionNodes=True,
        ) or []

        for dest_plug in connections:
            node, attr = dest_plug.split('.', 1)

            if not _is_transform(node):
                continue

            if attr not in _TRANSFORM_ATTRS:
                continue

            try:
                val = cmds.getAttr(dest_plug)
            except Exception:
                continue

            stripped_key = _strip_namespace(node) + '.' + attr
            attributes[stripped_key] = val

    return {
        'frame': int(cmds.currentTime(query=True)),
        'scene': cmds.file(query=True, sceneName=True) or '',
        'attributes': attributes,
    }


def apply_pose(pose_data, namespace=''):
    """
    Set attribute values from captured pose data onto controls.
    Prepends namespace if given.  Silently skips missing attributes.

    Returns (applied_count, skipped_count).
    """
    attrs = pose_data.get('attributes', {})
    applied = 0
    skipped = 0

    for stripped_key, value in attrs.items():
        node_attr = stripped_key
        if namespace:
            node, attr = stripped_key.split('.', 1)
            node_attr = '{}:{}.{}'.format(namespace, node, attr)

        if not cmds.objExists(node_attr):
            skipped += 1
            continue

        try:
            cmds.setAttr(node_attr, value)
            applied += 1
        except Exception:
            skipped += 1

    return applied, skipped


def default_pose(pose_data, namespace=''):
    """
    Reset all captured attributes to their default values.

    Returns (reset_count, skipped_count).
    """
    attrs = pose_data.get('attributes', {})
    reset = 0
    skipped = 0

    for stripped_key in attrs:
        node_attr = stripped_key
        if namespace:
            node, attr = stripped_key.split('.', 1)
            node_attr = '{}:{}.{}'.format(namespace, node, attr)

        if not cmds.objExists(node_attr):
            skipped += 1
            continue

        node, attr = node_attr.rsplit('.', 1)
        try:
            defaults = cmds.attributeQuery(attr, node=node, listDefault=True)
            default_val = defaults[0] if defaults else 0.0
        except Exception:
            default_val = 0.0

        try:
            cmds.setAttr(node_attr, default_val)
            reset += 1
        except Exception:
            skipped += 1

    return reset, skipped


def save_pose(pose_data, filepath=None):
    """Write pose data to JSON. Returns the filepath written."""
    filepath = filepath or _DEFAULT_PATH
    with open(filepath, 'w') as f:
        json.dump(pose_data, f, indent=2)
    return filepath


def load_pose(filepath=None):
    """Read pose data from JSON. Returns dict or None if file missing."""
    filepath = filepath or _DEFAULT_PATH
    if not os.path.isfile(filepath):
        return None
    with open(filepath, 'r') as f:
        return json.load(f)

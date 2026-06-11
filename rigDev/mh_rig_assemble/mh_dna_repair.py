"""
mh_dna_repair.py — repairs a broken Metahuman DNA file connection.
Finds the dnaFileNode in the scene, shows the current (broken) path,
and lets the user browse to the correct .dna file to restore the rig.
"""

import os

import maya.cmds as cmds
from maya import OpenMayaUI as omui
from PySide6 import QtWidgets
import shiboken6


def _maya_main_window():
    return shiboken6.wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


def _find_dna_node():
    nodes = cmds.ls(type='dnaFileNode') or []
    return nodes[0] if nodes else None


def _get_dna_attr(node):
    """Return (attr_name, current_value) for the DNA file path attribute."""
    for attr in ('dnaFilePath', 'inputDna', 'dna', 'filePath'):
        try:
            val = cmds.getAttr('{}.{}'.format(node, attr))
            if val is not None:
                return attr, str(val)
        except Exception:
            pass
    # Fallback: search all string attrs for something that looks like a path
    for attr in (cmds.listAttr(node, string=True) or []):
        try:
            val = str(cmds.getAttr('{}.{}'.format(node, attr)) or '')
            if '.dna' in val.lower() or (os.sep in val and val.strip()):
                return attr, val
        except Exception:
            pass
    return None, ''


def show():
    node = _find_dna_node()
    if not node:
        cmds.confirmDialog(
            title='MH DNA Repair',
            message='No dnaFileNode found in scene.\nIs a Metahuman rig loaded?',
            button=['OK'],
        )
        return

    attr, current_path = _get_dna_attr(node)
    if not attr:
        cmds.confirmDialog(
            title='MH DNA Repair',
            message='Found {} but could not locate the DNA path attribute.'.format(node),
            button=['OK'],
        )
        return

    is_broken = not (current_path and os.path.exists(current_path))
    status = 'MISSING' if is_broken else 'OK'

    msg = (
        'DNA node:  {}\n'
        'Attribute: {}\n'
        'Status:    {}\n\n'
        'Current path:\n{}\n\n'
        'Browse to the correct .dna file to repair.'
    ).format(node, attr, status, current_path or '(empty)')

    result = cmds.confirmDialog(
        title='MH DNA Repair',
        message=msg,
        button=['Browse...', 'Cancel'],
        defaultButton='Browse...',
        cancelButton='Cancel',
    )

    if result != 'Browse...':
        return

    start_dir = os.path.dirname(current_path) if current_path else ''
    new_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        _maya_main_window(),
        'Locate DNA File',
        start_dir,
        'DNA Files (*.dna);;All Files (*)',
    )

    if not new_path:
        return

    try:
        cmds.setAttr('{}.{}'.format(node, attr), new_path, type='string')
        cmds.inViewMessage(
            amg='<b>DNA path repaired.</b>',
            pos='midCenter', fade=True,
        )
        print('[mh_dna_repair] {} = {}'.format(node, new_path))
    except Exception as e:
        cmds.confirmDialog(
            title='MH DNA Repair',
            message='Failed to set path:\n{}'.format(e),
            button=['OK'],
        )

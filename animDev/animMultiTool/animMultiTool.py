import maya.cmds as cmds
import maya.mel as mel

WORKSPACE_CONTROL_NAME = "animMultiToolWorkspaceControl"
TOOL_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class AnimMultiTool(object):
    # Constructed lazily inside _populate_workspace_control
    pass


class AnimMultiToolWidget(object):
    pass


def _build_widget(parent):
    from PySide2 import QtWidgets, QtCore

    widget = QtWidgets.QWidget(parent)
    widget.setObjectName("animMultiToolWidget")

    main_layout = QtWidgets.QVBoxLayout(widget)
    main_layout.setContentsMargins(4, 4, 4, 4)
    main_layout.setSpacing(6)
    main_layout.setAlignment(QtCore.Qt.AlignTop)

    main_layout.addWidget(_build_snap_section(widget))
    main_layout.addStretch()

    return widget


def _build_snap_section(parent):
    from PySide2 import QtWidgets

    group = QtWidgets.QGroupBox("Snap")
    layout = QtWidgets.QVBoxLayout(group)
    layout.setSpacing(4)

    # Checkboxes
    cb_layout = QtWidgets.QHBoxLayout()
    cb_translate = QtWidgets.QCheckBox("Translate")
    cb_translate.setChecked(True)
    cb_rotate = QtWidgets.QCheckBox("Rotate")
    cb_rotate.setChecked(True)
    cb_scale = QtWidgets.QCheckBox("Scale")
    cb_scale.setChecked(False)
    cb_layout.addWidget(cb_translate)
    cb_layout.addWidget(cb_rotate)
    cb_layout.addWidget(cb_scale)
    cb_layout.addStretch()
    layout.addLayout(cb_layout)

    # Buttons
    btn_layout = QtWidgets.QHBoxLayout()
    btn_a_to_b = QtWidgets.QPushButton("Snap A  →  B")
    btn_b_to_a = QtWidgets.QPushButton("Snap B  →  A")
    btn_a_to_b.setToolTip("Snap first selected object to second selected object")
    btn_b_to_a.setToolTip("Snap second selected object to first selected object")
    btn_a_to_b.clicked.connect(
        lambda: _do_snap(cb_translate, cb_rotate, cb_scale, source_is_first=True)
    )
    btn_b_to_a.clicked.connect(
        lambda: _do_snap(cb_translate, cb_rotate, cb_scale, source_is_first=False)
    )
    btn_layout.addWidget(btn_a_to_b)
    btn_layout.addWidget(btn_b_to_a)
    layout.addLayout(btn_layout)

    return group


def _do_snap(cb_translate, cb_rotate, cb_scale, source_is_first):
    sel = cmds.ls(selection=True, long=True)
    if len(sel) != 2:
        cmds.inViewMessage(
            amg="<b>Snap:</b> Select exactly two objects (A then B).",
            pos="midCenter", fade=True
        )
        return

    source = sel[0] if source_is_first else sel[1]
    target = sel[1] if source_is_first else sel[0]

    if cb_translate.isChecked():
        pos = cmds.xform(target, query=True, worldSpace=True, translation=True)
        cmds.xform(source, worldSpace=True, translation=pos)

    if cb_rotate.isChecked():
        rot = cmds.xform(target, query=True, worldSpace=True, rotation=True)
        cmds.xform(source, worldSpace=True, rotation=rot)

    if cb_scale.isChecked():
        scl = cmds.xform(target, query=True, worldSpace=True, scale=True)
        cmds.xform(source, worldSpace=True, scale=scl)


# ---------------------------------------------------------------------------
# Workspace control / docking
# ---------------------------------------------------------------------------

def show():
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, restore=True)
        return

    cmds.workspaceControl(
        WORKSPACE_CONTROL_NAME,
        label="Anim Multi Tool",
        tabToControl=("ChannelBoxLayerEditor", -1),
        initialWidth=270,
        minimumWidth=200,
        retain=True,
        uiScript="import animMultiTool; animMultiTool._populate_workspace_control()",
    )


def _populate_workspace_control():
    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance
    from maya import OpenMayaUI as omui

    ptr = omui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
    if not ptr:
        return
    parent = wrapInstance(int(ptr), QtWidgets.QWidget)

    # Clear any existing layout before repopulating
    old_layout = parent.layout()
    if old_layout:
        while old_layout.count():
            item = old_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    else:
        from PySide2 import QtWidgets as _QtWidgets
        layout = _QtWidgets.QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

    widget = _build_widget(parent)
    parent.layout().addWidget(widget)


def close():
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)

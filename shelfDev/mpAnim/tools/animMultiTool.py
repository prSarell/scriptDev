import maya.cmds as cmds
import maya.mel as mel

WORKSPACE_CONTROL_NAME = "animMultiToolWorkspaceControl"
TOOL_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Snap logic (no PySide2 needed here)
# ---------------------------------------------------------------------------

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
# UI builders (PySide2 imported lazily)
# ---------------------------------------------------------------------------

def _build_snap_section():
    from PySide2 import QtWidgets

    group = QtWidgets.QGroupBox("Snap")
    layout = QtWidgets.QVBoxLayout(group)
    layout.setSpacing(4)

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


def _build_tool_widget(parent=None):
    from PySide2 import QtWidgets, QtCore

    widget = QtWidgets.QWidget(parent)
    widget.setObjectName("animMultiToolWidget")

    main_layout = QtWidgets.QVBoxLayout(widget)
    main_layout.setContentsMargins(4, 4, 4, 4)
    main_layout.setSpacing(6)
    main_layout.setAlignment(QtCore.Qt.AlignTop)

    main_layout.addWidget(_build_snap_section())
    main_layout.addStretch()

    return widget


# ---------------------------------------------------------------------------
# Workspace control
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

    # Maya sets the parent context before calling uiScript — query it here
    parent_name = cmds.setParent(query=True)

    ptr = omui.MQtUtil.findLayout(parent_name)
    if not ptr:
        ptr = omui.MQtUtil.findControl(parent_name)
    if not ptr:
        print("[animMultiTool] ERROR: could not find workspace control parent widget")
        return

    parent = wrapInstance(int(ptr), QtWidgets.QWidget)

    # Replace contents if called again (e.g. Maya restoring layout on startup)
    existing = parent.findChild(QtWidgets.QWidget, "animMultiToolWidget")
    if existing:
        existing.deleteLater()

    widget = _build_tool_widget(parent)

    if parent.layout() is None:
        layout = QtWidgets.QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
    else:
        parent.layout().addWidget(widget)

    widget.show()


def close():
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)

import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMayaUI as omui
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance

WORKSPACE_CONTROL_NAME = "animMultiToolWorkspaceControl"
TOOL_VERSION = "1.0"


def get_maya_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QMainWindow)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class AnimMultiTool(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(AnimMultiTool, self).__init__(parent)
        self.setObjectName("animMultiToolWidget")
        self._build_ui()

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)
        main_layout.setAlignment(QtCore.Qt.AlignTop)

        main_layout.addWidget(self._build_snap_section())
        main_layout.addStretch()

    # ------------------------------------------------------------------
    # Snap section
    # ------------------------------------------------------------------

    def _build_snap_section(self):
        group = QtWidgets.QGroupBox("Snap")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setSpacing(4)

        # Checkboxes
        cb_layout = QtWidgets.QHBoxLayout()
        self.cb_translate = QtWidgets.QCheckBox("Translate")
        self.cb_translate.setChecked(True)
        self.cb_rotate = QtWidgets.QCheckBox("Rotate")
        self.cb_rotate.setChecked(True)
        self.cb_scale = QtWidgets.QCheckBox("Scale")
        self.cb_scale.setChecked(False)
        cb_layout.addWidget(self.cb_translate)
        cb_layout.addWidget(self.cb_rotate)
        cb_layout.addWidget(self.cb_scale)
        cb_layout.addStretch()
        layout.addLayout(cb_layout)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_a_to_b = QtWidgets.QPushButton("Snap A  →  B")
        btn_b_to_a = QtWidgets.QPushButton("Snap B  →  A")
        btn_a_to_b.setToolTip("Snap first selected object to second selected object")
        btn_b_to_a.setToolTip("Snap second selected object to first selected object")
        btn_a_to_b.clicked.connect(lambda: self._snap(source_is_first=True))
        btn_b_to_a.clicked.connect(lambda: self._snap(source_is_first=False))
        btn_layout.addWidget(btn_a_to_b)
        btn_layout.addWidget(btn_b_to_a)
        layout.addLayout(btn_layout)

        return group

    def _snap(self, source_is_first):
        sel = cmds.ls(selection=True, long=True)
        if len(sel) != 2:
            cmds.inViewMessage(
                amg="<b>Snap:</b> Select exactly two objects (A then B).",
                pos="midCenter", fade=True
            )
            return

        source = sel[0] if source_is_first else sel[1]
        target = sel[1] if source_is_first else sel[0]

        if self.cb_translate.isChecked():
            pos = cmds.xform(target, query=True, worldSpace=True, translation=True)
            cmds.xform(source, worldSpace=True, translation=pos)

        if self.cb_rotate.isChecked():
            rot = cmds.xform(target, query=True, worldSpace=True, rotation=True)
            cmds.xform(source, worldSpace=True, rotation=rot)

        if self.cb_scale.isChecked():
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
    ptr = omui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
    if not ptr:
        return
    parent = wrapInstance(int(ptr), QtWidgets.QWidget)
    widget = AnimMultiTool(parent)
    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)


def close():
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)

import maya.cmds as cmds

import mtSnap
import mtConstraints
import mtGravity
import mtRefPlane
import mtWSBake
import mtTips

WORKSPACE_CONTROL_NAME = 'multiToolWorkspaceControl'
TOOL_VERSION = '1.0'

BTN_H = 20

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

def _adj(h, amt):
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return '#{:02X}{:02X}{:02X}'.format(
        max(0, min(255, r + amt)),
        max(0, min(255, g + amt)),
        max(0, min(255, b + amt)))

def _btn(bg, fg='white'):
    return (
        'QPushButton {{ background-color:{bg}; color:{fg}; border:none; '
        'padding:2px 4px; font-size:11px; }}'
        'QPushButton:hover {{ background-color:{light}; }}'
        'QPushButton:pressed {{ background-color:{dark}; }}'
    ).format(bg=bg, fg=fg, light=_adj(bg, 25), dark=_adj(bg, -30))

HEADER_STYLE = (
    'QPushButton { background-color:#313131; color:#BCBCBC; border:none; '
    'text-align:left; padding:3px 6px; font-weight:bold; font-size:11px; }'
    'QPushButton:hover { background-color:#3A3A3A; }'
)

HINT_STYLE = 'color:#666; font-size:9px; padding:0px 2px;'

# ---------------------------------------------------------------------------
# Collapsible section
# ---------------------------------------------------------------------------

def _make_collapsible(title, content_builder, collapsed=False):
    from PySide6 import QtWidgets, QtCore

    outer = QtWidgets.QWidget()
    outer.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Preferred,
        QtWidgets.QSizePolicy.Policy.Maximum)

    v = QtWidgets.QVBoxLayout(outer)
    v.setContentsMargins(0, 0, 0, 1)
    v.setSpacing(0)

    header = QtWidgets.QPushButton(('▶  ' if collapsed else '▼  ') + title)
    header.setStyleSheet(HEADER_STYLE)
    header.setMinimumHeight(22)
    v.addWidget(header)

    content = QtWidgets.QWidget()
    inner = QtWidgets.QVBoxLayout(content)
    inner.setContentsMargins(4, 3, 4, 5)
    inner.setSpacing(2)
    content_builder(inner)
    content.setVisible(not collapsed)
    v.addWidget(content)

    def _toggle():
        vis = not content.isVisible()
        content.setVisible(vis)
        header.setText(('▼  ' if vis else '▶  ') + title)

    header.clicked.connect(_toggle)
    return outer

# ---------------------------------------------------------------------------
# Section content builders
# ---------------------------------------------------------------------------

def _snap_content(layout):
    from PySide6 import QtWidgets, QtCore, QtGui

    def _handler():
        mods = QtWidgets.QApplication.keyboardModifiers()
        if mods & QtCore.Qt.KeyboardModifier.ShiftModifier:
            m = QtWidgets.QMenu()
            m.addAction('Translate only', lambda: mtSnap.snap_to('trans'))
            m.addAction('Rotate only',    lambda: mtSnap.snap_to('rots'))
            m.exec(QtGui.QCursor.pos())
        else:
            mtSnap.snap_to('transrot')

    btn = QtWidgets.QPushButton('Snap')
    btn.setMinimumHeight(BTN_H)
    btn.setStyleSheet(_btn('#33664D'))
    btn.setToolTip('Snap: select objects to snap, driver last  |  Shift+click for options')
    btn.clicked.connect(_handler)
    layout.addWidget(btn)

    hint = QtWidgets.QLabel('select driven → driver last  |  shift = options')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _constraints_content(layout):
    from PySide6 import QtWidgets, QtCore

    def _handler(cons_type):
        mods = QtWidgets.QApplication.keyboardModifiers()
        maintain = not bool(mods & QtCore.Qt.KeyboardModifier.ControlModifier)
        mtConstraints.simple_constraint(cons_type, maintain_offset=maintain)

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(2)
    for label, ctype, color in [('point',  'point',  '#668080'),
                                  ('orient', 'orient', '#806680'),
                                  ('parent', 'parent', '#808066')]:
        btn = QtWidgets.QPushButton(label)
        btn.setMinimumHeight(BTN_H)
        btn.setStyleSheet(_btn(color))
        btn.setToolTip(label + ' constraint  |  Ctrl = no offset')
        btn.clicked.connect(lambda checked=False, ct=ctype: _handler(ct))
        row.addWidget(btn)
    layout.addLayout(row)

    hint = QtWidgets.QLabel('select driven → driver last  |  ctrl = no offset')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _gravity_content(layout):
    from PySide6 import QtWidgets, QtCore

    btn = QtWidgets.QPushButton('Gravity Ball')
    btn.setMinimumHeight(BTN_H)
    btn.setStyleSheet(_btn('#336633'))
    btn.setToolTip('Creates a gravity ball from selected object  |  Right-click for custom settings')
    btn.clicked.connect(mtGravity.ball_launcher)
    btn.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

    def _context(pos):
        m = QtWidgets.QMenu()
        m.addAction('Custom Settings…', mtGravity.show_settings)
        m.exec(btn.mapToGlobal(pos))
    btn.customContextMenuRequested.connect(_context)
    layout.addWidget(btn)

    hint = QtWidgets.QLabel('select one object  |  right-click for custom settings')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _ws_bake_content(layout):
    from PySide6 import QtWidgets

    btn = QtWidgets.QPushButton('Bake to World')
    btn.setMinimumHeight(BTN_H)
    btn.setStyleSheet(_btn('#4A5E7A'))
    btn.setToolTip(
        'Select one object, drag-select a frame range on the timeslider, then bake.\n'
        'No range selected = full timeline.')
    btn.clicked.connect(mtWSBake.bake_to_world)
    layout.addWidget(btn)

    hint = QtWidgets.QLabel('select one object  |  drag timeslider for range (or full timeline)')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _ref_plane_content(layout):
    from PySide6 import QtWidgets, QtCore

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(2)

    btn = QtWidgets.QPushButton('Add Ref Plane')
    btn.setMinimumHeight(BTN_H)
    btn.setStyleSheet(_btn('#7A6633', '#1A1A1A'))
    btn.setToolTip('Adds a ref plane to top-right of active camera  |  Right-click to remove')
    btn.clicked.connect(mtRefPlane.add_ref_plane)
    btn.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

    def _context(pos):
        m = QtWidgets.QMenu()
        m.addAction('Remove All Ref Planes', mtRefPlane.remove_ref_planes)
        m.exec(btn.mapToGlobal(pos))
    btn.customContextMenuRequested.connect(_context)
    row.addWidget(btn)

    sync_btn = QtWidgets.QPushButton('Sync Frame Offset')
    sync_btn.setMinimumHeight(BTN_H)
    sync_btn.setStyleSheet(_btn('#4A4A7A'))
    sync_btn.setToolTip('Match image sequence start frame to scene frame range')
    sync_btn.clicked.connect(mtRefPlane.sync_frame_offset)
    row.addWidget(sync_btn)

    layout.addLayout(row)

    hint = QtWidgets.QLabel('click in viewport first  |  right-click to remove all  |  sync offsets frames')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)

# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

def _build_tool_widget(parent=None):
    from PySide6 import QtWidgets, QtCore

    widget = QtWidgets.QWidget(parent)
    widget.setObjectName('multiToolWidget')

    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)
    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    layout.addWidget(_make_collapsible('Snap',         _snap_content))
    layout.addWidget(_make_collapsible('Constraints',  _constraints_content))
    layout.addWidget(_make_collapsible('Gravity Ball', _gravity_content))
    layout.addWidget(_make_collapsible('Ref Plane',    _ref_plane_content))
    layout.addWidget(_make_collapsible('WS Bake',      _ws_bake_content))
    layout.addStretch()

    from PySide6 import QtWidgets
    tips_btn = QtWidgets.QPushButton('Learn Me Something')
    tips_btn.setMinimumHeight(BTN_H + 4)
    tips_btn.setStyleSheet(_btn('#5A3F1E'))
    tips_btn.setToolTip('Shows a random animation tip')
    tips_btn.clicked.connect(mtTips.show_tip)
    layout.addWidget(tips_btn)

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
        label='multiTool',
        tabToControl=('ChannelBoxLayerEditor', -1),
        initialWidth=200,
        minimumWidth=160,
        retain=True,
        uiScript='import multiTool; multiTool._populate_workspace_control()',
    )


def _populate_workspace_control():
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
    from maya import OpenMayaUI as omui

    parent_name = cmds.setParent(query=True)
    ptr = omui.MQtUtil.findLayout(parent_name)
    if not ptr:
        ptr = omui.MQtUtil.findControl(parent_name)
    if not ptr:
        print('[multiTool] ERROR: could not find workspace control parent.')
        return

    parent = wrapInstance(int(ptr), QtWidgets.QWidget)
    existing = parent.findChild(QtWidgets.QWidget, 'multiToolWidget')
    if existing:
        existing.deleteLater()

    widget = _build_tool_widget(parent)
    if parent.layout() is None:
        lay = QtWidgets.QVBoxLayout(parent)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
    else:
        parent.layout().addWidget(widget)
    widget.show()


def close():
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)

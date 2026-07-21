import maya.cmds as cmds

import mtSnap
import mtConstraints
import mtAimRig
import mtGravity
import mtBallistics
import mtRefPlane
import mtWSBake
import mtOSBake
import mtBakeDown
import mtCycleKeys
import mtTips
import mtPanic

WORKSPACE_CONTROL_NAME = 'multiToolWorkspaceControl'
TOOL_VERSION = '1.0'

BTN_H = 20

_dock_btn = None   # 'Dock' button — enabled only while the tool is floating/undocked

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


def _aim_rig_content(layout):
    from PySide6 import QtWidgets

    build_btn = QtWidgets.QPushButton('Build Aim Rig')
    build_btn.setMinimumHeight(BTN_H)
    build_btn.setStyleSheet(_btn('#7A4A33'))
    build_btn.setToolTip(
        'No selection: build at world origin\n'
        'One object: snap and parent-constrain rig to selection\n'
        'Multiple objects: cluster of rigs, chained aim (tail mode)')
    build_btn.clicked.connect(mtAimRig.build_aim_rig)
    layout.addWidget(build_btn)

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(2)

    flip_btn = QtWidgets.QPushButton('Bake & Flip')
    flip_btn.setMinimumHeight(BTN_H)
    flip_btn.setStyleSheet(_btn('#4A5E7A'))
    flip_btn.setToolTip(
        'Select cluster or master_grp_01\n'
        'Bakes parent constraint to keys, then flips —\n'
        'aim_loc drives the original joint')
    flip_btn.clicked.connect(mtAimRig.bake_and_flip)
    row.addWidget(flip_btn)

    bake_btn = QtWidgets.QPushButton('Bake Aim')
    bake_btn.setMinimumHeight(BTN_H)
    bake_btn.setStyleSheet(_btn('#5E4A7A'))
    bake_btn.setToolTip(
        'Select cluster or master_grp_01\n'
        'Bakes joints driven by aim_loc back to direct keys')
    row.addWidget(bake_btn)

    layout.addLayout(row)

    chk_row = QtWidgets.QHBoxLayout()
    chk_row.setSpacing(8)
    chk_row.addStretch()

    layer_chk = QtWidgets.QCheckBox('Bake to Layer')
    layer_chk.setStyleSheet('font-size:10px;')
    chk_row.addWidget(layer_chk)

    delete_chk = QtWidgets.QCheckBox('Delete Rig')
    delete_chk.setStyleSheet('font-size:10px;')
    chk_row.addWidget(delete_chk)

    layout.addLayout(chk_row)

    bake_btn.clicked.connect(
        lambda: mtAimRig.bake_aim(
            to_layer=layer_chk.isChecked(),
            delete_rig=delete_chk.isChecked()))

    hint = QtWidgets.QLabel('build: no sel=origin | one=snap | multi=chain  —  flip/bake: select cluster or grp_01')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _gravity_content(layout):
    from PySide6 import QtWidgets, QtCore, QtGui

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(2)

    # ── Gravity Ball ──────────────────────────────────────────────────────
    gb_btn = QtWidgets.QPushButton('Gravity Ball')
    gb_btn.setMinimumHeight(BTN_H)
    gb_btn.setStyleSheet(_btn('#336633'))
    gb_btn.setToolTip('Creates a gravity ball from selected object  |  Right-click for custom settings')
    gb_btn.clicked.connect(mtGravity.ball_launcher)
    gb_btn.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

    def _grav_context(pos):
        m = QtWidgets.QMenu()
        m.addAction('Custom Settings…', mtGravity.show_settings)
        m.exec(gb_btn.mapToGlobal(pos))
    gb_btn.customContextMenuRequested.connect(_grav_context)
    row.addWidget(gb_btn)

    # ── Ballistics ────────────────────────────────────────────────────────
    bal_btn = QtWidgets.QPushButton('Ballistics')
    bal_btn.setMinimumHeight(BTN_H)
    bal_btn.setStyleSheet(_btn('#2A4A7A'))
    bal_btn.setToolTip('Bake ballistic trajectory from selected object  |  Shift+click for presets')

    # Floor controls — referenced by both the click handler and the row below
    floor_chk = QtWidgets.QCheckBox('Floor')
    floor_chk.setStyleSheet('font-size:10px;')
    floor_val = QtWidgets.QLineEdit('0.0')
    floor_val.setFixedWidth(48)
    floor_val.setFixedHeight(18)
    floor_val.setStyleSheet('font-size:10px;')
    floor_val.setEnabled(False)
    floor_chk.stateChanged.connect(lambda s: floor_val.setEnabled(bool(s)))

    def _get_floor():
        if floor_chk.isChecked():
            try:
                return float(floor_val.text())
            except ValueError:
                return None
        return None

    def _bal_handler():
        mods = QtWidgets.QApplication.keyboardModifiers()
        if mods & QtCore.Qt.KeyboardModifier.ShiftModifier:
            m = QtWidgets.QMenu()
            for key, p in mtBallistics.PRESETS.items():
                m.addAction(p['label'],
                            lambda checked=False, k=key: mtBallistics.launch_preset(k, floor_y=_get_floor()))
            m.exec(QtGui.QCursor.pos())
        else:
            mtBallistics.launch(floor_y=_get_floor())

    bal_btn.clicked.connect(_bal_handler)
    row.addWidget(bal_btn)
    layout.addLayout(row)

    # ── Floor row ─────────────────────────────────────────────────────────
    floor_row = QtWidgets.QHBoxLayout()
    floor_row.setSpacing(4)
    floor_row.addWidget(floor_chk)
    floor_lbl = QtWidgets.QLabel('Y:')
    floor_lbl.setStyleSheet('font-size:10px;')
    floor_row.addWidget(floor_lbl)
    floor_row.addWidget(floor_val)
    floor_row.addStretch()
    layout.addLayout(floor_row)

    hint = QtWidgets.QLabel('select one object  |  G-ball: right-click  |  Ballistics: shift+click for presets')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _cycle_keys_content(layout):
    from PySide6 import QtWidgets, QtCore

    reps_spin = QtWidgets.QSpinBox()
    reps_spin.setMinimum(1)
    reps_spin.setMaximum(99)
    reps_spin.setValue(1)
    reps_spin.setFixedWidth(48)
    reps_spin.setFixedHeight(20)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.setSpacing(2)
    for label, direction in [('Forward', 'forward'), ('Backward', 'backward'), ('Both', 'both')]:
        btn = QtWidgets.QPushButton(label)
        btn.setMinimumHeight(BTN_H)
        btn.setStyleSheet(_btn('#4A6B6B'))
        btn.setToolTip('Tile selected keys {} by N reps'.format(direction))
        btn.clicked.connect(
            lambda checked=False, d=direction: mtCycleKeys.tile_keys(reps_spin.value(), d))
        btn_row.addWidget(btn)
    layout.addLayout(btn_row)

    reps_row = QtWidgets.QHBoxLayout()
    reps_row.setSpacing(4)
    reps_lbl = QtWidgets.QLabel('Reps:')
    reps_lbl.setStyleSheet('font-size:11px;')
    reps_row.addWidget(reps_lbl)
    reps_row.addWidget(reps_spin)
    reps_row.addStretch()
    layout.addLayout(reps_row)

    hint = QtWidgets.QLabel('select objects + keys in Graph Editor, set reps, pick direction')
    hint.setStyleSheet(HINT_STYLE)
    layout.addWidget(hint)


def _bake_content(layout):
    from PySide6 import QtWidgets

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(2)

    ws_btn = QtWidgets.QPushButton('Bake to World')
    ws_btn.setMinimumHeight(BTN_H)
    ws_btn.setStyleSheet(_btn('#4A5E7A'))
    ws_btn.setToolTip(
        'Select one object, drag-select a range, bake to world space.\n'
        'No range selected = full timeline.')
    ws_btn.clicked.connect(mtWSBake.bake_to_world)
    row.addWidget(ws_btn)

    os_btn = QtWidgets.QPushButton('Bake to Object')
    os_btn.setMinimumHeight(BTN_H)
    os_btn.setStyleSheet(_btn('#6B4A5E'))
    os_btn.setToolTip(
        'Select driven first, driver last, drag-select a range, bake to object space.\n'
        'No range selected = full timeline.')
    os_btn.clicked.connect(mtOSBake.bake_to_object)
    row.addWidget(os_btn)

    layout.addLayout(row)

    down_btn = QtWidgets.QPushButton('Bake to Origin Space')
    down_btn.setMinimumHeight(BTN_H)
    down_btn.setStyleSheet(_btn('#4A6B4A'))
    down_btn.setToolTip(
        'Bake driven object(s) back to direct keys and remove constraints.\n'
        'Select an anim layer to bake to that layer instead of base animation.')
    down_btn.clicked.connect(mtBakeDown.bake_to_origin)
    layout.addWidget(down_btn)

    hint = QtWidgets.QLabel('WS: one object  |  OS: driven → driver last  |  origin: select layer to bake to layer')
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
    layout.addWidget(_make_collapsible('Aim Rig',      _aim_rig_content))
    layout.addWidget(_make_collapsible('Physics',      _gravity_content))
    layout.addWidget(_make_collapsible('Ref Plane',    _ref_plane_content))
    layout.addWidget(_make_collapsible('Cycle Keys',   _cycle_keys_content))
    layout.addWidget(_make_collapsible('Bake',          _bake_content))

    global _dock_btn
    dock_btn = QtWidgets.QPushButton('Dock')
    dock_btn.setMinimumHeight(BTN_H)
    dock_btn.setStyleSheet(_btn('#3F3F3F'))
    dock_btn.setToolTip('Redock multiTool to its original position — active only while undocked')
    dock_btn.clicked.connect(_redock)
    dock_btn.setEnabled(_is_floating())
    layout.addWidget(dock_btn)
    _dock_btn = dock_btn

    # No float-state-changed callback exists on workspaceControl — poll instead.
    # Timer is parented to widget so it's torn down automatically when the tool closes.
    dock_timer = QtCore.QTimer(widget)
    dock_timer.setInterval(1000)
    dock_timer.timeout.connect(_update_dock_button)
    dock_timer.start()

    layout.addStretch()

    from PySide6 import QtWidgets
    bottom_row = QtWidgets.QHBoxLayout()
    bottom_row.setSpacing(2)

    tips_btn = QtWidgets.QPushButton('Learn Me Something')
    tips_btn.setMinimumHeight(BTN_H + 4)
    tips_btn.setStyleSheet(_btn('#5A3F1E'))
    tips_btn.setToolTip('Shows a random animation tip')
    tips_btn.clicked.connect(mtTips.show_tip)
    bottom_row.addWidget(tips_btn)

    panic_btn = QtWidgets.QPushButton('Panic')
    panic_btn.setMinimumHeight(BTN_H + 4)
    panic_btn.setStyleSheet(_btn('#7A1A1A'))
    panic_btn.setToolTip('Take a breath')
    panic_btn.clicked.connect(mtPanic.show_panic)
    bottom_row.addWidget(panic_btn)

    layout.addLayout(bottom_row)

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


def _is_floating():
    if not cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
        return False
    return bool(cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, floating=True))


def _update_dock_button():
    if _dock_btn is None:
        return
    try:
        _dock_btn.setEnabled(_is_floating())
    except RuntimeError:
        pass   # underlying Qt widget was deleted (e.g. tool closed) — ignore


def _redock():
    try:
        cmds.workspaceControl(
            WORKSPACE_CONTROL_NAME, edit=True,
            tabToControl=('ChannelBoxLayerEditor', -1))
    except Exception as e:
        cmds.confirmDialog(
            title='multiTool', icon='critical', button=['OK'],
            message='Could not redock multiTool:\n\n{}'.format(e))
        return

    if _is_floating():
        cmds.confirmDialog(
            title='multiTool', icon='warning', button=['OK'],
            message=(
                'Could not redock multiTool.\n\n'
                'Your Maya UI layout is likely locked — unlock it via\n'
                'Windows > Workspaces > Lock UI Elements, then try again.'
            ))
        return

    _update_dock_button()


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

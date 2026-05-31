import maya.cmds as cmds
from PySide6 import QtWidgets, QtCore
from shiboken6 import wrapInstance
from maya import OpenMayaUI as omui

_window = None

# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

def _sample_world_state(obj, frame_a, frame_b):
    """World-space (pos, rot) at two frames via a temp parent-constrained locator."""
    sampler = cmds.spaceLocator()[0]
    cmds.parentConstraint(obj, sampler, mo=False)

    def _at(f):
        pos = (cmds.getAttr(sampler + '.tx', time=f),
               cmds.getAttr(sampler + '.ty', time=f),
               cmds.getAttr(sampler + '.tz', time=f))
        rot = (cmds.getAttr(sampler + '.rx', time=f),
               cmds.getAttr(sampler + '.ry', time=f),
               cmds.getAttr(sampler + '.rz', time=f))
        return pos, rot

    pa, ra = _at(frame_a)
    pb, rb = _at(frame_b)
    cmds.delete(sampler)
    return pa, ra, pb, rb


def _run_simulation(result, pos, rot, vel, rot_vel,
                    grav, metric, frame_rate, drag, floor_y,
                    start_frame, end_frame):
    dt = 1.0 / frame_rate
    x, y, z       = pos
    rx, ry, rz    = rot
    vx, vy, vz    = vel
    drx, dry, drz = rot_vel

    frame = start_frame
    while frame <= end_frame:
        cmds.setKeyframe(result, attribute='tx', value=x,  time=frame)
        cmds.setKeyframe(result, attribute='ty', value=y,  time=frame)
        cmds.setKeyframe(result, attribute='tz', value=z,  time=frame)
        cmds.setKeyframe(result, attribute='rx', value=rx, time=frame)
        cmds.setKeyframe(result, attribute='ry', value=ry, time=frame)
        cmds.setKeyframe(result, attribute='rz', value=rz, time=frame)

        # Gravity step (trapezoidal integration)
        final_vy = vy + grav * dt
        next_y   = y + 0.5 * (vy + final_vy) * dt * metric

        # Floor check — land at floor_y and stop
        if floor_y is not None and next_y <= floor_y:
            cmds.setKeyframe(result, attribute='tx', value=x  + vx  * dt * metric, time=frame + 1)
            cmds.setKeyframe(result, attribute='ty', value=floor_y,                time=frame + 1)
            cmds.setKeyframe(result, attribute='tz', value=z  + vz  * dt * metric, time=frame + 1)
            cmds.setKeyframe(result, attribute='rx', value=rx + drx,               time=frame + 1)
            cmds.setKeyframe(result, attribute='ry', value=ry + dry,               time=frame + 1)
            cmds.setKeyframe(result, attribute='rz', value=rz + drz,               time=frame + 1)
            break

        # Advance position and rotation using current velocities
        x  += vx  * dt * metric
        z  += vz  * dt * metric
        y   = next_y
        vy  = final_vy
        rx += drx
        ry += dry
        rz += drz

        # Apply drag to X/Z and rotation for next frame
        vx  *= drag;  vz  *= drag
        drx *= drag;  dry *= drag;  drz *= drag

        frame += 1

    for ax in ['tx', 'tz', 'rx', 'ry', 'rz']:
        cmds.keyTangent(result, attribute=ax, itt='linear', ott='linear')
    cmds.keyTangent(result, attribute='ty', itt='clamped', ott='clamped')


def launch(frame_rate=24, grav=-9.807, metric=10.0, drag=1.0, floor_y=None):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.inViewMessage(amg='<b>Ballistics:</b> Select one object.',
                           pos='midCenter', fade=True)
        return None
    if len(sel) > 1:
        cmds.inViewMessage(amg='<b>Ballistics:</b> Select only one object.',
                           pos='midCenter', fade=True)
        return None

    obj       = sel[0]
    cur_time  = cmds.currentTime(q=True)
    end_frame = int(cmds.playbackOptions(q=True, max=True))
    short     = obj.split('|')[-1].split(':')[-1]

    pos_prev, rot_prev, pos_cur, rot_cur = _sample_world_state(
        obj, cur_time - 1, cur_time)

    dt = 1.0 / frame_rate
    vel = (
        ((pos_cur[0] - pos_prev[0]) / dt) / metric,
        ((pos_cur[1] - pos_prev[1]) / dt) / metric,
        ((pos_cur[2] - pos_prev[2]) / dt) / metric,
    )
    rot_vel = (
        rot_cur[0] - rot_prev[0],
        rot_cur[1] - rot_prev[1],
        rot_cur[2] - rot_prev[2],
    )

    shapes  = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
    is_mesh = any(cmds.nodeType(s) == 'mesh' for s in shapes)

    if is_mesh:
        result = cmds.duplicate(obj, name='ballistics_' + short)[0]
        if cmds.listRelatives(result, parent=True):
            result = cmds.parent(result, world=True)[0]
        cmds.cutKey(result, attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'], clear=True)
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            try:
                cmds.setAttr(result + '.' + attr, lock=False)
            except Exception:
                pass
    else:
        result = cmds.spaceLocator(name='ballistics_' + short)[0]

    _run_simulation(
        result,
        pos=pos_cur, rot=rot_cur,
        vel=vel, rot_vel=rot_vel,
        grav=grav, metric=metric, frame_rate=frame_rate,
        drag=drag, floor_y=floor_y,
        start_frame=int(cur_time), end_frame=end_frame,
    )

    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
        cmds.setAttr(result + '.' + attr, lock=True)

    cmds.select(result)
    mode = 'duplicate' if is_mesh else 'locator'
    cmds.inViewMessage(
        amg='<b>Ballistics</b> ({}) created.'.format(mode),
        pos='midCenter', fade=True)
    return result


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def _maya_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _field(default, width=80):
    f = QtWidgets.QLineEdit(default)
    f.setFixedHeight(20)
    f.setFixedWidth(width)
    f.setStyleSheet('font-size:11px;')
    return f


class BallisticsWindow(QtWidgets.QWidget):

    def __init__(self):
        super().__init__(_maya_window())
        self.setObjectName('ballisticsWindow')
        self.setWindowFlags(QtCore.Qt.WindowType.Window)
        self.setWindowTitle('Ballistics')
        self.setMinimumWidth(270)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Selection ─────────────────────────────────────────────────────
        sel_box = QtWidgets.QGroupBox('Selection')
        sel_v   = QtWidgets.QVBoxLayout(sel_box)
        sel_v.setContentsMargins(6, 6, 6, 6)
        sel_v.setSpacing(3)

        self._lbl_obj  = QtWidgets.QLabel('—')
        self._lbl_mode = QtWidgets.QLabel('')
        self._lbl_obj.setStyleSheet('font-size:11px;')
        self._lbl_mode.setStyleSheet('font-size:10px; color:#888888;')

        ref_row = QtWidgets.QHBoxLayout()
        ref_row.addWidget(self._lbl_obj)
        ref_row.addStretch()
        ref_btn = QtWidgets.QPushButton('Refresh')
        ref_btn.setFixedHeight(18)
        ref_btn.setStyleSheet(
            'QPushButton { background:#3A3A3A; color:#BCBCBC; border:none;'
            ' font-size:10px; padding:1px 8px; }'
            'QPushButton:hover { background:#4A4A4A; }')
        ref_btn.clicked.connect(self._refresh)
        ref_row.addWidget(ref_btn)

        sel_v.addLayout(ref_row)
        sel_v.addWidget(self._lbl_mode)
        root.addWidget(sel_box)

        # ── Physics ───────────────────────────────────────────────────────
        phys_box = QtWidgets.QGroupBox('Physics')
        form     = QtWidgets.QFormLayout(phys_box)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(4)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self._fr     = _field('24',     60)
        self._grav   = _field('-9.807', 80)
        self._metric = _field('10.0',   60)
        self._drag   = _field('1.0',    60)

        form.addRow('Frame Rate:',   self._fr)
        form.addRow('Gravity:',      self._grav)
        form.addRow('Metric Scale:', self._metric)

        drag_row = QtWidgets.QHBoxLayout()
        drag_row.setSpacing(4)
        drag_row.addWidget(self._drag)
        drag_hint = QtWidgets.QLabel('1.0 = no drag')
        drag_hint.setStyleSheet('font-size:9px; color:#666666;')
        drag_row.addWidget(drag_hint)
        drag_row.addStretch()
        form.addRow('Drag:', drag_row)
        root.addWidget(phys_box)

        # ── Floor ─────────────────────────────────────────────────────────
        floor_box = QtWidgets.QGroupBox('Floor')
        floor_h   = QtWidgets.QHBoxLayout(floor_box)
        floor_h.setContentsMargins(6, 6, 6, 6)
        floor_h.setSpacing(8)

        self._floor_chk = QtWidgets.QCheckBox('Enable')
        self._floor_chk.setStyleSheet('font-size:11px;')
        self._floor_y = _field('0.0', 70)
        self._floor_y.setEnabled(False)
        floor_lbl = QtWidgets.QLabel('Y:')
        floor_lbl.setStyleSheet('font-size:11px;')
        self._floor_chk.stateChanged.connect(
            lambda s: self._floor_y.setEnabled(bool(s)))

        floor_h.addWidget(self._floor_chk)
        floor_h.addStretch()
        floor_h.addWidget(floor_lbl)
        floor_h.addWidget(self._floor_y)
        root.addWidget(floor_box)

        # ── Launch ────────────────────────────────────────────────────────
        launch_btn = QtWidgets.QPushButton('Launch Ballistics')
        launch_btn.setMinimumHeight(34)
        launch_btn.setStyleSheet(
            'QPushButton { background-color:#2A4A7A; color:white; border:none;'
            ' font-size:13px; font-weight:bold; padding:4px; }'
            'QPushButton:hover   { background-color:#3A5A8A; }'
            'QPushButton:pressed { background-color:#1A3A6A; }')
        launch_btn.clicked.connect(self._on_launch)
        root.addWidget(launch_btn)
        root.addStretch()

    def _refresh(self):
        sel = cmds.ls(sl=True)
        if not sel:
            self._lbl_obj.setText('No selection')
            self._lbl_obj.setStyleSheet('font-size:11px; color:#AA5555;')
            self._lbl_mode.setText('')
        elif len(sel) > 1:
            self._lbl_obj.setText('Multiple objects selected')
            self._lbl_obj.setStyleSheet('font-size:11px; color:#AA7733;')
            self._lbl_mode.setText('Select only one object')
        else:
            obj     = sel[0]
            short   = obj.split('|')[-1].split(':')[-1]
            shapes  = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            is_mesh = any(cmds.nodeType(s) == 'mesh' for s in shapes)
            mode    = 'Mesh  →  will duplicate' if is_mesh else 'Control / joint  →  will create locator'
            self._lbl_obj.setText(short)
            self._lbl_obj.setStyleSheet('font-size:11px; color:#88CC88;')
            self._lbl_mode.setText(mode)

    def _on_launch(self):
        try:
            frame_rate = int(self._fr.text())
            grav       = float(self._grav.text())
            metric     = float(self._metric.text())
            drag       = float(self._drag.text())
            floor_y    = float(self._floor_y.text()) if self._floor_chk.isChecked() else None
        except ValueError as e:
            cmds.inViewMessage(amg='<b>Ballistics:</b> Bad value — ' + str(e),
                               pos='midCenter', fade=True)
            return
        launch(frame_rate=frame_rate, grav=grav, metric=metric,
               drag=drag, floor_y=floor_y)
        self._refresh()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def show():
    global _window
    if _window is not None:
        try:
            if not _window.isHidden():
                _window.raise_()
                _window.activateWindow()
                return
        except RuntimeError:
            _window = None

    _window = BallisticsWindow()
    _window.show()

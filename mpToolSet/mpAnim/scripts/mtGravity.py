import maya.cmds as cmds


def grav_calculator(obj, num_frames=49, velocity=9.807, frame_rate=24,
                    trans_y=0.0, frame=1001, grav=-9.807, metric=10.0):
    for _ in range(num_frames):
        cmds.setKeyframe(obj, attribute='ty', value=trans_y, time=(frame, frame))
        final_v  = velocity + (grav * (1.0 / frame_rate))
        trans_y += 0.5 * (velocity + final_v) * (1.0 / frame_rate) * metric
        velocity = final_v
        frame   += 1


def ball_launcher(frame_rate=24, grav=-9.807, metric=10.0):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.inViewMessage(amg='<b>Gravity Ball:</b> Select one object.', pos='midCenter', fade=True)
        return
    if len(sel) > 1:
        cmds.inViewMessage(amg='<b>Gravity Ball:</b> Select only one object.', pos='midCenter', fade=True)
        return

    obj      = sel[0]
    cur_time = cmds.currentTime(q=True)
    num_frames = int(cmds.playbackOptions(q=True, max=True) - cur_time)

    # Sample world position via temporary locator
    sampler = cmds.polySphere()[0]
    cmds.pointConstraint(obj, sampler, mo=False)
    cx = cmds.getAttr(sampler + '.translateX')
    cy = cmds.getAttr(sampler + '.translateY')
    cz = cmds.getAttr(sampler + '.translateZ')
    px = cmds.getAttr(sampler + '.translateX', time=(cur_time - 1))
    py = cmds.getAttr(sampler + '.translateY', time=(cur_time - 1))
    pz = cmds.getAttr(sampler + '.translateZ', time=(cur_time - 1))
    cmds.delete(sampler)

    velocity = ((cy - py) / (1.0 / frame_rate)) / metric

    ball = cmds.polySphere()[0]
    grav_calculator(ball, num_frames=num_frames, velocity=velocity,
                    frame_rate=frame_rate, trans_y=cy,
                    frame=int(cur_time), grav=grav, metric=metric)

    cmds.setKeyframe(ball, attribute='tx', value=cx,            time=(cur_time,))
    cmds.setKeyframe(ball, attribute='tz', value=cz,            time=(cur_time,))
    cmds.setKeyframe(ball, attribute='tx', value=cx + (cx - px), time=(cur_time + 1,))
    cmds.setKeyframe(ball, attribute='tz', value=cz + (cz - pz), time=(cur_time + 1,))
    cmds.keyTangent(ball, itt='clamped', ott='clamped')
    cmds.setInfinity(ball, poi='linear')

    shapes = cmds.listRelatives(obj, shapes=True) or []
    if shapes:
        bb    = cmds.exactWorldBoundingBox(shapes[0])
        size  = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
        scale = (size / 2.0) * 1.1
        for ax in ('X', 'Y', 'Z'):
            cmds.setAttr(ball + '.scale' + ax, scale)

    for ax in ('X', 'Y', 'Z'):
        cmds.setAttr(ball + '.translate' + ax, lock=True)

    ball = cmds.rename(ball, 'gravityBall_' + obj.split('|')[-1].split(':')[-1])
    cmds.select(ball)
    cmds.inViewMessage(amg='<b>Gravity Ball</b> created.', pos='midCenter', fade=True)


def show_settings():
    from PySide6 import QtWidgets

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle('Gravity Ball — Custom Settings')
    dlg.setFixedWidth(240)

    form = QtWidgets.QFormLayout(dlg)
    form.setContentsMargins(8, 8, 8, 8)
    form.setSpacing(4)

    specs = [
        ('Frame Rate',      'frame_rate',  '24'),
        ('Gravity',         'grav',        '-9.807'),
        ('Metric Scale',    'metric',      '10'),
        ('Num Frames',      'num_frames',  '49'),
        ('Initial Velocity','velocity',    '9.807'),
        ('Start Y',         'trans_y',     '0'),
        ('Start Frame',     'frame',       '1001'),
    ]
    fields = {}
    for label, key, default in specs:
        edit = QtWidgets.QLineEdit(default)
        form.addRow(label + ':', edit)
        fields[key] = edit

    btn_row = QtWidgets.QHBoxLayout()
    ok  = QtWidgets.QPushButton('Create')
    can = QtWidgets.QPushButton('Cancel')
    ok.clicked.connect(dlg.accept)
    can.clicked.connect(dlg.reject)
    btn_row.addWidget(ok)
    btn_row.addWidget(can)
    form.addRow(btn_row)

    if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return

    try:
        ball = cmds.polySphere()[0]
        grav_calculator(
            ball,
            num_frames=int(fields['num_frames'].text()),
            velocity=float(fields['velocity'].text()),
            frame_rate=int(fields['frame_rate'].text()),
            trans_y=float(fields['trans_y'].text()),
            frame=int(fields['frame'].text()),
            grav=float(fields['grav'].text()),
            metric=float(fields['metric'].text()),
        )
        for ax in ('X', 'Y', 'Z'):
            cmds.setAttr(ball + '.translate' + ax, lock=True)
        ball = cmds.rename(ball, 'gravityBall_custom')
        cmds.select(ball)
        cmds.inViewMessage(amg='<b>Gravity Ball (custom)</b> created.', pos='midCenter', fade=True)
    except ValueError as e:
        cmds.inViewMessage(amg='<b>Gravity Ball:</b> Bad value — ' + str(e), pos='midCenter', fade=True)

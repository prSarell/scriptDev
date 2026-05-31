import maya.cmds as cmds
import maya.mel as mel

METRIC = 10.0
GRAV   = -9.807

PRESETS = {
    'tiny_light': {
        'label':       'Tiny Light  (pen / ping-pong)',
        'drag_ps':     0.50,
        'friction_ps': 0.10,
    },
    'small_light': {
        'label':       'Small Light  (basketball)',
        'drag_ps':     0.75,
        'friction_ps': 0.20,
    },
    'big_heavy': {
        'label':       'Big Heavy  (person → car)',
        'drag_ps':     0.93,
        'friction_ps': 0.44,
    },
    'massive_heavy': {
        'label':       'Massive Heavy  (bus → whale)',
        'drag_ps':     0.99,
        'friction_ps': 0.70,
    },
}

_DEFAULT_DRAG_PS     = 1.0
_DEFAULT_FRICTION_PS = 0.30

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_fps():
    return mel.eval('currentTimeUnitToFPS()')


def _sample_world_state(obj, frame_a, frame_b):
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


def _build_result(obj, short):
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
    return result, is_mesh

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def _run_simulation(result, pos, rot, vel, rot_vel,
                    fps, drag_pfr, friction_pfr, floor_y, start_frame, end_frame):
    dt = 1.0 / fps
    x, y, z       = pos
    rx, ry, rz    = rot
    vx, vy, vz    = vel
    drx, dry, drz = rot_vel
    on_floor      = False

    frame = start_frame
    while frame <= end_frame:
        cmds.setKeyframe(result, attribute='tx', value=x,  time=frame)
        cmds.setKeyframe(result, attribute='ty', value=y,  time=frame)
        cmds.setKeyframe(result, attribute='tz', value=z,  time=frame)
        cmds.setKeyframe(result, attribute='rx', value=rx, time=frame)
        cmds.setKeyframe(result, attribute='ry', value=ry, time=frame)
        cmds.setKeyframe(result, attribute='rz', value=rz, time=frame)

        if on_floor:
            vx  *= friction_pfr;  vz  *= friction_pfr
            drx *= friction_pfr;  dry *= friction_pfr;  drz *= friction_pfr
            x  += vx * dt * METRIC
            z  += vz * dt * METRIC
            rx += drx;  ry += dry;  rz += drz
        else:
            final_vy = vy + GRAV * dt
            next_y   = y + 0.5 * (vy + final_vy) * dt * METRIC

            if floor_y is not None and next_y <= floor_y:
                y        = floor_y
                vy       = 0.0
                on_floor = True
                x  += vx * dt * METRIC
                z  += vz * dt * METRIC
                rx += drx;  ry += dry;  rz += drz
            else:
                x  += vx  * dt * METRIC
                z  += vz  * dt * METRIC
                y   = next_y
                vy  = final_vy
                rx += drx;  ry += dry;  rz += drz
                vx  *= drag_pfr;  vz  *= drag_pfr
                drx *= drag_pfr;  dry *= drag_pfr;  drz *= drag_pfr

        frame += 1

    for ax in ['tx', 'tz', 'rx', 'ry', 'rz']:
        cmds.keyTangent(result, attribute=ax, itt='linear', ott='linear')
    cmds.keyTangent(result, attribute='ty', itt='clamped', ott='clamped')

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def launch(drag_ps=_DEFAULT_DRAG_PS, friction_ps=_DEFAULT_FRICTION_PS, floor_y=None):
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
    fps       = _get_fps()

    pos_prev, rot_prev, pos_cur, rot_cur = _sample_world_state(
        obj, cur_time - 1, cur_time)

    dt = 1.0 / fps
    vel = (
        ((pos_cur[0] - pos_prev[0]) / dt) / METRIC,
        ((pos_cur[1] - pos_prev[1]) / dt) / METRIC,
        ((pos_cur[2] - pos_prev[2]) / dt) / METRIC,
    )
    rot_vel = (
        rot_cur[0] - rot_prev[0],
        rot_cur[1] - rot_prev[1],
        rot_cur[2] - rot_prev[2],
    )

    drag_pfr     = drag_ps     ** (1.0 / fps)
    friction_pfr = friction_ps ** (1.0 / fps)

    result, is_mesh = _build_result(obj, short)

    _run_simulation(
        result,
        pos=pos_cur, rot=rot_cur,
        vel=vel, rot_vel=rot_vel,
        fps=fps, drag_pfr=drag_pfr, friction_pfr=friction_pfr,
        floor_y=floor_y,
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


def launch_preset(key, floor_y=None):
    p = PRESETS[key]
    launch(drag_ps=p['drag_ps'], friction_ps=p['friction_ps'], floor_y=floor_y)

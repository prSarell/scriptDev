"""
Publish Tool — shot cameras
Publishes a shot's camera from a shot scene on scratch as two files: the
camera (all its settings, no keys) and its keys (baked curves + a map of
which curve drives which attribute). No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §3i "Cameras" and "The ID rule".

    scratch  G:\\scratch\\NWF_SHF\\maya\\sequences\\EAP_010\\EAP_010_010\\scenes\\layout_003.ma
    H drive  G:\\H\\NWF_SHF\\maya\\sequences\\EAP_010\\EAP_010_010\\scenes\\s1234567\\
               EAP_010_010_s1234567_cam_v001.ma
               EAP_010_010_s1234567_camAnim_v001.ma
               EAP_010_010_s1234567_camAnim_v001.json

Rules (DECIDED 2026-10-12):
- A camera belongs to a shot; the ShotGrid Version goes on the Shot.
- Keys are baked every frame first, so the curve shape survives rigs,
  constraints, tangents and expressions. Every animated/driven attribute on
  the camera shape is found and baked, not from a hand-made list.
- All camera data (film back, display options...) travels in the camera file.
- No scale on cameras (it breaks Arnold renders): the published camera is
  always scale 1, no scale keys, scale channels locked.
"""

import os
import re
import json

import maya.cmds as cmds

import publishTool_api as api
from publishTool_api import PublishError

CAM_CODE = "cam"
KEYS_CODE = "camAnim"
CAM_LABEL = "Camera"
PUBLISHED_CAMERA = "shotCam"         # node name inside the published camera file
STARTUP_CAMERAS = ("persp", "top", "front", "side")
TRANSFORM_ATTRS = ("translateX", "translateY", "translateZ",
                   "rotateX", "rotateY", "rotateZ")
SCALE_ATTRS = ("scaleX", "scaleY", "scaleZ")


# ---------------------------------------------------------------------------
# Working out which shot the open scene is in
# ---------------------------------------------------------------------------

def shot_context(scene_path):
    """Describe the shot a scene belongs to.

    Expects <FILM>/maya/sequences/<SEQ>/<SHOT>/scenes/.../<file>.
    """
    root, rel = api.find_film_folder(scene_path)
    if (len(rel) < 7 or rel[1] != "maya" or rel[2] != "sequences"
            or rel[5] != "scenes"):
        raise PublishError(
            "This scene isn't in a shot's scenes folder.\n"
            "Expected: <film>\\maya\\sequences\\<sequence>\\<shot>\\scenes\\")
    return {
        "kind": "shot",
        "root": root,
        "film": rel[0],
        "seq": rel[3],
        "shot": rel[4],
        "rel_folder": rel[:6],                            # the shot's scenes folder
        "shot_project": os.path.join(root, *rel[:5]),     # on scratch
    }


# ---------------------------------------------------------------------------
# Which camera
# ---------------------------------------------------------------------------

def camera_transform(node):
    """The camera transform for a transform or camera shape, else None."""
    if not cmds.objExists(node):
        return None
    if cmds.nodeType(node) == "camera":
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, type="camera") or []
    return cmds.ls(node, long=True)[0] if shapes else None


def contains_camera(objects):
    """Cameras among objects or anywhere under them (for asset publishes,
    which must not carry a shot camera out by accident)."""
    found = []
    for obj in objects:
        if not cmds.objExists(obj):
            continue
        for shape in cmds.listRelatives(obj, allDescendents=True, fullPath=True,
                                        type="camera") or []:
            found.append(cmds.listRelatives(shape, parent=True)[0])
        if camera_transform(obj):
            found.append(cmds.ls(obj)[0])
    return sorted(set(found))


def check_camera(objects):
    """A camera publish takes exactly one camera, and not a startup one.
    Returns its transform (long name)."""
    cams = [c for c in (camera_transform(o) for o in objects or []) if c]
    others = [o for o in objects or [] if not camera_transform(o)]
    if not objects:
        raise PublishError("Select the shot camera in Maya, then Add to List.")
    if others:
        raise PublishError("A Camera publish takes only the camera. Not a camera: %s"
                           % ", ".join(others))
    if len(set(cams)) != 1:
        raise PublishError("Select just one camera (selected: %s)."
                           % ", ".join(cmds.ls(cams)))
    short = cmds.ls(cams[0])[0].split("|")[-1].split(":")[-1]
    if short in STARTUP_CAMERAS:
        raise PublishError("'%s' is one of Maya's built-in cameras. "
                           "Make a new camera for the shot." % short)
    return cams[0]


# ---------------------------------------------------------------------------
# Versions on the H drive
# ---------------------------------------------------------------------------

def published_camera_versions(folder, shot, login):
    """Version numbers this person has already used for either camera file
    in their folder."""
    exts = ("ma", "mb", "json")
    return sorted(set(api.published_versions(folder, shot, login, CAM_CODE, exts) +
                      api.published_versions(folder, shot, login, KEYS_CODE, exts)))


def camera_file_names(shot, login, version):
    """e.g. EAP_010_010_s1234567_cam_v001.ma, ..._camAnim_v001.ma/.json"""
    return {"camera": api.published_name(shot, login, CAM_CODE, version, ".ma"),
            "keys": api.published_name(shot, login, KEYS_CODE, version, ".ma"),
            "map": api.published_name(shot, login, KEYS_CODE, version, ".json")}


def plan_camera(scene_path, h_root, scratch_root, camera=None):
    """Work out where a camera publish would go, without touching anything."""
    h_root, scratch_root = api.resolve_root(h_root), api.resolve_root(scratch_root)
    api.check_roots(h_root, scratch_root)
    ctx = shot_context(scene_path)
    if not api._same_path(ctx["root"], scratch_root):
        where = "the H drive" if api._same_path(ctx["root"], h_root) else ctx["root"]
        raise PublishError(
            "This scene isn't on your scratch drive (%s), it's on %s.\n"
            "Work from scratch and publish from there." % (scratch_root, where))
    h_shot = os.path.join(h_root, *ctx["rel_folder"][:5])
    if not os.path.isdir(h_shot):
        raise PublishError("No folder for shot %s on the H drive:\n%s" % (ctx["shot"], h_shot))
    if camera:
        check_camera([camera])

    login = api.who()
    h_folder = api.personal_folder(h_root, ctx["rel_folder"][:5], login)
    versions = published_camera_versions(h_folder, ctx["shot"], login)
    version = (versions[-1] + 1) if versions else 1
    names = camera_file_names(ctx["shot"], login, version)
    ctx.update({
        "login": login,
        "code": CAM_CODE,
        "asset": ctx["shot"],                # what playblast_frames names things by
        "asset_project": ctx["shot_project"],
        "h_folder": h_folder,
        "version": version,
        "dest": os.path.join(h_folder, names["camera"]),
        "keys_dest": os.path.join(h_folder, names["keys"]),
        "map_dest": os.path.join(h_folder, names["map"]),
    })
    return ctx


# ---------------------------------------------------------------------------
# Bake: a clean world-space copy, every frame keyed
# ---------------------------------------------------------------------------

def _driven_shape_attrs(shape):
    """Attributes on the camera shape that something drives: keys,
    expressions, connections. These are the ones that need baking."""
    attrs = []
    pairs = cmds.listConnections(shape, source=True, destination=False,
                                 connections=True, plugs=True) or []
    for i in range(0, len(pairs), 2):
        attr = pairs[i].split(".", 1)[1]
        if attr == "message" or "[" in attr or "." in attr:
            continue        # image planes, compound children etc.
        if cmds.attributeQuery(attr, node=shape, exists=True):
            attrs.append(attr)
    return sorted(set(attrs))


def bake_camera(camera, start, end):
    """Make the publishable camera: a world-space duplicate named shotCam,
    driven by the original and baked every frame from start to end. Scale is
    1 and locked. Returns (transform, shape, {curve: (where, attr)}, warnings)."""
    src_tr = camera_transform(camera)
    src_sh = cmds.listRelatives(src_tr, shapes=True, fullPath=True, type="camera")[0]

    pub_tr = cmds.duplicate(src_tr, name=PUBLISHED_CAMERA, returnRootsOnly=True,
                            inputConnections=False)[0]
    # Children that came with the duplicate (constraints, image planes,
    # anything parented under the camera) are not part of the camera.
    for child in cmds.listRelatives(pub_tr, children=True, fullPath=True,
                                    type="transform") or []:
        cmds.delete(child)
    for child in cmds.listRelatives(pub_tr, children=True, fullPath=True) or []:
        if cmds.nodeType(child) != "camera":
            cmds.delete(child)
    if cmds.listRelatives(pub_tr, parent=True):
        pub_tr = cmds.parent(pub_tr, world=True)[0]
    pub_tr = cmds.ls(pub_tr, long=True)[0]
    pub_sh = cmds.listRelatives(pub_tr, shapes=True, fullPath=True, type="camera")[0]
    for attr in TRANSFORM_ATTRS + SCALE_ATTRS + ("visibility",):
        cmds.setAttr("%s.%s" % (pub_tr, attr), lock=False)

    driven = _driven_shape_attrs(src_sh)
    for attr in driven:
        cmds.setAttr("%s.%s" % (pub_sh, attr), lock=False)
        cmds.connectAttr("%s.%s" % (src_sh, attr), "%s.%s" % (pub_sh, attr), force=True)
    # Position and rotation in world space; scale deliberately not followed.
    constraint = cmds.parentConstraint(src_tr, pub_tr, maintainOffset=False)[0]

    targets = ["%s.%s" % (pub_tr, a) for a in TRANSFORM_ATTRS] + \
              ["%s.%s" % (pub_sh, a) for a in driven]
    cmds.bakeResults(targets, time=(start, end), sampleBy=1, simulation=True,
                     preserveOutsideKeys=False, disableImplicitControl=True,
                     minimizeRotation=True)
    if cmds.objExists(constraint):
        cmds.delete(constraint)
    for attr in driven:     # anything still wired to the original
        plug = "%s.%s" % (pub_sh, attr)
        for src in cmds.listConnections(plug, source=True, destination=False,
                                        plugs=True) or []:
            if not cmds.nodeType(src.split(".")[0]).startswith("animCurve"):
                cmds.disconnectAttr(src, plug)

    for attr in SCALE_ATTRS:
        cmds.setAttr("%s.%s" % (pub_tr, attr), 1)
        cmds.setAttr("%s.%s" % (pub_tr, attr), lock=True)

    curves = {}
    for node, where in ((pub_tr, "transform"), (pub_sh, "shape")):
        pairs = cmds.listConnections(node, source=True, destination=False,
                                     connections=True, plugs=True, type="animCurve") or []
        for i in range(0, len(pairs), 2):
            attr = pairs[i].split(".", 1)[1]
            curve = pairs[i + 1].split(".")[0]
            name = "%s_%s%s" % (PUBLISHED_CAMERA, "shape_" if where == "shape" else "", attr)
            curves[cmds.rename(curve, name)] = (where, attr)
    rot = [c for c, (w, a) in curves.items() if w == "transform" and a.startswith("rotate")]
    if rot:
        cmds.filterCurve(rot, filter="euler")

    warnings = []
    scales = set(round(cmds.getAttr(src_sh + ".cameraScale", time=t), 4)
                 for t in range(int(start), int(end) + 1))
    if scales != {1.0}:
        warnings.append("This camera's Camera Scale isn't 1 (%s). It was kept as is; "
                        "check it renders correctly in Arnold."
                        % ", ".join(str(s) for s in sorted(scales)))
    return pub_tr, pub_sh, curves, warnings


# ---------------------------------------------------------------------------
# Export the two files
# ---------------------------------------------------------------------------

def _export(nodes, path):
    cmds.select(nodes, replace=True)
    cmds.file(path, exportSelected=True, type="mayaAscii", force=True,
              constructionHistory=False, channels=False, constraints=False,
              expressions=False, shader=False, preserveReferences=False)
    api._lock(path)


def export_camera(camera, plan, start, end, scene_path):
    """Bake, then write the keys file + map and the camera file to the H
    drive. Nothing it makes is left in the open scene. Returns warnings."""
    for key in ("dest", "keys_dest", "map_dest"):
        if os.path.exists(plan[key]):
            raise PublishError("%s already exists — try again." % plan[key])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])

    selection = cmds.ls(selection=True)
    current = cmds.currentTime(query=True)
    made = []
    try:
        pub_tr, pub_sh, curves, warnings = bake_camera(camera, start, end)
        made = [pub_tr] + list(curves)
        _export(list(curves), plan["keys_dest"])
        mapping = {
            "camera": PUBLISHED_CAMERA,
            "shot": plan["shot"],
            "login": plan["login"],
            "version": plan["version"],
            "start": start,
            "end": end,
            "fps": api._scene_fps(),
            "source_scene": os.path.basename(scene_path),
            "source_camera": cmds.ls(camera)[0],
            "curves": dict((c, list(v)) for c, v in sorted(curves.items())),
        }
        with open(plan["map_dest"], "w") as f:
            json.dump(mapping, f, indent=2)
        api._lock(plan["map_dest"])
        cmds.delete(list(curves))      # the camera file carries no keys
        made = [pub_tr]
        _export([pub_tr], plan["dest"])
    finally:
        existing = [n for n in made if cmds.objExists(n)]
        if existing:
            cmds.delete(existing)
        cmds.currentTime(current)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return warnings


# ---------------------------------------------------------------------------
# ShotGrid — shot folder -> Shot
# ---------------------------------------------------------------------------

def find_shotgrid_shot(plan, h_root):
    """Return the ShotGrid Shot whose code matches the shot folder.
    (Later: read the Shot ID from shot.json — spec "The ID rule".)"""
    film_config = api.load_film_config(h_root, plan["film"])
    sg = api._shotgrid().get_connection()
    project = {"type": "Project", "id": film_config["shotgrid_project_id"]}
    shots = sg.find("Shot", [["project", "is", project]], ["id", "code"])
    matches = [s for s in shots if api._match_key(s["code"]) == api._match_key(plan["shot"])]
    if not matches:
        raise PublishError("No ShotGrid shot matches the folder '%s' in %s."
                           % (plan["shot"], film_config.get("shotgrid_project_name", project)))
    if len(matches) > 1:
        raise PublishError("More than one ShotGrid shot matches '%s': %s"
                           % (plan["shot"], ", ".join(s["code"] for s in matches)))
    return matches[0]


# ---------------------------------------------------------------------------
# One-click camera publish
# ---------------------------------------------------------------------------

def publish_camera(scene_path, h_root, scratch_root, camera, frame_count=None, notes=""):
    """ShotGrid lookup -> playblast through the camera -> bake + write both
    files to the H drive -> ShotGrid Version on the Shot.

    Shot publishes always use the whole playback range, for the baked keys
    and the ShotGrid movie alike. frame_count is ignored (kept so callers
    can pass the asset setting without a special case)."""
    frame_count = None
    h_root = api.resolve_root(h_root)
    api.check_script_nodes()
    camera = check_camera([camera])
    plan = plan_camera(scene_path, h_root, scratch_root)
    plan["objects"] = [cmds.ls(camera)[0]]
    plan["sg_shot"] = find_shotgrid_shot(plan, h_root)
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    plan["frames_folder"], files = api.playblast_frames(plan, frame_count, camera=camera)

    plan["warnings"] = export_camera(camera, plan, start, end, scene_path)

    note = ("Published camera v%03d to the H drive:\n%s\n%s\n"
            "(from %s, camera %s, keys baked %d-%d)" % (
                plan["version"], plan["dest"], plan["keys_dest"],
                os.path.basename(scene_path), plan["objects"][0], start, end))
    if notes.strip():
        note = notes.strip() + "\n\n---\n" + note
    plan["sg_version"] = plan["sg_error"] = None
    rvio = api.find_rvio()
    plan["movie_warning"] = None if rvio else (
        "RV's rvio wasn't found on this machine, so ShotGrid got a thumbnail "
        "but no playable movie.")
    # Sound in the movie, for lip sync (same as shotSub).
    plan["audio"], audio_offset = api.scene_audio(start)
    try:
        plan["sg_version"] = api.upload_with_audio(
            api._shotgrid(), plan, plan["audio"], audio_offset,
            "Shot", plan["sg_shot"]["id"], plan["frames_folder"],
            files=files, notes=note, fps=api._scene_fps(), rvio_path=rvio,
            machine_diagnostic=plan["movie_warning"])
    except Exception as e:     # files already on the H drive; report, don't lose them
        plan["sg_error"] = str(e)
    else:
        api.remove_frames(plan["frames_folder"], plan["shot_project"])
    return plan

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

Camera group (DECIDED 2026-10-20, user):
    <shot>_cam_GRP          pipe stamp (like the model group) + image plane info
      shotCam               the camera; animated attributes driven 1:1 by...
      shotCam_DATA          ...one attribute each here, which the keys drive
The group is named from the shot being published, never a fixed name. The
keys file holds the curves for shotCam_DATA, the map says which attribute
each one drives. Build imports it live, so the camera behaves like a
referenced one (driven, locked) with no reference path to manage.
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
DATA_SUFFIX = "_DATA"                # shotCam_DATA: holds the keys, drives the camera
MAP_FORMAT = 2                       # 2 = camera group + data node (2026-10-20)
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


def camera_in_group(node):
    """The camera for anything inside a published camera group (the group
    itself, camera1_DATA, ...), so selecting any part of the shot camera
    gives a Camera row. None otherwise."""
    parts = ((cmds.ls(node, long=True) or [""])[0]).split("|")
    for i in range(len(parts), 1, -1):
        group = "|".join(parts[:i])
        attr = api.PIPE_ATTR_PREFIX + "department"
        if cmds.attributeQuery(attr, node=group, exists=True) \
                and cmds.getAttr("%s.%s" % (group, attr)) == CAM_CODE:
            for child in cmds.listRelatives(group, children=True, fullPath=True,
                                            type="transform") or []:
                if camera_transform(child):
                    return child
    return None


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


def camera_group_name(shot):
    """<shot>_cam_GRP, like the model group's <asset>_<department>_GRP.
    Always from the shot being published (EAP_010_010_cam_GRP, ...)."""
    return "%s_%s_GRP" % (shot, CAM_CODE)


def data_attr_name(where, attr):
    """The data node's attribute for one camera attribute, e.g.
    cam_translateX, camShape_focalLength."""
    return ("camShape_" if where == "shape" else "cam_") + attr


# Data node attribute type for each camera attribute type. Matching types
# means no unit-conversion nodes between curve, data node and camera.
_ATTR_TYPES = {"doubleAngle": "doubleAngle", "doubleLinear": "doubleLinear",
               "bool": "bool", "long": "long", "short": "long", "byte": "long",
               "enum": "long", "time": "time"}


def make_data_node(pub_tr, pub_sh, curves):
    """Move the baked keys off the camera onto shotCam_DATA: each curve now
    drives one attribute there, which drives the camera attribute 1:1.
    Returns (data node, {curve: data attr}, {data attr: [where, attr]})."""
    data = cmds.createNode("transform", name=PUBLISHED_CAMERA + DATA_SUFFIX)
    data = cmds.ls(data, long=True)[0]
    curve_attrs, attrs = {}, {}
    for curve, (where, attr) in sorted(curves.items()):
        node = pub_sh if where == "shape" else pub_tr
        plug = "%s.%s" % (node, attr)
        name = data_attr_name(where, attr)
        cmds.addAttr(data, longName=name, keyable=True,
                     attributeType=_ATTR_TYPES.get(cmds.getAttr(plug, type=True), "double"))
        cmds.connectAttr(curve + ".output", "%s.%s" % (data, name), force=True)
        cmds.connectAttr("%s.%s" % (data, name), plug, force=True)
        new = cmds.rename(curve, "%s%s_%s" % (PUBLISHED_CAMERA, DATA_SUFFIX, name))
        curve_attrs[new] = name
        attrs[name] = [where, attr]
    return data, curve_attrs, attrs


def image_plane_info(camera):
    """What image sequences the camera uses (user, 2026-10-20: the publish
    records their location and name). Recorded only; image planes are not
    published or rebuilt. [{node, folder, file, image, type,
    useFrameExtension, frameOffset, ...}]"""
    shape = cmds.listRelatives(camera_transform(camera), shapes=True, fullPath=True,
                               type="camera")[0]
    planes = []
    for ip in sorted(set(cmds.listConnections(shape + ".imagePlane", source=True,
                                              destination=False, shapes=True,
                                              type="imagePlane") or [])):
        image = cmds.getAttr(ip + ".imageName") or ""
        info = {"node": ip.split("|")[-1], "image": image,
                "folder": os.path.dirname(image), "file": os.path.basename(image)}
        for attr in ("type", "useFrameExtension", "frameOffset", "frameIn", "frameOut",
                     "frameCache", "depth", "fit", "displayMode"):
            if cmds.attributeQuery(attr, node=ip, exists=True):
                info[attr] = cmds.getAttr("%s.%s" % (ip, attr))
        planes.append(info)
    return planes


# ---------------------------------------------------------------------------
# Export the two files
# ---------------------------------------------------------------------------

def _export(nodes, path):
    cmds.select(nodes, replace=True)
    cmds.file(path, exportSelected=True, type="mayaAscii", force=True,
              constructionHistory=False, channels=False, constraints=False,
              expressions=False, shader=False, preserveReferences=False)
    api._lock(path)


# The shot's frame range in the edit (user, 2026-10-20: "the publish group
# ... should also hold frame range data for the shot from the latest edl on
# shotgrid"). An EDL imported to ShotGrid is a Cut with one CutItem per
# shot; the newest Cut holding the shot wins. Without one, the Shot's own
# cut fields; without those, nothing (a warning, never a refusal).
EDIT_FIELDS = (("cutIn", "cut_item_in"), ("cutOut", "cut_item_out"),
               ("cutDuration", "cut_item_duration"), ("editIn", "edit_in"),
               ("editOut", "edit_out"), ("cutOrder", "cut_order"))
SHOT_EDIT_FIELDS = (("cutIn", "sg_cut_in"), ("cutOut", "sg_cut_out"),
                    ("cutDuration", "sg_cut_duration"), ("cutOrder", "sg_cut_order"),
                    ("headIn", "sg_head_in"), ("tailOut", "sg_tail_out"))
EDIT_NONE, EDIT_CUT, EDIT_SHOT = "none", "cut", "shot"


def shot_edit_range(sg, shot):
    """{"source", "cut", "cutId", "cutDate", ...frame fields} for a ShotGrid
    Shot: frame fields from the newest Cut holding it (head/tail from the
    Shot), else from the Shot's cut fields. Only values ShotGrid has."""
    shot_data = sg.find_one("Shot", [["id", "is", shot["id"]]],
                            [f for _, f in SHOT_EDIT_FIELDS]) or {}
    items = sg.find("CutItem", [["shot", "is", {"type": "Shot", "id": shot["id"]}]],
                    [f for _, f in EDIT_FIELDS] + ["cut", "cut.Cut.code",
                                                   "cut.Cut.created_at"])
    items = [i for i in items if i.get("cut") and i.get("cut.Cut.created_at")]
    found = {"source": EDIT_NONE, "cut": ""}
    if items:
        item = max(items, key=lambda i: i["cut.Cut.created_at"])
        found.update(source=EDIT_CUT, cut=item.get("cut.Cut.code") or "",
                     cutId=item["cut"]["id"],
                     cutDate=item["cut.Cut.created_at"].isoformat(timespec="seconds"))
        fields = EDIT_FIELDS
        data = item
        for name, field in SHOT_EDIT_FIELDS:
            if name in ("headIn", "tailOut") and shot_data.get(field) is not None:
                found[name] = shot_data[field]
    elif shot_data.get("sg_cut_in") is not None or shot_data.get("sg_cut_out") is not None:
        found["source"] = EDIT_SHOT
        fields, data = SHOT_EDIT_FIELDS, shot_data
    else:
        return found
    for name, field in fields:
        if data.get(field) is not None:
            found[name] = int(data[field])
    return found


def edit_range_warning(edit, start, end):
    """Say so when there's no edit range, or the timeline's length differs
    from the shot's length in the edit (lengths only: the edit counts from
    its own frame numbers)."""
    if edit.get("source", EDIT_NONE) == EDIT_NONE:
        return ("ShotGrid has no edit range for this shot yet (no EDL/Cut with it), so "
                "none was recorded on the camera.")
    length = end - start + 1
    if edit.get("cutDuration") and edit["cutDuration"] != length:
        return ("The timeline is %d frames (%d-%d) but the shot is %d frames in the edit "
                "(%s). Check the frame range." % (length, start, end, edit["cutDuration"],
                                                  edit.get("cut") or "ShotGrid shot fields"))
    return None


def camera_stamp(plan, scene_path, planes=(), start=None, end=None):
    """The pipe stamp for a published camera, on its <shot>_cam_GRP like the
    model publish's group (spec item 6a). Records which stage published it
    (user, 2026-10-19: a camera published from Animation must say so), the
    image sequences the camera uses, the baked frame range and the shot's
    range in the latest edit on ShotGrid (2026-10-20)."""
    from datetime import datetime
    edit = plan.get("edit_range") or {"source": EDIT_NONE, "cut": ""}
    frames = [("frameStart", int(start)), ("frameEnd", int(end))] if start is not None else []
    edit_stamp = [("editSource", edit["source"]), ("editCut", edit.get("cut") or "")]
    edit_stamp += [("edit" + k[0].upper() + k[1:], edit[k])
                   for k in ("cutId", "cutDate") if k in edit]
    edit_stamp += [(name, edit[name]) for name, _ in SHOT_EDIT_FIELDS if name in edit]
    return [
        ("sgShotId", (plan.get("sg_shot") or {}).get("id") or 0),
        ("shot", plan["shot"]),
        ("department", CAM_CODE),
        ("version", plan["version"]),
        ("publishedFrom", plan.get("publish_for") or "layout"),
        ("artistId", plan["login"]),
        ("artistName", api.artist_name(plan["login"])),
        ("published", datetime.now().isoformat(timespec="seconds")),
        ("sourceScene", os.path.normpath(scene_path)),
        ("imagePlanes", json.dumps(list(planes))),
    ] + frames + edit_stamp


def _lock_transform(node):
    for attr in TRANSFORM_ATTRS + SCALE_ATTRS + ("visibility",):
        cmds.setAttr("%s.%s" % (node, attr), lock=True)


def export_camera(camera, plan, start, end, scene_path):
    """Bake, then write the keys file + map and the camera group file to the
    H drive. Nothing it makes is left in the open scene. Returns warnings."""
    for key in ("dest", "keys_dest", "map_dest"):
        if os.path.exists(plan[key]):
            raise PublishError("%s already exists — try again." % plan[key])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])

    selection = cmds.ls(selection=True)
    current = cmds.currentTime(query=True)
    group_name = camera_group_name(plan["shot"])
    # Publishing from a built shot: its own group has the name the
    # published one needs, so step it aside until the export is done.
    aside = None
    if cmds.objExists("|" + group_name):
        uuid = cmds.ls(camera, uuid=True)[0]     # its path changes with the group's name
        aside = cmds.rename("|" + group_name, group_name + "_publishing")
        camera = cmds.ls(uuid, long=True)[0]
    made = []
    try:
        planes = image_plane_info(camera)
        pub_tr, pub_sh, curves, warnings = bake_camera(camera, start, end)
        made = [pub_tr] + list(curves)
        data, curve_attrs, attrs = make_data_node(pub_tr, pub_sh, curves)
        made = [pub_tr, data] + list(curve_attrs)
        _export(list(curve_attrs), plan["keys_dest"])
        mapping = {
            "format": MAP_FORMAT,
            "group": group_name,
            "camera": PUBLISHED_CAMERA,
            "data": PUBLISHED_CAMERA + DATA_SUFFIX,
            "shot": plan["shot"],
            "login": plan["login"],
            "version": plan["version"],
            "start": start,
            "end": end,
            "fps": api._scene_fps(),
            "source_scene": os.path.basename(scene_path),
            "source_camera": cmds.ls(camera)[0],
            "published_from": plan.get("publish_for") or "layout",
            "curves": curve_attrs,          # curve -> data node attribute
            "attrs": attrs,                 # data node attribute -> [where, camera attribute]
            "image_planes": planes,
        }
        with open(plan["map_dest"], "w") as f:
            json.dump(mapping, f, indent=2, sort_keys=True)
        api._lock(plan["map_dest"])
        cmds.delete(list(curve_attrs))  # the camera file carries no keys
        group = api.make_pipe_group(group_name)
        made = [group, pub_tr, data]
        pub_tr = cmds.parent(pub_tr, group)[0]
        data = cmds.parent(data, group)[0]
        made = [group]
        for node in (pub_tr, data):
            _lock_transform(node)
        api.finish_pipe_group(group)    # icon, locked at the origin, channels hidden
        api._stamp(group, camera_stamp(plan, scene_path, planes, start, end))
        _export([group], plan["dest"])
    finally:
        existing = [n for n in made if cmds.objExists(n)]
        if existing:
            cmds.delete(existing)
        if aside and cmds.objExists(aside):
            cmds.rename(aside, group_name)
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

def publish_camera(scene_path, h_root, scratch_root, camera, frame_count=None, notes="",
                   publish_for="layout", review=None):
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
    plan["publish_for"] = publish_for       # which stage, stamped on the camera
    plan["sg_shot"] = find_shotgrid_shot(plan, h_root)
    # Not blocked by approval (changed 2026-10-19); the Version goes on the
    # task of the stage it was published from.
    plan["sg_task"] = api.task_on(plan["sg_shot"],
                                  "Layout" if publish_for == "layout" else "Final")
    api.check_rv()
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    try:
        plan["edit_range"] = shot_edit_range(api._shotgrid().get_connection(), plan["sg_shot"])
    except Exception as e:      # the range is a record, not a reason to stop
        plan["edit_range"] = {"source": EDIT_NONE, "cut": "", "error": str(e)}
    edit_warning = edit_range_warning(plan["edit_range"], start, end)
    plan["frames_folder"], files = api.playblast_frames(plan, frame_count, camera=camera)
    # Sound in the movie, for lip sync (same as shotSub).
    plan["audio"], audio_offset = api.scene_audio(start)
    api.review_before_publish(plan, review, plan["shot_project"], plan["audio"], audio_offset)

    try:
        plan["warnings"] = export_camera(camera, plan, start, end, scene_path)
        if edit_warning:
            plan["warnings"] = list(plan["warnings"] or []) + [edit_warning]
    except Exception:
        # Nothing was published: don't leave this attempt's frames on scratch.
        api.remove_frames(plan["frames_folder"], plan["shot_project"])
        raise

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
    try:
        plan["sg_version"] = api.upload_with_audio(
            api._shotgrid(), plan, plan["audio"], audio_offset,
            "Shot", plan["sg_shot"]["id"], plan["frames_folder"],
            files=files, notes=note, fps=api._scene_fps(), rvio_path=rvio,
            machine_diagnostic=plan["movie_warning"])
    except Exception as e:     # files already on the H drive; report, don't lose them
        plan["sg_error"] = str(e)
    else:
        api.link_version_to_task(plan, plan["sg_task"])
        if not api.note_no_movie(plan):
            api.remove_frames(plan["frames_folder"], plan["shot_project"])
    return plan

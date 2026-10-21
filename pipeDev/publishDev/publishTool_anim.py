"""
Publish Tool — shot animation publish (v0)
Publishes the animation in a shot scene on scratch, after the shot has been
approved in ShotGrid through shotSub review. No UI, so it can be tested
under mayapy.

Design: pipeDev/filmPipeline_spec.md §4 "Shot (animation) publish v0" and
item 6a (all DECIDED 2026-10-15 / 2026-10-19):
- The animator selects objects and adds them; Publish works out what each
  is. A published asset carries the pipe stamp on its group
  (<asset>_<dept>_GRP, pipe_sgAssetId...); no stamp = made in the shot.
- Nothing is blocked by approval (changed 2026-10-19): every Layout or
  Animation publish writes keys + the full file and makes a ShotGrid
  Version for review; students ask for approval in the notes. Once a
  Version on the shot's Final task is Approved, the next Animation publish
  also makes an Alembic cache per item (animated: whole timeline; static:
  one frame). The newest final is the true source. Layout never caches.
- One version number per publish, shared by everything in it.

    H drive  <film>\\maya\\sequences\\EAP_010\\EAP_010_010\\scenes\\scout\\
                 EAP_010_010_scout_anim_v001.ma           the full file
                 EAP_010_010_scout_backpack_anim_v001.ma  keys, per item
                 EAP_010_010_scout_backpack_anim_v001.json   + the map
             <film>\\maya\\sequences\\EAP_010\\EAP_010_010\\cache\\alembic\\
                 EAP_010_010_backpack_anim_v001.abc       final only
    scratch  <film>\\premiere\\shotgridMovs\\EAP_010_010.mp4  (replaced each time)

Not in v0 (spec item 7): Build pulling animation back in, the camera
fingerprint, USD, final-publish checkboxes, renaming items. Keys are the
animator's own time-based curves (not baked); constraints, expressions and
driven keys aren't carried in the keys file.
"""

import os
import re
import json
import glob
import shutil
import stat

import maya.cmds as cmds

import publishTool_api as api
import publishTool_camera as cam
from publishTool_api import PublishError

ANIM_CODE = "anim"
ANIM_LABEL = "Animation"
LAYOUT_CODE = "layout"
BLOCKING, FINAL, LAYOUT = "blocking", "final", "layout"
ANIMATION = "animation"              # an Animation publish before any Final approval
# What a shot publish is for: the stage dropdown (user, 2026-10-19). Layout
# publishes the same as animation, approved on the Layout task, never with
# caches. Lighting and FX come later. (label, code, live)
PUBLISH_FOR = [("Layout", LAYOUT_CODE, True), ("Animation", ANIM_CODE, True),
               ("Lighting", "lighting", False), ("FX", "fx", False)]
PUBLISH_FOR_LABELS = dict((c, l) for l, c, _ in PUBLISH_FOR)
SHOT_CAMERA = "camera1"              # Build always makes the shot camera camera1
TIME_CURVES = ("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT")


# ---------------------------------------------------------------------------
# What is each selected thing?
# ---------------------------------------------------------------------------

def stamped_root(node):
    """The pipe group (a published asset's <asset>_<dept>_GRP) node sits in,
    or None."""
    path = (cmds.ls(node, long=True) or [""])[0]
    parts = path.split("|")
    for i in range(len(parts), 1, -1):
        candidate = "|".join(parts[:i])
        if api.is_pipe_group(candidate):
            return candidate
    return None


def _clean(name):
    return re.sub(r"[^A-Za-z0-9]", "", name) or "item"


def _stamp(root):
    info = {}
    for attr in cmds.listAttr(root, userDefined=True) or []:
        if attr.startswith(api.PIPE_ATTR_PREFIX):
            info[attr[len(api.PIPE_ATTR_PREFIX):]] = cmds.getAttr("%s.%s" % (root, attr))
    return info


def _namespace(node):
    short = node.split("|")[-1]
    return short.rsplit(":", 1)[0].lstrip(":") if ":" in short else ""


def time_curves(nodes):
    """{curve: (node, attr)} for the animator's keys on nodes (time-based
    curves straight into an attribute; driven keys belong to the rig)."""
    found = {}
    for node in nodes:
        pairs = cmds.listConnections(node, source=True, destination=False, connections=True,
                                     plugs=True, skipConversionNodes=True) or []
        for i in range(0, len(pairs), 2):
            curve = pairs[i + 1].split(".")[0]
            if cmds.nodeType(curve) in TIME_CURVES:
                found[curve] = (node, pairs[i].split(".", 1)[1])
    return found


# Lights made in the shot (user, 2026-10-20: "publish lights as part of the
# animation publish process if necessary ... sometimes when it's important
# for shot composition"). Each is written as its own small .ma (the light,
# its settings and keys) for lighting to bring in; never cached, since an
# Alembic can't carry a light.
LIGHT_KIND = "light"
GEOMETRY_TYPES = ("mesh", "nurbsSurface", "nurbsCurve", "subdiv")


def _is_light_shape(shape):
    if cmds.ls(shape, type="light"):        # Maya's own lights
        return True
    # Plug-in lights (Arnold's aiAreaLight, aiSkyDomeLight...) say so in
    # their classification.
    return any(part == "light" for c in cmds.getClassification(cmds.nodeType(shape)) or []
               for part in re.split(r"[/:]", c))


def is_light_item(nodes):
    """True if nodes hold lights (Maya's or Arnold's) and no geometry."""
    shapes = cmds.ls(nodes, shapes=True, long=True) or []
    return (any(_is_light_shape(s) for s in shapes)
            and not cmds.ls(shapes, type=GEOMETRY_TYPES))


def classify(objects):
    """[item] for the selected objects, one per thing being published:
    {"name", "kind", "root", "nodes", "stamp", "animated", "label"}.
    kind is the published department ("model", "rig", ...) or "shot" for
    something made in the shot. Raises PublishError for what can't go in an
    Animation publish."""
    if not objects:
        raise PublishError("Select what you animated in Maya (characters, props, ...), "
                           "then Add to List.")
    missing = [o for o in objects if not cmds.objExists(o)]
    if missing:
        raise PublishError("Not in the scene any more: %s" % ", ".join(missing))
    cameras = cam.contains_camera(objects) + [c for c in (cam.camera_in_group(o) for o in objects) if c]
    if cameras:
        raise PublishError("Cameras go in their own Camera row, not Animation: %s"
                           % ", ".join(cameras))
    items, roots = [], set()
    for obj in cmds.ls(objects, long=True) or []:
        root = stamped_root(obj)
        if root:
            stamp = _stamp(root)
            kind = stamp.get("department", "?")
            name = _namespace(root) or stamp.get("asset", "item")
        else:
            if cmds.referenceQuery(obj, isNodeReferenced=True):
                ref = cmds.referenceQuery(obj, filename=True, withoutCopyNumber=True)
                raise PublishError(
                    "%s comes from %s, which was published before the pipe stamp, so "
                    "Publish can't tell which asset it is.\nUse Build to update it to "
                    "the latest version, then publish again." % (obj.split("|")[-1],
                                                                  os.path.basename(ref)))
            # Made in the shot: the top-most selected object is the item.
            root, stamp, kind = obj, {}, "shot"
            name = obj.split("|")[-1].split(":")[-1]
        if root in roots or any(root.startswith(r + "|") for r in roots):
            continue
        roots.add(root)
        nodes = [root] + (cmds.listRelatives(root, allDescendents=True, fullPath=True) or [])
        if kind == "shot" and is_light_item(nodes):
            kind = LIGHT_KIND
        animated = bool(time_curves(nodes))
        items.append({"name": _clean(name), "kind": kind, "root": root, "nodes": nodes,
                      "stamp": stamp, "animated": animated})
    seen = {}
    for item in items:
        if item["name"] in seen:
            raise PublishError("Two items would both be called '%s' (%s and %s). Rename one."
                               % (item["name"], seen[item["name"]], item["root"]))
        seen[item["name"]] = item["root"]
        what = ("made in the shot" if item["kind"] == "shot" else
                "light, made in the shot" if item["kind"] == LIGHT_KIND else
                "%s v%03d" % (item["kind"], item["stamp"].get("version") or 0))
        item["label"] = "%s (%s, %s)" % (item["name"], what,
                                         "keyed" if item["animated"] else "no keys")
    return items


# ---------------------------------------------------------------------------
# Where it goes
# ---------------------------------------------------------------------------

def plan_anim(scene_path, h_root, scratch_root, items=None, publish_for=ANIM_CODE):
    """Work out where a Layout or Animation publish would go, without
    touching anything. Uses the camera publish's shot checks. Each stage
    has its own version series."""
    if publish_for not in (LAYOUT_CODE, ANIM_CODE):
        raise PublishError("%s publishes aren't built yet."
                           % PUBLISH_FOR_LABELS.get(publish_for, publish_for))
    plan = cam.plan_camera(scene_path, h_root, scratch_root)
    shot, login, folder = plan["shot"], plan["login"], plan["h_folder"]
    code = publish_for
    versions = api.published_versions(folder, shot, login, code)
    version = (versions[-1] + 1) if versions else 1
    ext = os.path.splitext(scene_path)[1].lower() or ".ma"
    h_shot = os.path.join(api.resolve_root(h_root), *plan["rel_folder"][:5])
    plan.update({
        "code": code,
        "publish_for": publish_for,
        "version": version,
        "dest": os.path.join(folder, api.published_name(shot, login, code, version, ext)),
        "cache_folder": os.path.join(h_shot, "cache", "alembic"),
    })
    for key in ("keys_dest", "map_dest"):
        plan.pop(key, None)
    plan["item_files"] = {}
    for item in items or []:
        base = "%s_%s_%s_%s_v%03d" % (shot, login, item["name"], code, version)
        plan["item_files"][item["name"]] = {
            "keys": os.path.join(folder, base + ".ma"),
            "map": os.path.join(folder, base + ".json"),
            "cache": os.path.join(plan["cache_folder"], "%s_%s_%s_v%03d.abc"
                                  % (shot, item["name"], code, version)),
        }
        if item["kind"] == LIGHT_KIND:
            plan["item_files"][item["name"]]["light"] = os.path.join(folder, base + "_light.ma")
    return plan


def publish_stage(sg_shot, publish_for=ANIM_CODE):
    """(stage, the Task its ShotGrid Version goes on). Nothing is blocked
    (user, 2026-10-19: iterative publishes must populate the pipe; students
    ask for approval in the publish notes, e.g. "please approve for
    lighting"). Only caches wait for approval:
      Layout     -> ("layout", Layout task), never caches;
      Animation  -> ("final", Final task) if the shot already has an
                    Approved Version on its Final task: this publish makes
                    the caches; otherwise ("animation", Final task), no
                    caches yet."""
    if publish_for == LAYOUT_CODE:
        return LAYOUT, api.task_on(sg_shot, "Layout")
    approved = api.approved_tasks(sg_shot)
    if FINAL in approved:
        return FINAL, dict(approved[FINAL], content="Final")
    return ANIMATION, api.task_on(sg_shot, "Final")


# ---------------------------------------------------------------------------
# Writing the files
# ---------------------------------------------------------------------------

def _writable_remove(path):
    if os.path.exists(path):
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def export_keys(item, files, plan, start, end, scene_path):
    """The item's keys (copies of its time curves) + a map of which curve
    drives which node.attr, names without namespaces, so the keys can be put
    back on the same asset by name."""
    curves = time_curves(item["nodes"])
    namespace = _namespace(item["root"])
    copies, mapping = [], {}
    try:
        for curve, (node, attr) in sorted(curves.items()):
            node_name = node.split("|")[-1].split(":")[-1]
            copy = cmds.duplicate(curve, name="%s__%s_%s" % (item["name"], node_name, attr))[0]
            copies.append(copy)
            mapping[copy] = [node_name, attr]
        cmds.select(copies, replace=True)
        cmds.file(files["keys"], exportSelected=True, type="mayaAscii", force=True,
                  constructionHistory=False, channels=False, constraints=False,
                  expressions=False, shader=False, preserveReferences=False)
    finally:
        existing = [c for c in copies if cmds.objExists(c)]
        if existing:
            cmds.delete(existing)
    api._lock(files["keys"])
    info = {
        "item": item["name"],
        "kind": item["kind"],
        "asset": item["stamp"],
        "namespace": namespace,
        "shot": plan["shot"],
        "login": plan["login"],
        "version": plan["version"],
        "stage": plan["stage"],
        "start": start,
        "end": end,
        "fps": api._scene_fps(),
        "source_scene": os.path.basename(scene_path),
        "curves": mapping,
    }
    with open(files["map"], "w") as f:
        json.dump(info, f, indent=2, sort_keys=True)
    api._lock(files["map"])


def cache_roots(item):
    """What an item's Alembic holds: a rig's cache_SET members (spec
    "cache_SET"), otherwise the whole item."""
    if item["kind"] == api.RIG_CODE:
        namespace = _namespace(item["root"])
        cache_set = ("%s:%s" % (namespace, api.CACHE_SET)) if namespace else api.CACHE_SET
        if cmds.objExists(cache_set):
            # Shapes and components count as their transforms (the rig
            # publish accepts meshes put straight in the set).
            members = api.cache_transforms(cmds.sets(cache_set, query=True) or [])
            if members:
                return [m for m in members if m not in api.nested_in(members)]
    return [item["root"]]


def export_cache(item, path, start, end):
    """Alembic of the item: the whole timeline if it's animated, one frame
    if not (spec item 4: keyframed get the full range, static ones one)."""
    if not cmds.pluginInfo("AbcExport", query=True, loaded=True):
        cmds.loadPlugin("AbcExport", quiet=True)
    last = end if item["animated"] else start
    roots = " ".join("-root %s" % r for r in cache_roots(item))
    job = ("-frameRange %d %d -uvWrite -worldSpace -writeVisibility -dataFormat ogawa "
           "%s -file \"%s\"" % (start, last, roots, path.replace("\\", "/")))
    cmds.AbcExport(jobArg=job)
    api._lock(path)


def export_light(item, path):
    """The light itself: its transform, shape, settings and keys (a group
    of lights: the group and everything in it)."""
    cmds.select(item["root"], replace=True)
    cmds.file(path, exportSelected=True, type="mayaAscii", force=True,
              constructionHistory=True, channels=True, constraints=True,
              expressions=True, shader=False, preserveReferences=False)
    api._lock(path)


def write_anim(items, plan, start, end, scene_path):
    """Everything for the H drive, all or nothing: if any file fails, the
    ones already written are removed again. Returns the files written."""
    targets = [plan["dest"]]
    for item in items:
        files = plan["item_files"][item["name"]]
        if item["animated"]:
            targets += [files["keys"], files["map"]]
        if item["kind"] == LIGHT_KIND:
            targets.append(files["light"])
        elif plan["stage"] == FINAL:
            targets.append(files["cache"])
    for path in targets:
        if os.path.exists(path):
            raise PublishError("%s already exists — try again." % path)
    for folder in set(os.path.dirname(p) for p in targets):
        if not os.path.isdir(folder):
            os.makedirs(folder)

    written = []
    selection = cmds.ls(selection=True)
    current = cmds.currentTime(query=True)
    try:
        shutil.copy2(scene_path, plan["dest"])          # the full file, as saved
        written.append(plan["dest"])
        api._lock(plan["dest"])
        for item in items:
            files = plan["item_files"][item["name"]]
            if item["animated"]:
                export_keys(item, files, plan, start, end, scene_path)
                written += [files["keys"], files["map"]]
            if item["kind"] == LIGHT_KIND:
                export_light(item, files["light"])
                written.append(files["light"])
            elif plan["stage"] == FINAL:
                export_cache(item, files["cache"], start, end)
                written.append(files["cache"])
    except Exception:
        for path in written:
            _writable_remove(path)
        raise
    finally:
        cmds.currentTime(current)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return written


def copy_movie_for_edit(plan):
    """The shot's latest movie in scratch premiere\\shotgridMovs\\<SHOT>.mp4,
    replaced each publish (spec item 6). Returns the path, or None if there
    was no movie."""
    movies = sorted(glob.glob(os.path.join(plan["frames_folder"], "*.mp4")))
    if not movies:
        return None
    folder = os.path.join(plan["root"], plan["film"], "premiere", "shotgridMovs")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    dest = os.path.join(folder, plan["shot"] + ".mp4")
    _writable_remove(dest)
    shutil.copy2(movies[-1], dest)
    return dest


# ---------------------------------------------------------------------------
# One-click animation publish
# ---------------------------------------------------------------------------

def publish_anim(scene_path, h_root, scratch_root, objects, notes="", publish_for=ANIM_CODE,
                 review=None):
    """Approval check -> playblast through the shot camera -> keys, full
    file (and caches if Final) to the H drive -> ShotGrid Version on the
    Shot, linked to its task -> movie copy for the edit.

    Everything that can refuse (what's selected, approval, RV) happens
    before the playblast and any H-drive write."""
    h_root = api.resolve_root(h_root)
    api.check_script_nodes()
    items = classify(objects)
    plan = plan_anim(scene_path, h_root, scratch_root, items, publish_for)
    plan["items"] = items
    plan["objects"] = [i["root"] for i in items]
    plan["sg_shot"] = cam.find_shotgrid_shot(plan, h_root)
    plan["stage"], plan["sg_task"] = publish_stage(plan["sg_shot"], publish_for)
    api.check_rv()
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    camera = SHOT_CAMERA if cam.camera_transform(SHOT_CAMERA) else None
    plan["frames_folder"], files = api.playblast_frames(plan, None, camera=camera)
    plan["audio"], audio_offset = api.scene_audio(start)
    api.review_before_publish(plan, review, plan["shot_project"], plan["audio"], audio_offset)

    try:
        plan["written"] = write_anim(items, plan, start, end, scene_path)
    except Exception:
        api.remove_frames(plan["frames_folder"], plan["shot_project"])
        raise

    lines = ["%s publish v%03d%s: %s" % (
        PUBLISH_FOR_LABELS[publish_for], plan["version"],
        " (Final approved: caches made)" if plan["stage"] == FINAL else "",
        ", ".join(i["label"] for i in items))]
    lines += plan["written"]
    note = "\n".join(lines)
    if notes.strip():
        note = notes.strip() + "\n\n---\n" + note
    plan["sg_version"] = plan["sg_error"] = plan["movie_copy"] = None
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
        try:
            plan["movie_copy"] = copy_movie_for_edit(plan)
        except Exception as e:
            plan.setdefault("warnings", []).append(
                "The movie wasn't copied to premiere\\shotgridMovs: %s" % e)
        if not api.note_no_movie(plan):
            api.remove_frames(plan["frames_folder"], plan["shot_project"])
    return plan

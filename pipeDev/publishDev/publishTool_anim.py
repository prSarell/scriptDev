"""
Publish Tool — shot animation publish (v0)
Publishes the animation in a shot scene on scratch. No UI, so it can be
tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §4 "Shot (animation) publish v0" and
item 6a (all DECIDED 2026-10-15 / 2026-10-19):
- The animator selects objects and adds them; Publish works out what each
  is. A published asset carries the pipe stamp on its group
  (<asset>_<dept>_GRP, pipe_sgAssetId...); no stamp = made in the shot.
- Nothing is blocked by approval (changed 2026-10-19): every Layout or
  Animation publish writes keys + the full file and makes a ShotGrid
  Version for review; students ask for approval in the notes.
- Caches are a tick, not an approval (user, 2026-11-24: tying them to the
  shot's Final approval in ShotGrid "over complicated this"). An Animation
  row's ABC, USD and FBX ticks make an Alembic, USD and/or FBX cache per
  item (animated: whole timeline; static: one frame). FBX (user,
  2026-11-25) carries the skeleton and skin, joints baked, for other
  software. A publish with caches is
  a Final publish (green thumbnail, Final task). Layout never caches.
- One version number per publish, shared by everything in it.

    H drive  <film>\\maya\\sequences\\EAP_010\\EAP_010_010\\scenes\\anim\\scout\\
                 EAP_010_010_scout_anim_v001.ma           the full file
                 EAP_010_010_scout_backpack_anim_v001.ma  keys, per item
                 EAP_010_010_scout_backpack_anim_v001.json   + the map
             (a Layout publish: scenes\\layout\\scout\\; spec §4g)
             <film>\\maya\\sequences\\EAP_010\\EAP_010_010\\cache\\alembic\\anim\\scout\\
                 EAP_010_010_backpack_anim_v001.abc       ABC ticked, per person
                 EAP_010_010_backpack_anim_v001.json      what it is, for Build
             (USD ticked: the same in cache\\usd\\anim\\scout\\, .usd + .json;
              FBX ticked: cache\\fbx\\anim\\scout\\, .fbx + .json)
    scratch  <film>\\premiere\\shotgridMovs\\EAP_010_010.mp4  (replaced each time)

Not in v0 (spec item 7): Build pulling animation back in, the camera
fingerprint, renaming items. Keys are the
animator's own time-based curves (not baked); constraints, expressions and
driven keys aren't carried in the keys file. Settings with no keys (a
master control placed, a space switch) go in the map, for every published
asset, keyed or not (2026-10-28).
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
ANIMATION = "animation"              # an Animation publish without caches
# The cache formats an Animation row can tick (user, 2026-11-24; FBX
# 2026-11-25), in the order the publish list shows them
# (publishTool_outputs.FORMATS keys).
CACHE_FORMATS = ("abc", "usd", "fbx")
CACHE_EXT = {"abc": ".abc", "usd": ".usd", "fbx": ".fbx"}
CACHE_FOLDER = {"abc": "alembic", "usd": "usd", "fbx": "fbx"}
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


# Animation layers (user, 2026-10-28, option 1): a channel on a layer is
# driven through Maya's layer blend nodes, not a curve, so time_curves
# misses it (SEQ010_140 lost Scout's clavicles and FK arms). Publish bakes
# the layered result to one curve per channel, a key every frame; the
# animator's scene keeps its layers.

TRANSFORM_CHANNELS = ("translate", "rotate", "scale", "visibility", "offsetParentMatrix") + tuple(
    a + x for a in ("translate", "rotate", "scale") for x in "XYZ")
CONSTRAINTS = ("constraint", "pairBlend", "motionPath", "expression")


def driven(nodes):
    """True if something other than its own keys moves a transform in
    nodes: a constraint (a walking stick on the hand), an expression, a
    connection from outside (2026-11-25: SEQ010_120's walking stick and
    power pack cached as one frame)."""
    inside = set(cmds.ls(nodes, uuid=True) or [])
    if cmds.ls(nodes, type=CONSTRAINTS):
        return True
    for node in cmds.ls(nodes, type="transform", long=True) or []:
        plugs = ["%s.%s" % (node, a) for a in TRANSFORM_CHANNELS]
        for src in cmds.listConnections(plugs, source=True, destination=False,
                                        skipConversionNodes=True) or []:
            if cmds.nodeType(src) in TIME_CURVES:
                continue            # keys: counted as animated already
            if cmds.ls(src, type=CONSTRAINTS) or not set(cmds.ls(src, uuid=True)) & inside:
                return True
    return False


def moves(item):
    """Whether an item's caches take the whole timeline: keyed, or (not a
    rig, whose own constraints always look driven) driven by something."""
    return item["animated"] or item.get("driven", False)


def layered_plugs(nodes):
    """[(node, attr)] for the channels on nodes driven by an animation
    layer, attr a single channel (rotateX, not rotate)."""
    found = []
    for node in nodes:
        pairs = cmds.listConnections(node, source=True, destination=False, connections=True,
                                     plugs=True, skipConversionNodes=True) or []
        for i in range(0, len(pairs), 2):
            if not cmds.nodeType(pairs[i + 1].split(".")[0]).startswith("animBlendNode"):
                continue
            attr = pairs[i].split(".", 1)[1]
            children = cmds.attributeQuery(attr, node=node, listChildren=True) \
                if cmds.attributeQuery(attr, node=node, exists=True) else None
            found += [(node, c) for c in children] if children else [(node, attr)]
    return found


_CURVE_TYPES = {"doubleAngle": "animCurveTA", "doubleLinear": "animCurveTL", "time": "animCurveTT"}


def bake_layered(plugs, start, end, prefix, curves):
    """Bake each layered channel to a plain curve, a key on every frame
    from start to end, filling curves {new curve: (node, attr)} as it goes
    (so the caller can clean up after a failure). Steps the timeline (a
    layered channel read at another time can come back wrong); the caller
    puts the current time back."""
    values = dict((p, []) for p in plugs)
    for frame in range(int(start), int(end) + 1):
        cmds.currentTime(frame, update=True)
        for node, attr in plugs:
            values[(node, attr)].append(cmds.getAttr("%s.%s" % (node, attr)))
    for (node, attr), vals in sorted(values.items()):
        kind = cmds.getAttr("%s.%s" % (node, attr), type=True)
        node_name = node.split("|")[-1].split(":")[-1]
        curve = cmds.createNode(_CURVE_TYPES.get(kind, "animCurveTU"),
                                name="%s__%s_%s_baked" % (prefix, node_name, attr), skipSelect=True)
        curves[curve] = (node, attr)    # first, so a failure below still cleans it up
        for frame, value in zip(range(int(start), int(end) + 1), vals):
            cmds.setKeyframe(curve, time=frame, value=float(value))
        if kind in ("bool", "enum", "long", "short", "byte"):
            cmds.keyTangent(curve, outTangentType="step")
    return curves


# Unkeyed settings (user, 2026-10-28: "settings for all controls that are
# not keyed need to be stored so that the pipe can reapply them to a clean
# build"): a master control placed but never keyed, a space switch left on
# world, a held hand pose. Every keyable or channel box setting on the item
# that has no keys and that the animator could set (not locked, nothing
# driving it) goes in the map with its value, whether it was changed or not.

def unkeyed_settings(nodes, curves=None):
    """{node name: {attr: value}} for the settings on nodes that aren't
    keyed. curves: time_curves(nodes), if already worked out. Names are
    without namespaces, like the curves in the map."""
    keyed = set((node.split("|")[-1].split(":")[-1], attr)
                for node, attr in (curves if curves is not None else time_curves(nodes)).values())
    settings = {}
    for node in nodes:
        if cmds.ls(node, intermediateObjects=True):
            continue
        name = node.split("|")[-1].split(":")[-1]
        attrs = set(cmds.listAttr(node, keyable=True, scalar=True) or []) | \
            set(cmds.listAttr(node, channelBox=True, scalar=True) or [])
        for attr in sorted(attrs):
            if (name, attr) in keyed:
                continue
            plug = "%s.%s" % (node, attr)
            try:
                # Driven (a constraint, the rig's driven keys) or locked.
                # A curve-driven plug still says it's settable.
                if (cmds.connectionInfo(plug, isDestination=True)
                        or not cmds.getAttr(plug, settable=True)):
                    continue
                value = cmds.getAttr(plug)
            except (RuntimeError, ValueError):
                continue
            if isinstance(value, (bool, int, float)):
                settings.setdefault(name, {})[attr] = value
    return settings


def carries_settings(item):
    """Published assets get a map even with no keys, so Build can put their
    unkeyed settings back (things made in the shot only live in the full
    file)."""
    return item["kind"] not in ("shot", LIGHT_KIND, STAGE_KIND)


# USD stages Build loaded (spec §4h) can be cached too (user, 2026-11-25:
# "If a student wants it as an alembic cache even though it is a usd they
# should be able to select it and publish it as an ABC and vice versa").
# The stage is copied into Maya geometry for the export (mayaUsdDuplicate,
# following the stage's placement, proxy and guide prims left out), then
# the copy is deleted. Its stamp is the model publish it reads, so Build
# puts that model's look on the cache. No keys file: the stage itself only
# moves by its transform.
STAGE_KIND = "usdStage"
USD_SHAPE = "mayaUsdProxyShape"
USD_KEY_ATTR = "pipe_buildKey"          # buildTool_api.USD_KEY_ATTR
USD_SOURCE_ATTR = "pipe_usdSource"      # buildTool_api.USD_SOURCE_ATTR
STAGE_TEMP_NAMESPACE = "pipeStageCopy"
_PUBLISHED_RE = re.compile(r"^(?P<asset>.+)_(?P<login>[^_]+)_(?P<dept>[^_]+)_v(?P<version>\d{3})"
                           r"\.usd[ac]?$", re.IGNORECASE)


def stage_shapes(obj):
    """The USD stage shapes at or under obj (long names)."""
    if not cmds.pluginInfo("mayaUsdPlugin", query=True, loaded=True):
        return []
    nodes = cmds.ls(obj, long=True) + (cmds.listRelatives(obj, allDescendents=True,
                                                          fullPath=True) or [])
    return cmds.ls(nodes, type=USD_SHAPE, long=True) or []


def stage_stamp(transform):
    """The asset stamp of a Build-loaded stage, from its manifest key and
    the publish it reads ({} for a stage Build didn't make)."""
    def attr(name):
        plug = "%s.%s" % (transform, name)
        return cmds.getAttr(plug) if cmds.objExists(plug) else None
    key, source = attr(USD_KEY_ATTR), attr(USD_SOURCE_ATTR)
    parts = (key or "").split("/")
    m = _PUBLISHED_RE.match(os.path.basename(source or "").replace("\\", "/").split("/")[-1])
    if len(parts) != 3:
        return {}
    stamp = {"assetType": parts[0], "asset": parts[1], "department": parts[2]}
    if m:
        stamp.update(artistId=m.group("login"), version=int(m.group("version")))
    return stamp


class _StageAsMaya(object):
    """For the length of a cache export: the item's stage as Maya geometry
    in a temporary group that follows the stage's transform. cache_roots()
    gives the copy's top nodes meanwhile."""

    def __init__(self, item):
        self.item, self.group = item, None

    def __enter__(self):
        if self.item["kind"] != STAGE_KIND:
            return self
        import mayaUsd.ufe
        from pxr import UsdGeom
        shape, transform = self.item["shape"], self.item["root"]
        stage = mayaUsd.ufe.getStage(shape)
        if not cmds.namespace(exists=":" + STAGE_TEMP_NAMESPACE):
            cmds.namespace(add=STAGE_TEMP_NAMESPACE)
        self.group = cmds.group(empty=True, world=True,
                                name="%s:%s_copy" % (STAGE_TEMP_NAMESPACE, self.item["name"]))
        self.group = cmds.ls(self.group, long=True)[0]
        cmds.parentConstraint(transform, self.group)
        cmds.scaleConstraint(transform, self.group)
        current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + STAGE_TEMP_NAMESPACE)
        try:
            for prim in stage.GetPseudoRoot().GetChildren():
                if prim.IsActive() and prim.IsDefined():
                    cmds.mayaUsdDuplicate(shape + "," + prim.GetPath().pathString, self.group)
        finally:
            cmds.namespace(setNamespace=current)
        # Proxy and guide prims stay out: only what renders is cached.
        by_path = {}
        for node in cmds.listRelatives(self.group, allDescendents=True, fullPath=True,
                                       type="transform") or []:
            rel = node[len(self.group):].split("|")
            by_path["/".join(p.split(":")[-1] for p in rel)] = node
        doomed = []
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Imageable) and UsdGeom.Imageable(prim).ComputePurpose() in (
                    UsdGeom.Tokens.proxy, UsdGeom.Tokens.guide):
                node = by_path.get(prim.GetPath().pathString)
                if node and not any(node.startswith(d + "|") for d in doomed):
                    doomed.append(node)
        for node in doomed:
            if cmds.objExists(node):
                cmds.delete(node)
        children = cmds.listRelatives(self.group, children=True, fullPath=True,
                                      type="transform") or []
        self.item["_temp_roots"] = [c for c in children if not cmds.ls(c, type="constraint")]
        return self

    def __exit__(self, *exc):
        self.item.pop("_temp_roots", None)
        if self.group and cmds.objExists(self.group):
            cmds.delete(self.group)
        if cmds.namespace(exists=":" + STAGE_TEMP_NAMESPACE):
            cmds.namespace(removeNamespace=":" + STAGE_TEMP_NAMESPACE,
                           deleteNamespaceContent=True)
        return False


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
    # USD stages (Build's, spec §4h): cached through a Maya copy, see
    # STAGE_KIND. Their keys stay in the full scene file.
    rest = []
    for obj in cmds.ls(objects, long=True) or []:
        shapes = stage_shapes(obj)
        if not shapes:
            rest.append(obj)
            continue
        for shape in shapes:
            root = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
            if root in roots:
                continue
            roots.add(root)
            stamp = stage_stamp(root)
            name = stamp.get("asset") or root.split("|")[-1].split(":")[-1]
            moved = bool(time_curves([root])) or bool(layered_plugs([root])) or driven([root])
            items.append({"name": _clean(name), "kind": STAGE_KIND, "root": root,
                          "shape": shape, "nodes": [root, shape], "stamp": stamp,
                          "animated": False, "driven": moved})
    for obj in rest:
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
        animated = bool(time_curves(nodes)) or bool(layered_plugs(nodes))
        items.append({"name": _clean(name), "kind": kind, "root": root, "nodes": nodes,
                      "stamp": stamp, "animated": animated,
                      "driven": kind != api.RIG_CODE and not animated and driven(nodes)})
    seen = {}
    for item in items:
        if item["name"] in seen:
            raise PublishError("Two items would both be called '%s' (%s and %s). Rename one."
                               % (item["name"], seen[item["name"]], item["root"]))
        seen[item["name"]] = item["root"]
        what = ("made in the shot" if item["kind"] == "shot" else
                "light, made in the shot" if item["kind"] == LIGHT_KIND else
                "USD stage, %s v%03d" % (item["stamp"].get("department", "?"),
                                         item["stamp"].get("version") or 0)
                if item["kind"] == STAGE_KIND else
                "%s v%03d" % (item["kind"], item["stamp"].get("version") or 0))
        item["label"] = "%s (%s, %s)" % (item["name"], what,
                                         "keyed" if item["animated"] else
                                         "constrained" if item["driven"] else "no keys")
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
    shot, login = plan["shot"], plan["login"]
    code = publish_for
    # The person's folder for the stage published: scenes\layout\<login>\ or
    # scenes\anim\<login>\ (spec §4g), versions counted across the old
    # scenes\<login>\ too.
    project = plan["rel_folder"][:5]
    folder = api.personal_folder(api.resolve_root(h_root), project, login, code)
    versions = api.person_versions(api.resolve_root(h_root), project, shot, login, code)
    version = (versions[-1] + 1) if versions else 1
    ext = os.path.splitext(scene_path)[1].lower() or ".ma"
    h_shot = os.path.join(api.resolve_root(h_root), *project)
    plan.update({
        "code": code,
        "publish_for": publish_for,
        "department": code,
        "h_folder": folder,
        "version": version,
        "dest": os.path.join(folder, api.published_name(shot, login, code, version, ext)),
        # per person, like the publishes: versions are per person, so two
        # people's v003 caches can't collide; per department (spec §4g)
        "cache_folder": os.path.join(h_shot, "cache", "alembic", code, login),
        "cache_folders": dict((fmt, os.path.join(h_shot, "cache", CACHE_FOLDER[fmt], code, login))
                              for fmt in CACHE_FORMATS),
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
            # What the cache is, for Build (spec "Shaders on caches"): the
            # asset version it came from, so its look can be found.
            "cache_info": os.path.join(plan["cache_folder"], "%s_%s_%s_v%03d.json"
                                       % (shot, item["name"], code, version)),
        }
        for fmt in CACHE_FORMATS:       # {fmt: (cache, its .json)}
            cache_base = os.path.join(plan["cache_folders"][fmt], "%s_%s_%s_v%03d"
                                % (shot, item["name"], code, version))
            plan["item_files"][item["name"]].setdefault("caches", {})[fmt] = (
                cache_base + CACHE_EXT[fmt], cache_base + ".json")
        if item["kind"] == LIGHT_KIND:
            plan["item_files"][item["name"]]["light"] = os.path.join(folder, base + "_light.ma")
    return plan


def cache_formats(publish_for, caches):
    """The cache formats this publish makes: what's ticked, Animation only."""
    if publish_for != ANIM_CODE:
        return []
    return [fmt for fmt in CACHE_FORMATS if fmt in (caches or ())]


def publish_stage(sg_shot, publish_for=ANIM_CODE, caches=()):
    """(stage, the Task its ShotGrid Version goes on). Nothing is blocked
    (user, 2026-10-19: iterative publishes must populate the pipe; students
    ask for approval in the publish notes). Caches are the student's tick
    (user, 2026-11-24), not a ShotGrid approval:
      Layout     -> ("layout", Layout task), never caches;
      Animation  -> ("final", Final task) with caches ticked, otherwise
                    ("animation", Final task)."""
    if publish_for == LAYOUT_CODE:
        return LAYOUT, api.task_on(sg_shot, "Layout")
    return (FINAL if cache_formats(publish_for, caches) else ANIMATION,
            api.task_on(sg_shot, "Final"))


# ---------------------------------------------------------------------------
# Writing the files
# ---------------------------------------------------------------------------

def _writable_remove(path):
    if os.path.exists(path):
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def export_keys(item, files, plan, start, end, scene_path):
    """The item's keys (copies of its time curves) + a map of which curve
    drives which node.attr and of its unkeyed settings, names without
    namespaces, so both can be put back on the same asset by name. With no
    keys only the map is written. Returns the number of settings."""
    curves = time_curves(item["nodes"])
    settings = unkeyed_settings(item["nodes"], curves)
    layered = layered_plugs(item["nodes"])
    namespace = _namespace(item["root"])
    copies, mapping = [], {}
    item["baked"] = sorted(set(n.split("|")[-1].split(":")[-1] for n, _ in layered))
    if curves or layered:
        try:
            for curve, (node, attr) in sorted(curves.items()):
                node_name = node.split("|")[-1].split(":")[-1]
                copy = cmds.duplicate(curve, name="%s__%s_%s" % (item["name"], node_name, attr))[0]
                copies.append(copy)
                mapping[copy] = [node_name, attr]
            if layered:
                baked = {}
                try:
                    bake_layered(layered, start, end, item["name"], baked)
                finally:
                    copies += list(baked)       # deleted below, even after a failure
                for curve, (node, attr) in baked.items():
                    mapping[curve] = [node.split("|")[-1].split(":")[-1], attr]
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
        "settings": settings,
    }
    with open(files["map"], "w") as f:
        json.dump(info, f, indent=2, sort_keys=True)
    api._lock(files["map"])
    return sum(len(attrs) for attrs in settings.values())


def cache_roots(item):
    """What an item's Alembic holds: a rig's cache_SET members (spec
    "cache_SET"), a USD stage's Maya copy (_StageAsMaya), otherwise the
    whole item."""
    if item.get("_temp_roots") is not None:
        return item["_temp_roots"]
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
    last = end if moves(item) else start
    roots = " ".join("-root %s" % r for r in cache_roots(item))
    strip = "-stripNamespaces " if item["kind"] == STAGE_KIND else ""   # the copy's namespace
    job = ("-frameRange %d %d -uvWrite -worldSpace -writeVisibility -dataFormat ogawa %s"
           "%s -file \"%s\"" % (start, last, strip, roots, path.replace("\\", "/")))
    cmds.AbcExport(jobArg=job)
    api._lock(path)


def export_usd_cache(item, path, start, end):
    """USD of the item, like its Alembic: the same roots, the whole
    timeline if animated, one frame if not. Control curves are left out (a
    rig's cache_SET holds geometry anyway); with Arnold loaded its shaders
    go too, for USD-reading renderers (Gaffer, Solaris)."""
    if not cmds.pluginInfo("mayaUsdPlugin", query=True, loaded=True):
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
    last = end if moves(item) else start
    options = dict(file=path.replace("\\", "/"), selection=True, frameRange=(start, last),
                   defaultUSDFormat="usdc", exportUVs=True, exportVisibility=True,
                   filterTypes=["nurbsCurve"])
    if cmds.pluginInfo("mtoa", query=True, loaded=True):
        options["jobContext"] = ["Arnold"]
    if item["kind"] == STAGE_KIND:
        # The copy's own roots in world space: not its temporary group (or
        # the constraints that make it follow the stage), nor its namespace.
        options.update(stripNamespaces=True, worldspace=True,
                       exportRoots=cache_roots(item))
    selection = cmds.ls(selection=True)
    try:
        cmds.select(cache_roots(item), replace=True)
        cmds.mayaUSDExport(**options)
    finally:
        if selection:
            cmds.select(selection, replace=True)
        else:
            cmds.select(clear=True)
    api._lock(path)


def skin_joints(meshes):
    """The top joints of the skeletons skinning these meshes (their
    skinClusters' influences, walked up to the topmost joint), so an FBX
    carries the whole skeleton the skin needs."""
    tops = []
    for mesh in meshes:
        history = cmds.listHistory(mesh, pruneDagObjects=True) or []
        for skin in cmds.ls(history, type="skinCluster"):
            for joint in cmds.skinCluster(skin, query=True, influence=True) or []:
                top = cmds.ls(joint, long=True)[0]
                parent = cmds.listRelatives(top, parent=True, fullPath=True)
                while parent and cmds.nodeType(parent[0]) == "joint":
                    top = parent[0]
                    parent = cmds.listRelatives(top, parent=True, fullPath=True)
                if top not in tops:
                    tops.append(top)
    return tops


def export_fbx_cache(item, path, start, end):
    """FBX of the item (user, 2026-11-25: skeleton + skin): the same roots
    as its Alembic plus the skeletons that skin them, joints and transforms
    baked over the whole timeline if animated, one frame if not. Skin
    weights and blendshapes go with the meshes; other deformers don't (the
    Alembic and USD carry every deformation)."""
    import maya.mel as mel
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        cmds.loadPlugin("fbxmaya", quiet=True)
    last = end if moves(item) else start
    roots = cache_roots(item)
    meshes = cmds.listRelatives(roots, allDescendents=True, type="mesh", fullPath=True) or []
    selection = cmds.ls(selection=True)
    try:
        cmds.select(roots + skin_joints(meshes), replace=True)
        mel.eval("FBXResetExport")
        for command in ("FBXExportSkins -v true", "FBXExportShapes -v true",
                        "FBXExportSmoothingGroups -v true", "FBXExportInputConnections -v false",
                        "FBXExportConstraints -v false", "FBXExportCameras -v false",
                        "FBXExportLights -v false", "FBXExportEmbeddedTextures -v false",
                        "FBXExportAnimationOnly -v false", "FBXExportBakeComplexAnimation -v true",
                        "FBXExportBakeComplexStart -v %d" % start,
                        "FBXExportBakeComplexEnd -v %d" % last,
                        "FBXExportBakeComplexStep -v 1"):
            mel.eval(command)
        mel.eval('FBXExport -f "%s" -s' % path.replace("\\", "/"))
    finally:
        if selection:
            cmds.select(selection, replace=True)
        else:
            cmds.select(clear=True)
    api._lock(path)


# Looked up by name when publishing, so a test can swap one.
CACHE_EXPORTERS = {"abc": "export_cache", "usd": "export_usd_cache",
                   "fbx": "export_fbx_cache"}


def write_cache_info(item, files, plan, start, end, scene_path):
    """The .json beside a cache: which item and asset version it is, and
    its frames. Build lists caches by it (spec "Shaders on caches")."""
    info = {
        "item": item["name"],
        "kind": item["kind"],
        "asset": item["stamp"],
        "shot": plan["shot"],
        "login": plan["login"],
        "version": plan["version"],
        "start": start,
        "end": end if moves(item) else start,
        "fps": api._scene_fps(),
        "source_scene": os.path.basename(scene_path),
        "roots": [r.split("|")[-1].split(":")[-1] for r in cache_roots(item)],
    }
    info["format"] = files.get("format", "abc")
    if files.get("look"):
        info["look"] = files["look"]
    with open(files["cache_info"], "w") as f:
        json.dump(info, f, indent=2, sort_keys=True)
    api._lock(files["cache_info"])


def export_shot_look(item, files, plan):
    """The shaders of something made in the shot, for its caches (user,
    2026-11-25: SEQ010_120's walking stick and power pack came through
    grey): a look like a rig's (publishTool_look) beside its keys file,
    <keys>_look.ma / .json, its textures copied to the shot's
    sourceimages\\<login>\\<keys name>\\. Returns (the look .ma's path
    from the shot folder, e.g. scenes/anim/scout/..._look.ma, or None if
    it only has Maya's default shader; the files written)."""
    import publishTool_look as look
    import publishTool_textures as tex
    look_plan = {"dest": files["keys"], "h_folder": os.path.dirname(files["keys"]),
                 "login": plan["login"], "asset": item["name"], "code": ANIM_CODE,
                 "version": plan["version"], "root": plan.get("root", "")}
    with tex.PublishedTextures(tex.collect([item["root"]]), look_plan):
        paths = look.export_look(look_plan, [item["root"]])
    written = list(paths or [])
    folder = (look_plan.get("textures") or {}).get("folder")
    for dirpath, _, names in os.walk(folder) if folder else ():
        written += [os.path.join(dirpath, n) for n in names]
    if not paths:
        return None, written
    shot_dir = api.project_of_publish(files["keys"])
    return os.path.relpath(paths[0], shot_dir).replace("\\", "/"), written


def export_light(item, path):
    """The light itself: its transform, shape, settings and keys (a group
    of lights: the group and everything in it)."""
    cmds.select(item["root"], replace=True)
    cmds.file(path, exportSelected=True, type="mayaAscii", force=True,
              constructionHistory=True, channels=True, constraints=True,
              expressions=True, shader=False, preserveReferences=False)
    api._lock(path)


class _Nothing(object):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# What the scene had (user, 2026-11-25: "We want to know everything in the
# animation scene is 1:1 in the lighting scene"; passing it "down the pipe
# so they don't have to chase it"): beside the full file,
# <published>_contents.json lists every pipe asset (Maya reference or USD
# stage, which version), everything made in the shot, and what this
# publish wrote for each (keys, caches by format). Build fills the next
# departments' lists from it.
CONTENTS_FORMAT = 1
CONTENTS_SUFFIX = "_contents.json"


def contents_path(plan):
    return os.path.splitext(plan["dest"])[0] + CONTENTS_SUFFIX


def _top_most(nodes):
    nodes = sorted(set(cmds.ls(nodes, long=True) or []))
    return [n for n in nodes if not any(n.startswith(o + "|") for o in nodes if o != n)]


def scene_contents(items, plan):
    """[entry] for the scene: {"name", "kind", "key", "load", "version",
    "login", "node", "published"}. kind: the asset's department, "usdStage"
    or "shot"; load: "maya" (referenced), "imported", "usd" or "shot";
    published: what this publish wrote for it (None if it isn't in it)."""
    shot_dir = api.project_of_publish(plan["dest"])
    rel = lambda p: os.path.relpath(p, shot_dir).replace("\\", "/")
    by_root = dict((item["root"], item) for item in items)
    entries, covered = [], []

    def published(item):
        if item is None:
            return None
        files = plan["item_files"][item["name"]]
        out = {"item": item["name"],
               "caches": dict((fmt, rel(files["caches"][fmt][0]))
                              for fmt in plan.get("caches") or () if item["kind"] != LIGHT_KIND),
               "keys": rel(files["keys"]) if item["animated"] else None}
        if item["kind"] == LIGHT_KIND:
            out["light"] = rel(files["light"])
        return out

    groups = cmds.ls("*." + api.ID_ATTR, objectsOnly=True, recursive=True, long=True) or []
    for group in _top_most(groups):
        if cmds.ls(group, long=True)[0].split("|")[1].startswith(STAGE_TEMP_NAMESPACE + ":"):
            continue
        stamp = _stamp(group)
        covered.append(group)
        entries.append({
            "name": _namespace(group) or stamp.get("asset"), "kind": stamp.get("department"),
            "key": "%s/%s/%s" % (stamp.get("assetType"), stamp.get("asset"),
                                 stamp.get("department")),
            "load": "maya" if cmds.referenceQuery(group, isNodeReferenced=True) else "imported",
            "version": stamp.get("version"), "login": stamp.get("artistId"),
            "node": group.split("|")[-1], "published": published(by_root.get(group))})
    stages = cmds.ls("*." + USD_KEY_ATTR, objectsOnly=True, recursive=True, long=True) or []
    for stage in sorted(set(cmds.ls(stages, long=True))):
        stamp = stage_stamp(stage)
        covered.append(stage)
        entries.append({
            "name": stamp.get("asset"), "kind": STAGE_KIND,
            "key": cmds.getAttr(stage + "." + USD_KEY_ATTR), "load": "usd",
            "version": stamp.get("version"), "login": stamp.get("artistId"),
            "node": stage.split("|")[-1], "source": cmds.getAttr(stage + "." + USD_SOURCE_ATTR)
            if cmds.objExists(stage + "." + USD_SOURCE_ATTR) else None,
            "published": published(by_root.get(stage))})
    # Made in the shot: what this publish took, and any other top-level
    # geometry it didn't (so the next department knows it's missing).
    for item in items:
        if item["root"] not in covered:
            covered.append(item["root"])
            entries.append({"name": item["name"], "kind": item["kind"], "key": None,
                            "load": "shot", "version": None, "login": None,
                            "node": item["root"].split("|")[-1], "published": published(item)})
    for top in cmds.ls(assemblies=True, long=True) or []:
        if any(c == top or c.startswith(top + "|") or top.startswith(c + "|") for c in covered):
            continue
        if top.split("|")[-1].startswith(STAGE_TEMP_NAMESPACE + ":"):
            continue
        if not cmds.listRelatives(top, allDescendents=True, type=GEOMETRY_TYPES):
            continue
        entries.append({"name": _clean(top.split("|")[-1].split(":")[-1]), "kind": "shot",
                        "key": None, "load": "shot", "version": None, "login": None,
                        "node": top.split("|")[-1], "published": None})
    return entries


def write_contents(items, plan, scene_path):
    data = {"format": CONTENTS_FORMAT, "shot": plan["shot"], "department": plan["code"],
            "login": plan["login"], "version": plan["version"],
            "published": os.path.basename(plan["dest"]),
            "source_scene": os.path.basename(scene_path),
            "caches": list(plan.get("caches") or ()),
            "contents": scene_contents(items, plan)}
    path = contents_path(plan)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    api._lock(path)
    return path


def write_anim(items, plan, start, end, scene_path):
    """Everything for the H drive, all or nothing: if any file fails, the
    ones already written are removed again. Returns the files written."""
    targets = [plan["dest"]]
    for item in items:
        files = plan["item_files"][item["name"]]
        if item["animated"]:
            targets += [files["keys"], files["map"]]
        elif carries_settings(item):
            targets.append(files["map"])
        if item["kind"] == LIGHT_KIND:
            targets.append(files["light"])
        else:
            for fmt in plan.get("caches") or ():
                targets += list(files["caches"][fmt])
    targets.append(contents_path(plan))
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
            if item["animated"] or carries_settings(item):
                item["settings"] = export_keys(item, files, plan, start, end, scene_path)
                written += ([files["keys"]] if item["animated"] else []) + [files["map"]]
            if item["kind"] == LIGHT_KIND:
                export_light(item, files["light"])
                written.append(files["light"])
            else:
                shot_look = None
                if item["kind"] == "shot" and plan.get("caches"):
                    shot_look, look_files = export_shot_look(item, files, plan)
                    written += look_files
                with _StageAsMaya(item) if plan.get("caches") else _Nothing():
                    for fmt in plan.get("caches") or ():
                        cache, cache_info = files["caches"][fmt]
                        globals()[CACHE_EXPORTERS[fmt]](item, cache, start, end)
                        written.append(cache)
                        write_cache_info(item, {"cache_info": cache_info, "format": fmt,
                                                "look": shot_look},
                                         plan, start, end, scene_path)
                        written.append(cache_info)
        write_contents(items, plan, scene_path)
        written.append(contents_path(plan))
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
                 review=None, camera=None, caches=(), camera_outputs=()):
    """Playblast through the shot camera -> keys, full file (and the
    ticked caches) to the H drive -> ShotGrid Version on the Shot, linked
    to its task -> movie copy for the edit.

    caches: the cache formats ticked ("abc", "usd"); Animation only. Any
    cache makes it a Final publish (user, 2026-11-24).

    camera: the shot camera, when it's published with the same stage. It
    goes out in this publish (user, 2026-10-28: "We don't need a mov per
    asset in a publish"): the movie is made through it, and its files are
    written with its own camera version (plan["camera_plan"]), but there's
    one movie and one ShotGrid Version for everything. camera_outputs: the
    formats ticked on its row ("abc", "usd", "fbx": for other software).

    Everything that can refuse (what's selected, RV) happens
    before the playblast and any H-drive write."""
    h_root = api.resolve_root(h_root)
    api.check_script_nodes()
    items = classify(objects)
    plan = plan_anim(scene_path, h_root, scratch_root, items, publish_for)
    plan["items"] = items
    plan["objects"] = [i["root"] for i in items]
    plan["sg_shot"] = cam.find_shotgrid_shot(plan, h_root)
    plan["caches"] = cache_formats(publish_for, caches)
    plan["stage"], plan["sg_task"] = publish_stage(plan["sg_shot"], publish_for, plan["caches"])
    # Final = green thumbnail border (user, 2026-10-28). Animation: a
    # publish with caches. Layout: Final when the Layout task's newest
    # Version is Approved, but still never caches.
    plan["final"] = plan["stage"] == FINAL or (
        plan["stage"] == LAYOUT and api.newest_approved(plan["sg_shot"], plan["sg_task"]))
    cam_plan = edit_warning = None
    start = int(cmds.playbackOptions(query=True, minTime=True))
    end = int(cmds.playbackOptions(query=True, maxTime=True))
    if camera:
        camera = cam.check_camera([camera])
        cam_plan = cam.plan_camera(scene_path, h_root, scratch_root, department=publish_for)
        cam_plan["objects"] = [cmds.ls(camera)[0]]
        cam_plan["publish_for"] = publish_for
        cam_plan["sg_shot"] = plan["sg_shot"]
        try:
            cam_plan["edit_range"] = cam.shot_edit_range(api._shotgrid().get_connection(),
                                                         plan["sg_shot"])
        except Exception as e:      # the range is a record, not a reason to stop
            cam_plan["edit_range"] = {"source": cam.EDIT_NONE, "cut": "", "error": str(e)}
        edit_warning = cam.edit_range_warning(cam_plan["edit_range"], start, end)
    plan["camera_plan"] = cam_plan
    api.check_rv()
    if not camera:
        camera = SHOT_CAMERA if cam.camera_transform(SHOT_CAMERA) else None
    plan["frames_folder"], files = api.playblast_frames(plan, None, camera=camera)
    plan["audio"], audio_offset = api.scene_audio(start)
    api.review_before_publish(plan, review, plan["shot_project"], plan["audio"], audio_offset)

    cam_written = []
    try:
        if cam_plan:
            plan["warnings"] = list(cam.export_camera(camera, cam_plan, start, end, scene_path,
                                                      camera_outputs)
                                    or []) + ([edit_warning] if edit_warning else [])
            cam_written = list(cam_plan["written"])
        plan["written"] = cam_written + write_anim(items, plan, start, end, scene_path)
    except Exception:
        for path in cam_written:        # all or nothing, the camera too
            _writable_remove(path)
        api.remove_frames(plan["frames_folder"], plan["shot_project"])
        raise

    lines = ["%s publish v%03d%s: %s" % (
        PUBLISH_FOR_LABELS[publish_for], plan["version"],
        " (Final: %s caches)" % " + ".join(f.upper() for f in plan["caches"])
        if plan["caches"] else "",
        ", ".join(i["label"] for i in items))]
    if cam_plan:
        lines.append("Camera v%03d (%s, keys baked %d-%d)%s" % (
            cam_plan["version"], cam_plan["objects"][0], start, end,
            "".join("\n  " + cam_plan["exports"][f][0]
                    for f in cam.export_formats(camera_outputs))))
    lines += ["%s: %d unkeyed control settings carried" % (i["name"], i["settings"])
              for i in items if i.get("settings")]
    baked = ["%s: on an animation layer, baked every frame: %s" % (i["name"], ", ".join(i["baked"]))
             for i in items if i.get("baked")]
    lines += baked
    plan["warnings"] = list(plan.get("warnings") or []) + baked    # shown in the Publish window
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

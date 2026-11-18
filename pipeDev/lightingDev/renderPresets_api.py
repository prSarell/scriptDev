"""
renderPresets_api.py: save a shot's render settings and lights as a named
preset, and apply it to any other shot (user, 2026-11-17: "similar to the
camera presets tool, however it is a render presets tool ... name and save
different rendering presets for different stages of the project
development").

A preset holds:
    render   every Arnold setting (render options, driver, filter) and
             Maya's render globals and resolution. Not the frame range,
             the image name, or pre/post render scripts: those belong to the
             shot (and a script in a preset would run in every shot it's
             applied to).
    aovs     Arnold's AOVs, with their settings.
    lights   every Maya and Arnold light: its name, type, world-space
             position, its group if it has one, and all of its Maya and
             Arnold settings. What feeds a light (an HDRI on a skydome,
             Arnold light filters such as barndoors and gobos) comes too.

Presets are JSON files, one per name, in the film's renderPresets folder on
scratch (<film>\\maya\\renderPresets\\, next to the show library), so every
shot of the film sees them. Outside a film folder they go in the Maya
project's data\\renderPresets\\, as the camera presets tool does.

Applying makes the scene match: render settings and AOVs are set (AOVs not
in the preset are removed), lights with the preset's names are moved and
set, missing ones are made. Lights in the scene but not in the preset are
the caller's choice (apply(remove_extra=...)). It's one undo.
"""

import os
import re
import json
import getpass
from datetime import datetime

import maya.cmds as cmds

FORMAT = 1
FOLDER = "renderPresets"
NO_PRESET = "-- None --"

RENDER_NODES = ("defaultArnoldRenderOptions", "defaultArnoldDriver", "defaultArnoldFilter",
                "defaultRenderGlobals", "defaultResolution")
# The shot's own, not a look: never carried from one shot to another.
SHOT_ATTRS = {"defaultRenderGlobals": {"startFrame", "endFrame", "byFrame", "byFrameStep",
                                       "imageFilePrefix"}}
# Scripts are never stored (a preset must not run code in another shot).
SCRIPT_ATTR = re.compile(r"mel|python|script|callback", re.IGNORECASE)
# Arnold's own run state (IPR started/finished), not a setting.
STATE_ATTR = re.compile(r"^IPR")

MAYA_LIGHTS = ("ambientLight", "directionalLight", "pointLight", "spotLight", "areaLight",
               "volumeLight")
ARNOLD_LIGHTS = ("aiAreaLight", "aiSkyDomeLight", "aiPhotometricLight", "aiLightPortal")
# Needs the mesh it lights from: not something a preset can make in another shot.
SKIPPED_LIGHTS = ("aiMeshLight",)
# Nodes feeding a light that are remade with it: Arnold's light filters and
# textures (an HDRI file on a skydome). Anything else feeding a light (an
# animation curve, an expression) is stored as the value it gives now.
FILTER_TYPES = ("aiBarndoor", "aiGobo", "aiLightBlocker", "aiLightDecay")
VALUE_TYPES = {"bool", "byte", "char", "short", "long", "enum", "float", "double",
               "doubleLinear", "doubleAngle", "time", "string"}
TRANSFORM_ATTRS = ("rotateOrder", "visibility")


class PresetError(Exception):
    pass


# ---------------------------------------------------------------------------
# Where presets live
# ---------------------------------------------------------------------------

def _film_folder(scene_path):
    """<root>\\<film>\\maya for a scene inside a film folder, else None."""
    try:
        import publishTool_api as pub
        root, rel = pub.find_film_folder(scene_path)
    except Exception:
        return None
    return os.path.join(root, rel[0], "maya") if len(rel) > 1 else None


def preset_folder(scene_path=None):
    """The folder presets are saved in and listed from (made if missing)."""
    scene_path = cmds.file(q=True, sceneName=True) if scene_path is None else scene_path
    film = _film_folder(scene_path) if scene_path else None
    if film:
        folder = os.path.join(film, FOLDER)
    else:
        root = cmds.workspace(q=True, rootDirectory=True)
        folder = os.path.join(root, cmds.workspace(fileRuleEntry="data") or "data", FOLDER)
    os.makedirs(folder, exist_ok=True)
    return os.path.normpath(folder)


def where_label(scene_path=None):
    """Where presets are shared, for the window."""
    scene_path = cmds.file(q=True, sceneName=True) if scene_path is None else scene_path
    film = _film_folder(scene_path) if scene_path else None
    if film:
        return "Film %s: shared by every shot" % os.path.basename(os.path.dirname(film))
    project = os.path.basename(os.path.normpath(cmds.workspace(q=True, rootDirectory=True) or ""))
    return "Project %s (not in a film folder)" % (project or "(none)")


def clean_name(name):
    """Letters, numbers, _ and -; spaces become _ (as the camera presets)."""
    return re.sub(r"[^A-Za-z0-9_\-]", "", (name or "").strip().replace(" ", "_"))


def preset_path(name, folder=None):
    return os.path.join(folder or preset_folder(), clean_name(name) + ".json")


def list_presets(folder=None):
    folder = folder or preset_folder()
    return sorted(os.path.splitext(n)[0] for n in os.listdir(folder)
                  if n.lower().endswith(".json"))


def read_preset(name, folder=None):
    path = preset_path(name, folder)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError) as e:
        raise PresetError("Couldn't read the preset '%s': %s" % (name, e))


def delete_preset(name, folder=None):
    os.remove(preset_path(name, folder))


# What feeds a light, as the window names it.
INPUT_LABELS = {"aiPhysicalSky": "Physical Sky", "file": "image file", "aiImage": "image file",
                "aiBarndoor": "barndoor", "aiGobo": "gobo", "aiLightBlocker": "light blocker",
                "aiLightDecay": "light decay"}


def lit_by(preset):
    """'aiSkyDomeLight1: Physical Sky (aiPhysicalSky3)' for each light with
    something feeding it, so the window shows a sky or HDRI was caught."""
    inputs = preset.get("inputs", {})
    out = []
    for light in preset.get("lights", []):
        names = []
        for feed in light.get("inputs", []):
            kind = inputs.get(feed["node"], {}).get("type", "")
            names.append("%s (%s)" % (INPUT_LABELS.get(kind, kind or "node"), feed["node"]))
        if names:
            out.append("%s: %s" % (light["name"], ", ".join(names)))
    return out


def describe(preset):
    """One line about a preset, for the window."""
    lights, aovs = len(preset.get("lights", [])), len(preset.get("aovs", []))
    when = (preset.get("savedAt") or "")[:10]
    fed = lit_by(preset)
    return "%d light(s), %d AOV(s).%s Saved from %s%s%s." % (
        lights, aovs, " " + "; ".join(fed) + "." if fed else "",
        preset.get("source") or "an unsaved scene",
        " by " + preset["savedBy"] if preset.get("savedBy") else "",
        " on " + when if when else "")


# ---------------------------------------------------------------------------
# Reading and writing attributes
# ---------------------------------------------------------------------------

_BASE = {}


def _base_attrs(kind):
    """Maya's own attributes every node (or every shape) has: not settings."""
    if kind not in _BASE:
        _BASE[kind] = set(cmds.attributeInfo(allAttributes=True, type=kind) or [])
    return _BASE[kind]


def _settings(node, base=(), skip=()):
    """{attr: value} for the node's own stored settings: numbers, on/offs,
    choices and text. Outputs, connected attributes, Maya's base attributes
    and scripts are left out."""
    names = set(cmds.listAttr(node, settable=True, scalar=True) or [])
    names |= {a for a in cmds.listAttr(node, settable=True) or [] if "." not in a
              and _type(node, a) == "string"}
    out = {}
    for a in sorted(names):
        if "." in a or a in base or a in skip or STATE_ATTR.match(a):
            continue
        try:
            if not cmds.attributeQuery(a, node=node, storable=True):
                continue
        except RuntimeError:
            continue
        kind = _type(node, a)
        if kind not in VALUE_TYPES or (kind == "string" and SCRIPT_ATTR.search(a)):
            continue
        value = cmds.getAttr("%s.%s" % (node, a))
        if kind == "string":
            value = value or ""
        out[a] = value
    return out


def _type(node, attr):
    try:
        return cmds.getAttr("%s.%s" % (node, attr), type=True)
    except (RuntimeError, ValueError):
        return None


def _set(plug, value):
    """True if the value went on (locked or missing attributes don't)."""
    try:
        if isinstance(value, str):
            cmds.setAttr(plug, value, type="string")
        else:
            cmds.setAttr(plug, value)
        return True
    except (RuntimeError, TypeError, ValueError):
        return False


def _set_all(node, values, counts):
    for a, v in values.items():
        if not cmds.objExists("%s.%s" % (node, a)):
            counts["skipped"] += 1
        elif cmds.getAttr("%s.%s" % (node, a)) == v or _set("%s.%s" % (node, a), v):
            counts["set"] += 1
        else:
            counts["skipped"] += 1


def _short(node):
    """A node's name without its path or namespace."""
    return node.split("|")[-1].split(":")[-1]


# ---------------------------------------------------------------------------
# Arnold
# ---------------------------------------------------------------------------

def ensure_arnold():
    """Load Arnold and make its render settings nodes if the scene has none."""
    if not cmds.pluginInfo("mtoa", q=True, loaded=True):
        try:
            cmds.loadPlugin("mtoa", quiet=True)
        except RuntimeError:
            raise PresetError("Arnold (mtoa) couldn't be loaded, so render presets can't be "
                              "used. Turn it on in the Plug-in Manager.")
    if not cmds.objExists("defaultArnoldRenderOptions"):
        import mtoa.core
        mtoa.core.createOptions()


def _aov_interface():
    import mtoa.aovs
    return mtoa.aovs.AOVInterface()


def capture_aovs():
    out = []
    for node in sorted(cmds.ls(type="aiAOV") or []):
        out.append({"name": cmds.getAttr(node + ".name"), "type": cmds.getAttr(node + ".type"),
                    "attrs": _settings(node, _base_attrs("network"), skip={"name"})})
    return out


def apply_aovs(aovs, counts):
    """Make the scene's AOVs the preset's: add missing, set all, remove others."""
    interface = _aov_interface()
    have = {cmds.getAttr(n + ".name"): n for n in cmds.ls(type="aiAOV") or []}
    wanted = {a["name"] for a in aovs}
    for name, node in have.items():
        if name not in wanted:
            interface.removeAOV(name)
            counts["aovs_removed"] += 1
    for aov in aovs:
        node = have.get(aov["name"])
        if not node:
            node = interface.addAOV(aov["name"], aovType=aov["type"]).node
            counts["aovs_added"] += 1
        _set_all(node, aov["attrs"], counts)


# ---------------------------------------------------------------------------
# Lights
# ---------------------------------------------------------------------------

def light_shapes():
    """Every Maya and Arnold light shape in the scene (not mesh lights)."""
    kinds = [t for t in MAYA_LIGHTS + ARNOLD_LIGHTS
             if t in (cmds.allNodeTypes() or [])]
    return sorted(cmds.ls(type=kinds, long=True) or [])


def skipped_lights():
    """Lights a preset can't hold (mesh lights), by name."""
    return sorted(_short(s) for s in cmds.ls(type=list(SKIPPED_LIGHTS), long=True) or [])


def _transform(shape):
    return cmds.listRelatives(shape, parent=True, fullPath=True)[0]


def _feeds(shape):
    """(dest attr, source node, source attr) for what feeds a light: its
    filters and textures, which are remade with it."""
    out = []
    pairs = cmds.listConnections(shape, source=True, destination=False, plugs=True,
                                 connections=True) or []
    for dest, src in zip(pairs[::2], pairs[1::2]):
        node, attr = src.split(".", 1)
        if _remade(cmds.nodeType(node)):
            out.append((dest.split(".", 1)[1], node, attr))
    return out


def _is_texture(kind):
    return any("texture/" in c or c == "texture" for c in
               ":".join(cmds.getClassification(kind) or []).split(":"))


def _remade(kind):
    return kind in FILTER_TYPES or _is_texture(kind)


def _fed_values(shape):
    """Attributes driven by something not remade (an animation curve, an
    expression): their value now."""
    out = {}
    pairs = cmds.listConnections(shape, source=True, destination=False, plugs=True,
                                 connections=True) or []
    remade = {d for d, _, _ in _feeds(shape)}
    for dest in pairs[::2]:
        attr = dest.split(".", 1)[1]
        if attr in remade or "." in attr or "[" in attr:
            continue
        kind = _type(shape, attr)
        if kind in VALUE_TYPES and kind != "string":
            out[attr] = cmds.getAttr(dest)
    return out


def capture_lights():
    """(lights, input nodes): each light with its world matrix and settings,
    and the filters and textures that feed them, by name."""
    lights, inputs = [], {}
    for shape in light_shapes():
        xf = _transform(shape)
        parent = cmds.listRelatives(xf, parent=True, fullPath=True)
        attrs = _settings(shape, _base_attrs("shape"))
        attrs.update(_fed_values(shape))
        feeds = []
        for attr, node, src_attr in _feeds(shape):
            key = _short(node)
            feeds.append({"attr": attr, "node": key, "plug": src_attr})
            if key not in inputs:
                inputs[key] = _capture_input(node)
        lights.append({
            "name": _short(xf), "shape": _short(shape), "type": cmds.nodeType(shape),
            "parent": _short(parent[0]) if parent else None,
            "matrix": cmds.xform(xf, q=True, worldSpace=True, matrix=True),
            "transform": {a: cmds.getAttr("%s.%s" % (xf, a)) for a in TRANSFORM_ATTRS},
            "attrs": attrs, "inputs": feeds})
    return lights, inputs


def _capture_input(node):
    data = {"type": cmds.nodeType(node), "attrs": _settings(node, _base_attrs("network"))}
    if cmds.objectType(node, isAType="dagNode"):        # a light blocker: a shape
        xf = _transform(cmds.ls(node, long=True)[0])
        data["name"] = _short(xf)
        data["matrix"] = cmds.xform(xf, q=True, worldSpace=True, matrix=True)
        data["attrs"] = _settings(node, _base_attrs("shape"))
    return data


def _find_light(light, shapes):
    """The scene's light with the preset light's name and type, or None."""
    for shape in shapes:
        if _short(_transform(shape)) == light["name"] and cmds.nodeType(shape) == light["type"]:
            return shape
    return None


def extra_lights(preset):
    """Lights in the scene that aren't in the preset (by name and type)."""
    shapes = light_shapes()
    matched = {_find_light(l, shapes) for l in preset.get("lights", [])}
    return [s for s in shapes if s not in matched]


def _named(xf, name, shape_name):
    """Rename a new transform and its shape; returns the shape (full path)."""
    xf = cmds.rename(xf, name)
    shape = cmds.listRelatives(xf, shapes=True, fullPath=True)[0]
    if shape_name and _short(shape) != shape_name:
        cmds.rename(shape, shape_name)
    return cmds.listRelatives(xf, shapes=True, fullPath=True)[0]


def _make_light(light):
    """A new light of the preset light's type and names, in its group if the
    scene has one of that name, else at the top of the scene."""
    xf = cmds.shadingNode(light["type"], asLight=True)
    shape = _named(xf, light["name"], light["shape"])
    parent = light.get("parent")
    if parent and len(cmds.ls(parent) or []) == 1 and cmds.objectType(parent, isAType="transform"):
        xf = cmds.parent(_transform(shape), parent)[0]
        shape = cmds.listRelatives(xf, shapes=True, fullPath=True)[0]
    return shape


def _make_input(name, data, made):
    """The scene's node for one of the preset's filters or textures: the
    one with its name and type, else a new one."""
    if name in made:
        return made[name]
    if data.get("matrix"):                       # a DAG input (light blocker)
        found = [s for xf in cmds.ls(data["name"], long=True) or []
                 for s in cmds.listRelatives(xf, shapes=True, type=data["type"], fullPath=True) or []]
        node = found[0] if found else _named(
            _transform(cmds.ls(cmds.createNode(data["type"]), long=True)[0]), data["name"], name)
        try:
            cmds.xform(_transform(node), worldSpace=True, matrix=data["matrix"])
        except RuntimeError:
            pass
    else:
        found = [n for n in cmds.ls(name) or [] if cmds.nodeType(n) == data["type"]]
        node = found[0] if found else (
            cmds.shadingNode(data["type"], asTexture=True, name=name) if _is_texture(data["type"])
            else cmds.createNode(data["type"], name=name))
    made[name] = node
    return node


def apply_lights(lights, inputs, remove_extra, counts):
    extras = extra_lights({"lights": lights})
    made = {}
    for light in lights:
        shape = _find_light(light, light_shapes())
        if shape:
            counts["lights_set"] += 1
        else:
            shape = _make_light(light)
            counts["lights_made"] += 1
        xf = _transform(shape)
        for a, v in light.get("transform", {}).items():
            _set("%s.%s" % (xf, a), v)
        try:
            cmds.xform(xf, worldSpace=True, matrix=light["matrix"])
        except RuntimeError:
            counts["not_moved"].append(light["name"])
        _set_all(shape, light["attrs"], counts)
        for feed in light.get("inputs", []):
            data = inputs.get(feed["node"])
            if not data:
                continue
            node = _make_input(feed["node"], data, made)
            _set_all(node, data["attrs"], counts)
            src, dest = "%s.%s" % (node, feed["plug"]), "%s.%s" % (shape, feed["attr"])
            if not cmds.isConnected(src, dest):
                try:
                    cmds.connectAttr(src, dest, force=True)
                except RuntimeError:
                    counts["skipped"] += 1
    if remove_extra:
        for shape in extras:
            xf = _transform(shape)
            if cmds.referenceQuery(xf, isNodeReferenced=True):
                counts["kept_referenced"].append(_short(xf))
            else:
                cmds.delete(xf)
                counts["lights_removed"] += 1


# ---------------------------------------------------------------------------
# Save and apply
# ---------------------------------------------------------------------------

def capture_render():
    base = _base_attrs("network")
    return {n: _settings(n, base, SHOT_ATTRS.get(n, ())) for n in RENDER_NODES if cmds.objExists(n)}


def capture(name):
    """The open scene's render settings, AOVs and lights as a preset."""
    ensure_arnold()
    lights, inputs = capture_lights()
    scene = cmds.file(q=True, sceneName=True)
    try:
        who = getpass.getuser()
    except Exception:
        who = ""
    return {"format": FORMAT, "presetName": clean_name(name),
            "savedAt": datetime.now().isoformat(timespec="seconds"), "savedBy": who,
            "source": os.path.splitext(os.path.basename(scene))[0] if scene else "",
            "sourceScene": scene, "render": capture_render(), "aovs": capture_aovs(),
            "lights": lights, "inputs": inputs, "skippedLights": skipped_lights()}


def save(name, folder=None):
    """Save the open scene as preset `name` (replacing one of that name).
    Returns (path, preset)."""
    if not clean_name(name):
        raise PresetError("Give the preset a name first, e.g. lookdev_001.")
    preset = capture(name)
    path = preset_path(name, folder)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2, sort_keys=True)
    os.replace(tmp, path)
    return path, preset


def apply(preset, remove_extra=False):
    """Make the open scene's render settings, AOVs and lights the preset's.
    remove_extra: True deletes lights the preset doesn't have (referenced
    ones can't be, and are listed), False keeps them. One undo.
    Returns counts of what changed."""
    if preset.get("format", 0) > FORMAT:
        raise PresetError("This preset was saved by a newer render presets tool. Update the "
                          "pipe tools, then apply it.")
    ensure_arnold()
    counts = {"set": 0, "skipped": 0, "aovs_added": 0, "aovs_removed": 0, "lights_set": 0,
              "lights_made": 0, "lights_removed": 0, "kept_referenced": [], "not_moved": []}
    cmds.undoInfo(openChunk=True, chunkName="Apply render preset")
    try:
        for node, values in preset.get("render", {}).items():
            if cmds.objExists(node):
                _set_all(node, values, counts)
        apply_aovs(preset.get("aovs", []), counts)
        apply_lights(preset.get("lights", []), preset.get("inputs", {}), remove_extra, counts)
    finally:
        cmds.undoInfo(closeChunk=True)
    return counts


def summary(counts):
    """What apply() did, in a sentence or two."""
    parts = ["%d light(s) set" % counts["lights_set"]]
    if counts["lights_made"]:
        parts.append("%d made" % counts["lights_made"])
    if counts["lights_removed"]:
        parts.append("%d removed" % counts["lights_removed"])
    if counts["aovs_added"] or counts["aovs_removed"]:
        parts.append("AOVs +%d / -%d" % (counts["aovs_added"], counts["aovs_removed"]))
    text = ", ".join(parts) + "; %d setting(s) applied." % counts["set"]
    if counts["skipped"]:
        text += " %d couldn't be set (locked or not in this Maya)." % counts["skipped"]
    if counts["kept_referenced"]:
        text += " Kept referenced light(s): %s." % ", ".join(counts["kept_referenced"])
    if counts["not_moved"]:
        text += " Couldn't move (locked or constrained): %s." % ", ".join(counts["not_moved"])
    return text

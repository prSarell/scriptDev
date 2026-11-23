"""
FBX Export (mpModel shelf, user 2026-11-24)

Exports the selected geometry and cameras as FBX to the asset's or shot's
Substance Painter folder, found from the open scene's own path:

    <film>\\maya\\assets\\<type>\\<asset>\\...      ->  <film>\\substancePainter\\assets\\<type>\\<asset>
    <film>\\maya\\sequences\\<seq>\\<shot>\\...     ->  <film>\\substancePainter\\sequences\\<seq>\\<shot>

e.g. D:\\NWF_SHF\\substancePainter\\assets\\environment\\hillShed\\hillShed_v001.fbx.
Each export is a new version (<asset or shot>_v001.fbx, v002, ...); nothing
is overwritten. In a shot the cameras' animation is baked over the
playback range; an asset exports as it stands.

Not part of the pipe: it only reads the scene's path, and doesn't touch
publishes, ShotGrid or the pipe's records. One click: run() exports and
says where; it refuses (with the reason) if nothing usable is picked or the
scene isn't saved in an asset or shot folder.
"""

import os
import re

import maya.cmds as cmds
import maya.mel as mel

FBX_PLUGIN = "fbxmaya"
MAYA_FOLDER = "maya"
TARGET_FOLDER = "substancePainter"
DEPTH = {"assets": 2, "sequences": 2}      # assets\<type>\<asset>, sequences\<seq>\<shot>
VERSION_RE = r"^%s_v(\d{3,})\.fbx$"
TITLE = "FBX Export"


class ExportError(Exception):
    pass


# ---------------------------------------------------------------------------
# Where it goes
# ---------------------------------------------------------------------------

def target(scene=None):
    """(folder, name, kind) for the open scene: the Substance Painter
    folder, the asset or shot name, and 'assets' or 'sequences'."""
    scene = scene or cmds.file(query=True, sceneName=True)
    if not scene:
        raise ExportError("Save the scene in its asset or shot folder first: the export "
                          "goes to that asset's or shot's Substance Painter folder.")
    parts = os.path.normpath(scene).split(os.sep)
    lowered = [p.lower() for p in parts]
    for i in range(len(parts) - 1, -1, -1):
        if lowered[i] != MAYA_FOLDER or i + 1 >= len(parts):
            continue
        kind = lowered[i + 1]
        depth = DEPTH.get(kind)
        if depth is None or i + 2 + depth > len(parts) - 1:     # -1: the file itself
            continue
        rel = [parts[i + 1]] + parts[i + 2:i + 2 + depth]
        film = os.sep.join(parts[:i]) or os.sep
        if film.endswith(":"):
            film += os.sep                                      # D: -> D:\
        folder = os.path.join(film, TARGET_FOLDER, *rel)
        return folder, rel[-1], kind
    raise ExportError("This scene isn't in an asset or shot folder:\n  %s\nOpen (or save) "
                      "it under <film>\\maya\\assets\\<type>\\<asset> or "
                      "<film>\\maya\\sequences\\<seq>\\<shot>." % scene)


def next_path(folder, name):
    """<folder>\\<name>_v###.fbx, one up from the highest already there."""
    pattern = re.compile(VERSION_RE % re.escape(name), re.IGNORECASE)
    taken = [int(m.group(1)) for m in (pattern.match(f) for f in
                                       (os.listdir(folder) if os.path.isdir(folder) else []))
             if m]
    return os.path.join(folder, "%s_v%03d.fbx" % (name, max(taken or [0]) + 1))


# ---------------------------------------------------------------------------
# What goes
# ---------------------------------------------------------------------------

def _shapes_under(node):
    """Every shape at or below node (listRelatives' shapes flag only finds
    node's own)."""
    below = cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
    return cmds.ls(below, shapes=True, long=True) or []


def picked(selection=None):
    """(roots, cameras, skipped): the picked transforms that hold geometry
    or a camera (a component or shape counts as its transform), the
    cameras among what's exported, and the picked things left out (USD
    stages: FBX can't carry them; lights and anything without geometry)."""
    selection = cmds.ls(selection if selection is not None else cmds.ls(selection=True),
                        long=True, objectsOnly=True) or []
    nodes = []
    for node in selection:
        if not cmds.objectType(node, isAType="transform"):
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
        if node and node not in nodes:
            nodes.append(node)
    nodes = [n for n in nodes if not any(n.startswith(o + "|") for o in nodes if o != n)]
    roots, cameras, skipped = [], [], []
    for node in nodes:
        shapes = _shapes_under(node)
        if any(cmds.nodeType(s) == "mayaUsdProxyShape" for s in shapes):
            skipped.append((node, "a USD stage (FBX can't carry it)"))
            continue
        geo = [s for s in shapes if cmds.objectType(s, isAType="geometryShape")
               and not cmds.objectType(s, isAType="camera")
               and not cmds.getAttr(s + ".intermediateObject")]
        cams = [s for s in shapes if cmds.nodeType(s) == "camera"]
        if geo or cams:
            roots.append(node)
            cameras += [cmds.listRelatives(c, parent=True, fullPath=True)[0] for c in cams]
        else:
            skipped.append((node, "no geometry or camera"))
    return roots, cameras, skipped


# ---------------------------------------------------------------------------
# The export
# ---------------------------------------------------------------------------

def _settings(bake):
    mel.eval("FBXResetExport")
    for command in ("FBXExportSmoothingGroups -v true",
                    "FBXExportSmoothMesh -v false",
                    "FBXExportTriangulate -v false",
                    "FBXExportTangents -v true",
                    "FBXExportEmbeddedTextures -v false",
                    "FBXExportInputConnections -v false",
                    "FBXExportCameras -v true",
                    "FBXExportLights -v false",
                    "FBXExportConstraints -v false",
                    "FBXExportSkins -v false",
                    "FBXExportShapes -v false",
                    "FBXExportAnimationOnly -v false"):
        mel.eval(command)
    mel.eval("FBXExportBakeComplexAnimation -v %s" % ("true" if bake else "false"))
    if bake:
        start = cmds.playbackOptions(query=True, minTime=True)
        end = cmds.playbackOptions(query=True, maxTime=True)
        mel.eval("FBXExportBakeComplexStart -v %d" % start)
        mel.eval("FBXExportBakeComplexEnd -v %d" % end)
        mel.eval("FBXExportBakeComplexStep -v 1")


def export(selection=None, scene=None):
    """Export what's picked to the next version in the asset's or shot's
    Substance Painter folder. Returns (path, roots, cameras, skipped)."""
    folder, name, kind = target(scene)
    film_target = os.path.dirname(os.path.dirname(os.path.dirname(folder)))
    if not os.path.isdir(film_target):
        raise ExportError("There's no %s folder in this film:\n  %s" % (TARGET_FOLDER,
                                                                         film_target))
    roots, cameras, skipped = picked(selection)
    if not roots:
        why = "".join("\n  %s: %s" % (n.split("|")[-1], r) for n, r in skipped)
        raise ExportError("Pick the geometry and cameras to export." + (
            "\nLeft out:" + why if why else ""))
    if not cmds.pluginInfo(FBX_PLUGIN, query=True, loaded=True):
        cmds.loadPlugin(FBX_PLUGIN, quiet=True)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    path = next_path(folder, name)
    before = cmds.ls(selection=True, long=True) or []
    try:
        _settings(bake=(kind == "sequences" and bool(cameras)))
        cmds.select(roots, replace=True)
        mel.eval('FBXExport -f "%s" -s' % path.replace("\\", "/"))
    finally:
        cmds.select(before, replace=True) if before else cmds.select(clear=True)
    if not os.path.isfile(path):
        raise ExportError("The FBX wasn't written:\n  %s" % path)
    return path, roots, cameras, skipped


def run():
    """The shelf button."""
    try:
        path, roots, cameras, skipped = export()
    except ExportError as e:
        cmds.confirmDialog(title=TITLE, message=str(e), button=["OK"])
        return None
    message = "Exported %d object(s)%s to:\n  %s" % (
        len(roots), (", %d camera(s)" % len(cameras)) if cameras else "", path)
    if skipped:
        message += "\n\nLeft out:" + "".join("\n  %s: %s" % (n.split("|")[-1], r)
                                            for n, r in skipped)
    print(message)
    cmds.inViewMessage(amg="FBX: <hl>%s</hl>" % os.path.basename(path),
                       pos="topCenter", fade=True)
    if skipped:
        cmds.confirmDialog(title=TITLE, message=message, button=["OK"])
    return path

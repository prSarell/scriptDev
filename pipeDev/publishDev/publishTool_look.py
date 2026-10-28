"""
Publish Tool — looks
A rig or model publish also writes its look (user, 2026-10-28: "I want to
automate texture application to caches in the pipe"): the shaders on its
geometry, so Build can put them back on an animation cache, which carries
no shaders. No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §4 "Shaders on caches, automatic".

    H drive  ...\\scout\\scenes\\s1234567\\scout_s1234567_rig_v004.ma
             ...\\scout\\scenes\\s1234567\\scout_s1234567_rig_v004_look.ma
             ...\\scout\\scenes\\s1234567\\scout_s1234567_rig_v004_look.json

The .ma holds only the material networks (what feeds each shading group:
shaders, file nodes, ...), never the shading groups: exporting a shading
group takes the meshes assigned to it along. The .json says what fed each
shading group and which meshes (or faces) it was on, by path with no
namespaces, so Build can make the shading groups again and assign them by
name. Written while the textures point at the H drive (inside
publishTool_textures.PublishedTextures), so the look uses the published
textures. No shaders but Maya's default = no look files.
"""

import os
import json

import maya.cmds as cmds

import publishTool_api as api

LOOK_FORMAT = 1
SUFFIX = "_look"
DEFAULT_SHADING_GROUPS = ("initialShadingGroup", "initialParticleSE")
# What connects into a shading group but isn't part of the material.
NOT_MATERIAL = ("geometryShape", "groupId")


def look_paths(plan):
    """(look .ma, look .json) next to the published file."""
    stem = os.path.splitext(plan["dest"])[0]
    return stem + SUFFIX + ".ma", stem + SUFFIX + ".json"


def _clean(path):
    """A DAG path with every namespace taken off (Publish takes them off)."""
    return "|".join(part.split(":")[-1] for part in path.split("|"))


def _under(node, roots):
    return any(node == r or node.startswith(r + "|") for r in roots)


def _members(engine, roots):
    """[{"path", "faces"}] of what the shading group is on, under roots.
    faces is a component list like "f[0:3]", or None for the whole mesh."""
    found = []
    for member in cmds.sets(engine, query=True) or []:
        for long in cmds.ls(member, long=True) or []:
            node, _, faces = long.partition(".")
            if cmds.objectType(node, isAType="shape"):
                node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
            if _under(node, roots):
                entry = {"path": _clean(node), "faces": faces or None}
                if entry not in found:
                    found.append(entry)
    return found


def _inputs(engine):
    """{shading group attribute: "node.attribute"} of what feeds it, e.g.
    {"surfaceShader": "skin_MTL.outColor"}, leaving out the meshes."""
    found = {}
    pairs = cmds.listConnections(engine, source=True, destination=False,
                                 connections=True, plugs=True) or []
    for i in range(0, len(pairs), 2):
        attr = pairs[i].split(".", 1)[1]
        node = pairs[i + 1].split(".")[0]
        if attr.startswith("dagSetMembers") or cmds.ls(node, type=NOT_MATERIAL):
            continue
        found[attr] = pairs[i + 1]
    return found


def collect(roots):
    """{shading group: {"inputs", "members"}} for the geometry under roots
    (long names), Maya's default shading groups left out."""
    roots = cmds.ls(roots, long=True) or []
    shapes = cmds.listRelatives(roots, allDescendents=True, fullPath=True,
                                type=api.GEOMETRY_TYPES) or []
    shapes = [s for s in shapes if not cmds.getAttr(s + ".intermediateObject")]
    engines = sorted(set(cmds.listConnections(shapes, type="shadingEngine") or []))
    look = {}
    for engine in engines:
        if engine.split(":")[-1] in DEFAULT_SHADING_GROUPS:
            continue
        members = _members(engine, roots)
        inputs = _inputs(engine)
        if members and inputs:
            look[_clean(engine)] = {"inputs": dict((a, _clean(p)) for a, p in inputs.items()),
                                    "members": members, "_inputs": inputs}
    return look


def export_look(plan, roots):
    """Write the look files for the geometry under roots. Returns the two
    paths, or None when there's no look (only Maya's default shader).
    Adds a warning when a material reaches back to geometry (e.g. a UV
    chooser), which would bring that geometry into the look file."""
    look = collect(roots)
    if not look:
        return None
    ma, js = look_paths(plan)
    for path in (ma, js):
        if os.path.exists(path):
            raise api.PublishError("%s already exists — try again." % path)
    if not os.path.isdir(os.path.dirname(ma)):
        os.makedirs(os.path.dirname(ma))
    materials = sorted(set(p.split(".")[0] for e in look.values() for p in e["_inputs"].values()))
    reaches = [n for n in cmds.ls(cmds.listHistory(materials) or [], type="geometryShape")]
    if reaches:
        plan.setdefault("warnings", []).append(
            "These shaders connect back to geometry, so the look file carries it too: "
            "%s" % ", ".join(sorted(set(n.split("|")[-1] for n in reaches))))
    selection = cmds.ls(selection=True)
    try:
        cmds.select(materials, replace=True, noExpand=True)
        cmds.file(ma, exportSelected=True, type="mayaAscii", force=True,
                  constructionHistory=True, channels=True, constraints=False,
                  expressions=True, shader=True, preserveReferences=False)
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    data = {
        "format": LOOK_FORMAT,
        "file": os.path.basename(ma),
        "published": os.path.basename(plan["dest"]),
        "asset": plan.get("asset"),
        "department": plan.get("code"),
        "version": plan.get("version"),
        "login": plan.get("login"),
        "shading_groups": dict((sg, {"inputs": e["inputs"], "members": e["members"]})
                               for sg, e in look.items()),
    }
    try:
        with open(js, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception:
        remove((ma, js))
        raise
    for path in (ma, js):
        api._lock(path)
    plan["look"] = {"file": ma, "map": js, "shading_groups": len(look)}
    return ma, js


def remove(paths):
    """Take look files off again (a publish that failed after writing them)."""
    import stat
    for path in paths or ():
        if path and os.path.isfile(path):
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)

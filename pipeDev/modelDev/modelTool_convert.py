"""
Model Tool — Convert to Model (mpModel shelf, user 2026-10-30)

Turns a published model or environment brought in from the pipe back into
a plain Maya model that can be worked on, saved and republished. Select
the asset's top node (or anything inside it) and click:

    1. a referenced publish (Build references into assets as into shots)
       is imported, and its textures are copied into this asset's own
       sourceimages\\<published name>\\ with the shaders pointed there (as
       Build's old Import into Asset did; user, 2026-10-30: Build always
       references, Convert makes it editable). One already imported is
       used as it is.
    2. the pipe group (<asset>_model_GRP / <asset>_env_GRP: stamp, lock,
       pipe icon) is removed; what was inside it goes to the world root,
       exactly where it was
    3. the namespace comes off everything that came in with it
    4. what the publish locked is unlocked (an environment's sky), and the
       publish's own locators group is removed (republishing makes new ones)

A fresh start (user): no note of where it came from. Nothing is frozen,
cleaned or moved; that's left to the student. Environment sets
(environment_SET and its role sets) are kept, so it can be republished.

Only the selected assets change, and only in an asset scene: in a shot it
would break Build's record of the shot. Anything that would clash with a
name already in the scene refuses before anything is changed.
No UI beyond a message, so it can be tested under mayapy.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\buildDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\modelDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_api, publishTool_env, pipeEnv, buildTool_api, modelTool_convert
    for m in (publishTool_api, publishTool_env, pipeEnv, buildTool_api, modelTool_convert):
        importlib.reload(m)
    modelTool_convert.run()
"""

import os

import maya.cmds as cmds

import publishTool_api as api
import publishTool_env as env
import buildTool_api as build

DEPT_ATTR = api.PIPE_ATTR_PREFIX + "department"
ASSET_ATTR = api.PIPE_ATTR_PREFIX + "asset"
CONVERTS = {api.MODEL_CODE: "model", env.ENV_CODE: "environment"}
# Sets the publish looks up by name: never let Maya number these.
NAMED_SETS = (env.ENVIRONMENT_SET,) + tuple(name for _, name in env.ROLE_SETS)


class ConvertError(Exception):
    pass


def _short(node):
    return node.split("|")[-1]


def _bare(name):
    """The name without its namespace."""
    return name.split("|")[-1].rsplit(":", 1)[-1]


def check_scene():
    """Refuse anything but a saved scene in an asset."""
    scene = cmds.file(query=True, sceneName=True)
    if not scene:
        raise ConvertError("Save this scene in your asset first (scenes\\model\\<your login>\\), "
                           "then convert.")
    place = api.pipe_place(scene)
    if not place:
        raise ConvertError("This scene isn't in the pipe. Open or save it in your asset's "
                           "scenes\\model\\<your login>\\ folder, then convert.")
    if place["kind"] != "asset":
        raise ConvertError(
            "This scene is in shot %s. Convert to Model only works in an asset scene: in a "
            "shot it would break Build's record of the shot.\nOpen (or save) a scene in the "
            "asset you're modelling, bring the publish in with Build, then convert it."
            % place["name"])


def pipe_group_of(node):
    """The outermost pipe group node sits in (or is), or None."""
    parts = cmds.ls(node, long=True)[0].split("|")[1:]
    for i in range(len(parts)):
        path = "|" + "|".join(parts[:i + 1])
        if api.is_pipe_group(path):
            return path
    return None


def _namespace(group):
    short = _short(group).lstrip(":")
    return short.rsplit(":", 1)[0] if ":" in short else ""


def _namespace_nodes(ns):
    if not ns or not cmds.namespace(exists=":" + ns):
        return []
    return cmds.namespaceInfo(":" + ns, listOnlyDependencyNodes=True, recurse=True,
                              dagPath=True) or []


def _what(group):
    dept = cmds.getAttr("%s.%s" % (group, DEPT_ATTR)) \
        if cmds.attributeQuery(DEPT_ATTR, node=group, exists=True) else ""
    asset = cmds.getAttr("%s.%s" % (group, ASSET_ATTR)) \
        if cmds.attributeQuery(ASSET_ATTR, node=group, exists=True) else _bare(group)
    return dept, asset


def _children(group):
    return cmds.listRelatives(group, children=True, fullPath=True, type="transform") or []


def check_group(group):
    """Refuse what this can't convert, before anything changes."""
    dept, asset = _what(group)
    if dept not in CONVERTS:
        raise ConvertError("%s is a %s publish. Convert to Model works on published models "
                           "and environments." % (_bare(group), dept or "pipe"))
    if cmds.referenceQuery(group, isNodeReferenced=True):
        ref = cmds.referenceQuery(group, referenceNode=True)
        if not cmds.referenceQuery(ref, isLoaded=True):
            raise ConvertError("%s's reference isn't loaded. Load it (Reference Editor), then "
                               "convert." % asset)
    # Names that would clash once the namespace is off and the group is
    # gone, where the name matters: the top groups (they go to the world
    # root, where Maya would make shed1) and the sets Publish finds by name.
    # Anything else (history like polyCube1, a shader) Maya numbers, and
    # its connections follow it, so it's only reported (see convert()).
    ns = _namespace(group)
    clashes = []
    for child in _children(group):
        name = _bare(child)
        if dept == env.ENV_CODE and name == env.LOCATOR_GROUP:
            continue
        if cmds.ls("|" + name):
            clashes.append(name)
    if ns:
        for node in _namespace_nodes(ns):
            if _bare(node) in NAMED_SETS and cmds.objExists(":" + _bare(node)):
                clashes.append(_bare(node))
    if clashes:
        raise ConvertError(
            "%s can't come in with its own names: these are already in the scene:\n  %s\n\n"
            "Rename or delete yours, then convert again." % (asset, "\n  ".join(sorted(set(clashes))[:10])))
    return dept, asset


def convert(group):
    """Convert one pipe group. Returns (asset, department, top nodes,
    [(name it came with, name Maya gave it)] for the few it had to number)."""
    dept, asset = check_group(group)
    ns = _namespace(group)
    uuid = cmds.ls(group, uuid=True)[0]
    name = _short(group)
    if cmds.referenceQuery(group, isNodeReferenced=True):
        ref = cmds.referenceQuery(group, referenceNode=True)
        pulled = os.path.expandvars(cmds.referenceQuery(ref, filename=True,
                                                        withoutCopyNumber=True))
        cmds.file(cmds.referenceQuery(ref, filename=True), importReference=True)
        # The asset's own copies of the publish's textures, as an editable
        # model's should be (the pulled ones are read-only and shared).
        place = api.pipe_place(cmds.file(query=True, sceneName=True))
        nodes = _namespace_nodes(ns) if ns else []
        if place and nodes:
            build.own_files(nodes, pulled, place["folder"])
    group = (cmds.ls(uuid, long=True) or cmds.ls("|" + name.lstrip("|"), long=True))[0]

    # Leftovers of the publish: its locators (an environment republish makes
    # new ones) and its locks.
    for child in _children(group):
        if dept == env.ENV_CODE and _bare(child) == env.LOCATOR_GROUP:
            cmds.delete(child)
    inside = cmds.listRelatives(group, allDescendents=True, fullPath=True, type="transform") or []
    for node in inside:
        for attr in env.TRANSFORM_CHANNELS:
            plug = "%s.%s" % (node, attr)
            if cmds.getAttr(plug, lock=True):
                cmds.setAttr(plug, lock=False)

    # Out of the pipe group, at the world root, where they were.
    tops = cmds.ls([cmds.parent(c, world=True)[0] for c in _children(group)], uuid=True)
    api.delete_pipe_group(group)

    # And no namespace.
    renamed = []
    for node_uuid in cmds.ls(_namespace_nodes(ns), uuid=True):
        node = cmds.ls(node_uuid, long=True)[0]
        if cmds.lockNode(node, query=True, lock=True)[0]:
            cmds.lockNode(node, lock=False)
        wanted = _bare(node)
        got = _short(cmds.rename(node, ":" + wanted, ignoreShape=True)).lstrip(":")
        if got != wanted:
            renamed.append((wanted, got))
    if ns and cmds.namespace(exists=":" + ns):
        cmds.namespace(removeNamespace=":" + ns, mergeNamespaceWithRoot=True)
    return asset, dept, cmds.ls(tops, long=True), renamed


def convert_selected(selection=None):
    """Convert every pipe asset in the selection. Returns
    [(asset, department, top nodes)]."""
    check_scene()
    selection = cmds.ls(selection if selection is not None else cmds.ls(selection=True),
                        long=True) or []
    if not selection:
        raise ConvertError("Select the top node of the published model or environment "
                           "(e.g. shed_env_GRP), then convert.")
    groups, outside = [], []
    for node in selection:
        group = pipe_group_of(node)
        if not group:
            outside.append(_short(node))
        elif group not in groups:
            groups.append(group)
    if outside:
        raise ConvertError("Not part of a published pipe asset: %s\nSelect the top node of "
                           "the published model or environment (it has the pipe icon)."
                           % ", ".join(outside[:10]))
    # Everything is checked before anything changes.
    uuids = cmds.ls(groups, uuid=True)
    for group in groups:
        check_group(group)
    done = [convert(cmds.ls(u, long=True)[0]) for u in uuids]
    cmds.select([n for _, _, tops, _ in done for n in tops], replace=True)
    return done


def run():
    try:
        done = convert_selected()
    except ConvertError as e:
        cmds.confirmDialog(title="Convert to Model", message=str(e), button=["OK"])
        return
    lines = ["%s %s" % (asset, CONVERTS[dept]) for asset, dept, _, _ in done]
    cmds.inViewMessage(amg="Converted to a plain model: <hl>%s</hl>. Save it, work on it, "
                           "publish it." % ", ".join(lines), pos="midCenter", fade=True)
    print("Convert to Model: %s is a plain Maya model now (no pipe group, no namespace)."
          % ", ".join(lines))
    renamed = [r for _, _, _, names in done for r in names]
    if renamed:
        print("Convert to Model: already in the scene, so Maya numbered these (their "
              "connections are fine): %s"
              % ", ".join("%s -> %s" % r for r in renamed))

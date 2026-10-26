"""
Layout Tool — environment sets (mpLayout shelf)
One click makes the empty groups and sets an environment publish needs,
with the right names (user, 2026-10-23). The artist then puts what they want
published into the groups. Nothing they've made is moved or changed.

    environment                 group
      landscape                 group, in landscape_SET
      buildings                 group, in building_SET (a group per building inside)
      sky                       group, in sky_SET
    environment_SET
      landscape_SET / building_SET / sky_SET

The names come from publishTool_env, so they always match what Publish
checks (spec §4c). Whatever already exists is reused, never duplicated.
A role set that already holds something is left as the artist made it.
No UI beyond a message, so it can be tested under mayapy.

Dev launch (Script Editor, Python tab):

    import sys, importlib
    for p in (r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\publishDev",
              r"C:\\Users\\scout\\Documents\\maya\\scriptDev\\pipeDev\\layoutDev"):
        if p not in sys.path: sys.path.insert(0, p)
    import publishTool_env, layoutTool_env
    for m in (publishTool_env, layoutTool_env): importlib.reload(m)
    layoutTool_env.run()
"""

import maya.cmds as cmds

import publishTool_env as env

TOP_GROUP = "environment"
# Role -> the group made for it under environment (buildings: the one group
# building_SET must hold, publishTool_env.BUILDINGS_GROUP).
ROLE_GROUPS = ((env.LANDSCAPE, "landscape"), (env.BUILDINGS, env.BUILDINGS_GROUP),
               (env.SKY, "sky"))


def _child(parent, name):
    """parent's direct child transform called name, or None."""
    for node in cmds.listRelatives(parent, children=True, fullPath=True,
                                   type="transform") or []:
        if node.split("|")[-1] == name:
            return node
    return None


def _group(name, parent=None):
    """An empty group called exactly name (Maya would add a number if the
    name is used elsewhere in the scene)."""
    node = cmds.group(empty=True, name=name, **({"parent": parent} if parent else {}))
    node = cmds.ls(node, long=True)[0]
    if node.split("|")[-1] != name:
        node = cmds.ls(cmds.rename(node, name), long=True)[0]
    return node


def _object_set(name):
    """(the objectSet called name, made?). Refuses a non-set node with that
    name, since Publish looks for the set by name."""
    if cmds.objExists(name):
        if cmds.nodeType(name) != "objectSet":
            raise RuntimeError("%s already exists but isn't a set (it's a %s). Rename it, "
                               "then run Environment Sets again."
                               % (name, cmds.nodeType(name)))
        return name, False
    return cmds.sets(empty=True, name=name), True


def make_environment_structure():
    """Make whatever is missing of the environment groups and sets.
    Returns (made, kept): lists of what was made and what was already there."""
    made, kept = [], []
    top = next((n for n in cmds.ls(TOP_GROUP, long=True, type="transform") or []
                if n.count("|") == 1), None)
    if top:
        kept.append(TOP_GROUP)
    else:
        top = _group(TOP_GROUP)
        made.append(TOP_GROUP)

    env_set, new = _object_set(env.ENVIRONMENT_SET)
    (made if new else kept).append(env.ENVIRONMENT_SET)
    for (role, group_name), (_, set_name) in zip(ROLE_GROUPS, env.ROLE_SETS):
        group = _child(top, group_name)
        if group:
            kept.append("%s|%s" % (TOP_GROUP, group_name))
        else:
            group = _group(group_name, top)
            made.append("%s|%s" % (TOP_GROUP, group_name))
        role_set, new = _object_set(set_name)
        if not cmds.sets(role_set, isMember=env_set):
            cmds.sets(role_set, add=env_set)
        if new or not cmds.sets(role_set, query=True):
            cmds.sets(group, add=role_set)
            made.append("%s holds %s" % (set_name, group_name))
        else:
            kept.append("%s (already holds %s)" % (
                set_name, ", ".join(m.split("|")[-1] for m in cmds.sets(role_set, query=True))))
    return made, kept


def run():
    """Shelf button: make the structure (one undo), then say what happened."""
    cmds.undoInfo(openChunk=True, chunkName="mpLayout environment sets")
    try:
        made, kept = make_environment_structure()
    except RuntimeError as e:
        cmds.confirmDialog(title="Environment Sets", message=str(e), button=["OK"])
        return
    finally:
        cmds.undoInfo(closeChunk=True)
    text = "Made:\n  " + "\n  ".join(made) if made else "Everything was already there."
    if made and kept:
        text += "\n\nAlready there (left as is):\n  " + "\n  ".join(kept)
    text += ("\n\nPut the terrain in landscape, each building in its own group inside "
             "buildings, and image planes / skydome in sky. A group you don't need "
             "(no buildings, no sky) can stay empty: the publish leaves it out.")
    print(text)
    cmds.confirmDialog(title="Environment Sets", message=text, button=["OK"])

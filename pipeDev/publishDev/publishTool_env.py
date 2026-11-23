"""
Publish Tool — environments (spec §4c, DECIDED 2026-10-21). No UI, so it
can be tested under mayapy.

An environment is laid out in a shot's layout scene (or its own asset
scene) and published to an environment asset. Groups say where things
are, sets say what they are:

    environment_SET
      landscape_SET   stays where it is, cleaned up like a model (frozen,
                      history deleted, Mesh Cleanup); the geometry doesn't move
      building_SET    any number of groups / objects, named freely, nested
                      however the artist likes (user, 2026-11-12); transforms
                      kept
      sky_SET         image planes / skydome geometry / clouds; transforms
                      kept, locked in the publish; pictures and image
                      sequences travel with it

Each set takes any number of groups or objects. A group named after its
role (landscape / buildings / sky, as Layout makes them) with no transforms
of its own is unpacked, so the publish has buildings > shed, not
buildings > buildings > shed. Locators aren't made any more (user,
2026-11-12: "lets remove this as an essential part of the publish"): an
artist's own locators in the sets publish like anything else.

The published file (copies only; the working scene is never changed):

    <asset>_model_GRP                pipe group, stamped, locked at the origin
      landscape / buildings / sky    the copies, by role
    + environment_SET and its role sets, holding the copies, so the publish
      follows the same rules as the scene

plus <published name>.abc beside it: one frame of the landscape and
buildings, for visual reference when a shot is rebuilt.
"""

import os
import json

import maya.cmds as cmds

import publishTool_api as api
from publishTool_api import PublishError

ENV_CODE = api.ENV_CODE
# An environment asset's publish is its Modeling publish (user, 2026-10-30:
# "Environment is not a department"): named and stamped model, numbered with
# the asset's other Modeling publishes. ENV_CODE only routes it here.
ENV_LABEL = "Modeling"
ENV_TYPE = "environment"
ENVIRONMENT_SET = "environment_SET"
LANDSCAPE, BUILDINGS, SKY = "landscape", "buildings", "sky"
ROLE_SETS = ((LANDSCAPE, "landscape_SET"), (BUILDINGS, "building_SET"), (SKY, "sky_SET"))
BUILDINGS_GROUP = "buildings"   # the group Layout makes for building_SET
# Publishes before 2026-11-12 made <building>_LOC locators in this group;
# Model's convert still clears it out of those.
LOCATOR_GROUP = "locators"
TRANSFORM_CHANNELS = ("translateX", "translateY", "translateZ", "rotateX", "rotateY",
                      "rotateZ", "scaleX", "scaleY", "scaleZ")
TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _short(node):
    return node.split("|")[-1].split(":")[-1]


def _how():
    return ("\n\nAn environment publish needs %s (Create > Sets > Set) holding these "
            "sets, each made by hand:\n  landscape_SET   the terrain: stays where it is\n"
            "  building_SET    buildings: any groups or objects\n"
            "  sky_SET         image planes, skydome, clouds\nPut the objects or groups in "
            "the set for their role; a group's whole contents go with it." % ENVIRONMENT_SET)


def find_sets():
    """{"environment": the environment_SET, role: its role set or None}.
    Raises PublishError if the sets aren't there or aren't nested right."""
    envs = api._own_sets(ENVIRONMENT_SET)
    if not envs:
        raise PublishError("This scene has no %s." % ENVIRONMENT_SET + _how())
    if len(envs) > 1:
        raise PublishError("This scene has more than one %s (%s). Keep just one."
                           % (ENVIRONMENT_SET, ", ".join(envs)))
    found = {"environment": envs[0]}
    inside = set(api.set_tree(envs[0]))
    for role, name in ROLE_SETS:
        sets = api._own_sets(name)
        if len(sets) > 1:
            raise PublishError("This scene has more than one %s (%s). Keep just one."
                               % (name, ", ".join(sets)))
        if sets and sets[0] not in inside:
            raise PublishError("%s isn't inside %s. Add it to %s (sets can hold sets)."
                               % (sets[0], ENVIRONMENT_SET, ENVIRONMENT_SET))
        found[role] = sets[0] if sets else None
    if not any(found[role] for role, _ in ROLE_SETS):
        raise PublishError("%s has none of landscape_SET, building_SET or sky_SET in it."
                           % ENVIRONMENT_SET + _how())
    return found


def role_members(object_set):
    """The transforms a role set stands for (shapes/components count as
    their transform), top-most only."""
    if not object_set:
        return []
    nodes = api.cache_transforms(cmds.sets(object_set, query=True) or [])
    return [n for n in nodes if n not in api.nested_in(nodes)]


def _has_contents(node):
    """False for an empty group: nothing under it to publish."""
    return bool(cmds.listRelatives(node, allDescendents=True))


def _is_identity(node):
    values = cmds.xform(node, query=True, matrix=True, worldSpace=True)
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    return all(abs(a - b) < TOLERANCE for a, b in zip(values, identity))


def unpacks(node, role):
    """True for a group named after its role (landscape / buildings / sky,
    as Layout makes them) that has no shape and no transforms of its own:
    the publish takes its contents, not the group, so nothing ends up
    nested in a group of the same name (fieldA's landscape|landscape)."""
    return (_short(node) == role
            and not cmds.listRelatives(node, shapes=True)
            and bool(cmds.listRelatives(node, children=True, type="transform"))
            and _is_identity(node))


def check_environment(h_root=None, film=None):
    """What an environment publish takes, by role:
    {"sets", landscape: [...], buildings: [...], sky: [...], "warnings"}:
    the top-most transforms in each role set, any number of them (user,
    2026-11-12). A role with nothing in it (no set, an empty set, or only
    empty groups) is left out with a warning: not every environment has
    buildings or a sky (user, 2026-10-26). Raises PublishError explaining
    what to fix. (h_root/film: kept for callers.)"""
    sets = find_sets()
    found = {"sets": sets, "warnings": []}
    seen = {}
    for role, name in ROLE_SETS:
        members = [m for m in role_members(sets[role]) if _has_contents(m)]
        for node in members:
            if node in seen:
                raise PublishError("%s is in both %s and %s. Each thing has one role."
                                   % (_short(node), dict(ROLE_SETS)[seen[node]], name))
            seen[node] = role
        found[role] = members
    for a in seen:
        for b in seen:
            if a != b and b.startswith(a + "|"):
                raise PublishError("%s (%s) is inside %s (%s). Each thing has one role: "
                                   "take the inner one out of its set."
                                   % (_short(b), seen[b], _short(a), seen[a]))
    empty = [role for role, _ in ROLE_SETS if not found[role]]
    if len(empty) == len(ROLE_SETS):
        raise PublishError("There's nothing to publish: landscape, buildings and sky are "
                           "all empty." + _how())
    if empty:
        found["warnings"].append("No %s in this environment, so it was published without."
                                 % " or ".join(empty))
    return found


# ---------------------------------------------------------------------------
# Where it goes
# ---------------------------------------------------------------------------

def plan_environment(scene_path, h_root, scratch_root, target):
    """Like publishTool_api.plan_publish, for an environment: from a shot's
    or an asset's scene on scratch, to an environment asset on H."""
    h_root, scratch_root = api.resolve_root(h_root), api.resolve_root(scratch_root)
    api.check_roots(h_root, scratch_root)
    root, rel = api.find_film_folder(scene_path)
    in_shot = len(rel) >= 7 and rel[1:3] == ["maya", "sequences"] and rel[5] == "scenes"
    in_asset = len(rel) >= 7 and rel[1:3] == ["maya", "assets"] and rel[5] == "scenes"
    if not (in_shot or in_asset):
        raise PublishError("Publish an environment from a shot's or an asset's scenes folder.")
    ext = os.path.splitext(rel[-1])[1].lower()
    if ext not in api.SCENE_EXTS:
        raise PublishError("Only .ma / .mb scenes can be published.")
    if not api._same_path(root, scratch_root):
        raise PublishError("This scene isn't on your scratch drive (%s). Work from scratch "
                           "and publish from there." % scratch_root)
    if not target or target[0] != ENV_TYPE:
        raise PublishError("Pick the environment asset to publish to.")
    film, asset = rel[0], target[1]
    asset_rel = [film, "maya", "assets", ENV_TYPE, asset]
    if not os.path.isdir(os.path.join(h_root, *asset_rel)):
        raise PublishError("No folder for environment '%s' on the H drive." % asset)
    login = api.who()
    h_folder = api.personal_folder(h_root, asset_rel, login)
    versions = api.published_versions(h_folder, asset, login, api.MODEL_CODE)
    version = (versions[-1] + 1) if versions else 1
    name = api.published_name(asset, login, api.MODEL_CODE, version, ext)
    return {"root": root, "film": film, "asset_type": ENV_TYPE, "asset": asset,
            "rel_folder": asset_rel + ["scenes"], "ext": ext,
            "asset_project": os.path.join(root, *rel[:5]),     # where the scene is, on scratch
            "source_asset": tuple(rel[3:5]) if in_asset else None,
            "is_source_asset": in_asset and tuple(rel[3:5]) == tuple(target),
            "login": login, "code": api.MODEL_CODE, "h_folder": h_folder, "version": version,
            "dest": os.path.join(h_folder, name)}


def cache_path(plan):
    return os.path.splitext(plan["dest"])[0] + ".abc"


def source_image_warnings(entries, plan):
    """Images that aren't in an asset's own sourceimages folder (spec §4c:
    source images belong in the asset's Maya project). Copied anyway."""
    outside = []
    for entry in entries:
        for f in entry["files"]:
            try:
                _, rel = api.find_film_folder(f)
                ok = len(rel) > 6 and rel[1:3] == ["maya", "assets"] and rel[5] == "sourceimages"
            except PublishError:
                ok = False
            if not ok:
                outside.append(f)
    if not outside:
        return []
    return ["Some images aren't in an asset's own sourceimages folder (they were copied "
            "with the publish anyway): %s" % ", ".join(sorted(set(outside))[:5])]


# ---------------------------------------------------------------------------
# The export
# ---------------------------------------------------------------------------

def _plain_group(name, parent):
    return cmds.group(empty=True, name=name, parent=parent)


def _lock_channels(node):
    for attr in TRANSFORM_CHANNELS:
        cmds.setAttr("%s.%s" % (node, attr), lock=True)


def export_environment_to_h_drive(plan, scene_path, found, warnings):
    """Build the published layout on copies (originals renamed aside so the
    copies keep their names), export it with its sets, write the one-frame
    cache, and put the working scene back exactly as it was."""
    import publishTool_textures as tex
    if os.path.exists(plan["dest"]):
        raise PublishError("%s already exists — try again." % plan["dest"])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])
    file_type = "mayaAscii" if plan["ext"] == ".ma" else "mayaBinary"
    group_name = api.pipe_group_name(plan["asset"], api.MODEL_CODE)
    selection = cmds.ls(selection=True)
    moved, made = [], []        # (uuid, short name) renamed aside; nodes to delete after
    roles = dict((role, cmds.ls(found[role], uuid=True)) for role, _ in ROLE_SETS)
    set_names = [ENVIRONMENT_SET] + [name for _, name in ROLE_SETS]
    try:
        with api._NoNamespaces() as clean:
            try:
                for name in [group_name] + set_names:
                    for node in cmds.ls(name) or []:
                        moved.append((cmds.ls(node, uuid=True)[0], name))
                        cmds.rename(node, "pipeTmp_" + name)
                group = api.make_pipe_group(group_name)
                made.append(cmds.ls(group, uuid=True)[0])
                group = cmds.ls(group, long=True)[0]
                holders, copies = {}, {}
                twins = []      # (original, copy) for api._CopiesDriveShaders
                for role, _ in ROLE_SETS:
                    holders[role] = cmds.ls(_plain_group(role, group), long=True)[0]
                    copies[role] = []
                    for uuid in roles[role]:
                        original = cmds.ls(uuid, long=True)[0]
                        short = original.split("|")[-1]
                        unpack = unpacks(original, role)
                        # Children by name (a copy's children keep their names).
                        inner = dict((c.split("|")[-1], cmds.ls(c, uuid=True)[0])
                                     for c in cmds.listRelatives(
                                         original, children=True, fullPath=True,
                                         type="transform") or []) if unpack else {}
                        copy = cmds.duplicate(original, returnRootsOnly=True)[0]
                        moved.append((uuid, short))
                        cmds.rename(original, "pipeTmp_" + short)
                        copy = cmds.rename(copy, short)
                        # World space kept: parent keeps the world placement.
                        copy = cmds.ls(cmds.parent(copy, holders[role])[0], long=True)[0]
                        if not unpack:
                            copies[role].append(cmds.ls(copy, uuid=True)[0])
                            twins.append((uuid, copies[role][-1]))
                            continue
                        # A group named after its role: its contents go in
                        # the role's group instead (no buildings|buildings).
                        for child in cmds.listRelatives(copy, children=True, fullPath=True,
                                                        type="transform") or []:
                            name = child.split("|")[-1]
                            child = cmds.ls(cmds.parent(child, holders[role])[0], long=True)[0]
                            copies[role].append(cmds.ls(child, uuid=True)[0])
                            if name in inner:
                                twins.append((inner[name], copies[role][-1]))
                        cmds.delete(copy)
                # Landscape: cleaned up like a model; the geometry stays put.
                land = cmds.ls(copies[LANDSCAPE], long=True)
                if land:
                    everything = land + (cmds.listRelatives(land, allDescendents=True,
                                                            fullPath=True) or [])
                    for mesh in cmds.ls(everything, type="mesh", long=True) or []:
                        if not cmds.getAttr(mesh + ".intermediateObject"):
                            try:
                                cmds.polyClean(mesh, cleanEdges=True, cleanVertices=True)
                            except RuntimeError:
                                pass
                    cmds.delete(everything, constructionHistory=True)
                    cmds.makeIdentity(land, apply=True, translate=True, rotate=True,
                                      scale=True, normal=0, preserveNormals=True)
                # Buildings: transforms kept, as they are. Sky: kept, locked.
                for uuid in copies[SKY]:
                    _lock_channels(cmds.ls(uuid, long=True)[0])
                # The artist's own locators, if any, travel like anything
                # else; recorded on the stamp (Model's convert reads it).
                locators = sorted(set(
                    cmds.listRelatives(shape, parent=True)[0] for shape in cmds.ls(
                        cmds.listRelatives(list(holders.values()), allDescendents=True,
                                           fullPath=True) or [], type="locator")))
                # The sets again, on the copies, so the publish says what's what.
                role_sets = []
                for role, name in ROLE_SETS:
                    if found["sets"][role]:
                        nodes = cmds.ls(copies[role], long=True)
                        role_sets.append(cmds.sets(nodes, name=name) if nodes else
                                         cmds.sets(empty=True, name=name))
                env_set = cmds.sets(role_sets, name=ENVIRONMENT_SET)
                made += cmds.ls(role_sets + [env_set], uuid=True)
                info = api.pipe_group_info(plan, scene_path)
                texture_nodes = cmds.ls(copies[LANDSCAPE] + copies[BUILDINGS] + copies[SKY],
                                        long=True)
                entries = tex.collect(texture_nodes, image_planes=True)
                warnings += source_image_warnings(entries, plan)
                with tex.PublishedTextures(entries, plan) as files:
                    api._stamp(group, info + [
                        ("buildings", json.dumps([cmds.ls(u)[0].split("|")[-1]
                                                  for u in copies[BUILDINGS]])),
                        ("locators", json.dumps(locators)),
                        ("textures", json.dumps(files.stamp_textures)),
                    ])
                    api.finish_pipe_group(group)
                    cmds.select(group, replace=True)
                    cmds.select(cmds.ls(made[1:]), add=True, noExpand=True)
                    with api._CopiesDriveShaders(twins), api._WithoutUnknownData():
                        cmds.file(plan["dest"], exportSelected=True, type=file_type,
                                  constructionHistory=True, channels=True, constraints=True,
                                  expressions=True, shader=True, preserveReferences=True,
                                  force=True)
                    api.drop_unknown_requires(plan["dest"])
                    roots = [holders[r] for r in (LANDSCAPE, BUILDINGS) if copies[r]]
                    if roots:
                        write_cache(roots, cache_path(plan))
                    # ABC / USD / FBX / OBJ for other software, from the same
                    # copy (publishTool_outputs).
                    import publishTool_outputs as outputs
                    with api._CopiesDriveShaders(twins):
                        outputs.write(plan, [group])
                plan["environment"] = dict(
                    (role, [cmds.ls(u)[0].split("|")[-1] for u in copies[role]])
                    for role, _ in ROLE_SETS)
                plan["environment"]["locators"] = locators
            finally:
                if cmds.ls(made):
                    for node in cmds.ls(made, long=True):
                        if cmds.objExists(node) and cmds.nodeType(node) == "dagContainer":
                            members = cmds.container(node, query=True, nodeList=True) or []
                            if members:
                                cmds.delete(members)
                    if cmds.ls(made):
                        cmds.delete(cmds.ls(made))
                for uuid, short in reversed(moved):
                    if cmds.ls(uuid):
                        cmds.rename(cmds.ls(uuid)[0], short)
    except Exception:
        for path in (plan["dest"], cache_path(plan)):
            if os.path.exists(path):
                os.chmod(path, 0o666)
                os.remove(path)
        raise
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    api._lock(plan["dest"])
    plan["namespaces_removed"] = sorted(clean.namespaces)
    plan["pipe_group"] = group_name


def write_cache(roots, path):
    """One frame (the current one) of the given groups, world space, for
    visual reference in shots."""
    if not cmds.pluginInfo("AbcExport", query=True, loaded=True):
        cmds.loadPlugin("AbcExport", quiet=True)
    frame = int(cmds.currentTime(query=True))
    job = ("-frameRange %d %d -uvWrite -worldSpace -writeVisibility -dataFormat ogawa %s "
           "-file \"%s\"" % (frame, frame, " ".join("-root %s" % r for r in roots),
                             path.replace("\\", "/")))
    cmds.AbcExport(jobArg=job)
    api._lock(path)

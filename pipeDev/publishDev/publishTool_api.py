"""
Publish Tool — core
Copies a saved scratch scene to the matching folder on the H drive as a
locked, versioned milestone. No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §3h (drives, 1:1 mirror) and §3i
(tabs, department codes, where publishes land).

    scratch  G:\\scratch\\NWF_SHF\\maya\\assets\\prop\\backpack\\scenes\\anything\\backPackPrevis.mb
    H drive  G:\\H\\NWF_SHF\\maya\\assets\\prop\\backpack\\scenes\\s1234567\\backpack_s1234567_model_v001.mb

Publishes are personal (spec §4 "Personal work folders", 2026-10-15): each
person's go in scenes\\<login>\\ with the login in the name, so everyone
has their own version series. Working files can be called anything.

One click publishes: playblast (shotSub-style, default 2 frames) ->
copy to H drive -> ShotGrid Version on the matching Asset. The local
frames are removed once ShotGrid has them. Clearing an asset off scratch
lives in the Build tool (pipeDev/buildDev), not here.

v0: asset publishes only; the scene file (or the listed objects) is the
only thing published, not textures/references.
"""

import os
import re
import glob
import json
import stat
import shutil
from datetime import datetime

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# Departments — (tab label, code). The code is used in published filenames
# and as the department subfolder in a shot (§3i). Order = tab order.
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    ("Modeling", "model"),
    ("Rigging",  "rig"),
    ("Previs",   "previs"),
    ("Anim",     "anim"),
    ("Creature", "creature"),
    ("LookDev",  "lookDev"),
    ("FX",       "fx"),
    ("Render",   "render"),
]

# Film folders are named <FILM>_<TYPE>, TYPE a three-letter code (§3f).
FILM_FOLDER_RE = re.compile(r"^[A-Za-z0-9]+_[A-Z]{3}$")

SCENE_EXTS = (".ma", ".mb")
CONFIG_NAME = "pipeline_config.json"     # per machine, Maya prefs folder
FILM_CONFIG_NAME = "pipeline.json"       # per film, in the H-drive film folder


class PublishError(Exception):
    """A problem the student can fix (unsaved scene, wrong folder...)."""


# ---------------------------------------------------------------------------
# Settings — where the H drive is. Drive letters differ between setups
# (home test rig, RMIT), so it's a setting, never hard-coded (§3h).
# ---------------------------------------------------------------------------

def _config_path():
    return os.path.join(cmds.internalVar(userPrefDir=True), CONFIG_NAME)


def load_config():
    try:
        with open(_config_path(), "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_config(config):
    with open(_config_path(), "w") as f:
        json.dump(config, f, indent=2)


# Setting keys for the two drive locations. Shared with the Build tool.
H_DRIVE = "h_drive_root"
SCRATCH = "scratch_root"


def get_root(key):
    return load_config().get(key, "")


# Who is publishing. Publishes are personal (spec §4 "Personal work
# folders", DECIDED 2026-10-15): they go in scenes\<login>\ with the login
# in the file name, so everyone has their own version series. The login
# is the Windows login (RMIT logins match ShotGrid logins). "publish_as"
# in the machine's settings overrides it, for staff testing on a machine
# whose Windows login isn't their RMIT one.
PUBLISH_AS = "publish_as"


def clean_login(name):
    """Logins go in file names between underscores: letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def who():
    """The login publishes are made under, e.g. 's1234567'."""
    import getpass
    login = clean_login(load_config().get(PUBLISH_AS, ""))
    if not login:
        try:
            login = clean_login(getpass.getuser())
        except Exception:
            login = clean_login(os.environ.get("USERNAME", ""))
    if not login:
        raise PublishError("Couldn't tell who is logged in, so the publish can't be named.")
    return login


def set_root(key, path):
    config = load_config()
    config[key] = os.path.normpath(path)
    save_config(config)


def resolve_root(path):
    """Accept the film folder itself (F:\\NWF_SHF) as well as the folder
    that holds it (F:\\): a drive root is always the latter."""
    if not path:
        return path
    path = os.path.normpath(path)
    if FILM_FOLDER_RE.match(os.path.basename(path)):
        return os.path.dirname(path)
    return path


def _same_path(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def check_roots(h_root, scratch_root):
    """Both locations set, both exist, and not the same place."""
    for name, path in (("H drive", h_root), ("Scratch drive", scratch_root)):
        if not path:
            raise PublishError("The %s location isn't set yet.\nSet it at the top of "
                               "the tool (Browse...)." % name)
        if not os.path.isdir(path):
            # Students move between classrooms, so a saved drive may not
            # exist on this machine (spec "Scratch drive follows the work").
            raise PublishError(
                "The %s is set to %s, but that isn't on this machine.\n"
                "Pick where the %s is on this machine (Browse...), or open a "
                "scene from your scratch drive and the tool will follow it."
                % (name, path, name))
    if _same_path(h_root, scratch_root):
        raise PublishError(
            "The H drive and scratch drive are set to the same place (%s)."
            % h_root)


def follow_open_scene(h_root, scratch_root):
    """The scratch drive follows the work (spec §3i "Scratch drive follows
    the work"): students move between classrooms and machines, so the drive
    a scene was opened from beats the saved setting.

    If the open scene is inside a film folder that isn't on the H drive,
    and its drive differs from scratch_root, save that drive as the scratch
    setting and return it. Otherwise return None (keep using scratch_root:
    no scene open -> the saved setting; saved drive missing -> check_roots
    explains)."""
    scene = cmds.file(query=True, sceneName=True) or ""
    if not scene:
        return None
    try:
        root, _ = find_film_folder(scene)
    except PublishError:
        return None
    if (h_root and _same_path(root, h_root)) or (scratch_root and _same_path(root, scratch_root)):
        return None
    if not os.path.isdir(root):
        return None
    set_root(SCRATCH, root)
    return os.path.normpath(root)


# ---------------------------------------------------------------------------
# Working out what the open scene is, from where it sits
# ---------------------------------------------------------------------------

def _split(path):
    return os.path.normpath(path).replace("\\", "/").split("/")


def find_film_folder(scene_path):
    """Split a scene path at its <FILM>_<TYPE> folder.

    Returns (root, film_relative_parts), e.g.
    ("D:\\", ["NWF_SHF", "maya", "assets", "prop", "backpack", "scenes", "x.mb"]).
    The root is whatever drive/folder holds the film folder, so the same
    film-relative path can be rebuilt under the H drive root.
    """
    parts = _split(scene_path)
    for i, part in enumerate(parts):
        if FILM_FOLDER_RE.match(part):
            root = os.path.normpath("/".join(parts[:i]) + "/")
            return root, parts[i:]
    raise PublishError(
        "This scene isn't inside a film folder (e.g. NWF_SHF).\n"
        "Open it from your scratch drive's film folder.")


def asset_context(scene_path):
    """Describe the asset a scene belongs to.

    Expects <FILM>/maya/assets/<type>/<asset>/scenes/.../<file>.
    """
    root, rel = find_film_folder(scene_path)
    if (len(rel) < 7 or rel[1] != "maya" or rel[2] != "assets"
            or rel[5] != "scenes"):
        raise PublishError(
            "This scene isn't in an asset's scenes folder.\n"
            "Expected: <film>\\maya\\assets\\<type>\\<asset>\\scenes\\")
    return {
        "root": root,
        "film": rel[0],
        "asset_type": rel[3],
        "asset": rel[4],
        "rel_folder": rel[:-1],     # film-relative folder the scene is in
        "asset_project": os.path.join(root, *rel[:5]),   # on scratch
        "ext": os.path.splitext(rel[-1])[1].lower(),
    }


# ---------------------------------------------------------------------------
# Versions on the H drive
# ---------------------------------------------------------------------------

def published_versions(folder, asset, login, code, exts=("ma", "mb")):
    """Sorted version numbers of <asset>_<login>_<code>_v###.<ext> in
    folder: one person's version series for one asset + department."""
    pattern = re.compile(
        r"^%s_%s_%s_v(\d{3})\.(%s)$" % (re.escape(asset), re.escape(login),
                                        re.escape(code), "|".join(exts)),
        re.IGNORECASE)
    if not os.path.isdir(folder):
        return []
    versions = []
    for name in os.listdir(folder):
        m = pattern.match(name)
        if m:
            versions.append(int(m.group(1)))
    return sorted(set(versions))


def published_name(asset, login, code, version, ext):
    """e.g. backpack_s1234567_model_v003.ma. Only the pipeline names
    published files; working files on scratch can be called anything."""
    return "%s_%s_%s_v%03d%s" % (asset, login, code, version, ext)


def personal_folder(h_root, rel_project, login):
    """<H>\\<film>\\maya\\...\\<asset or shot>\\scenes\\<login>: where one
    person's publishes for an asset or shot go."""
    return os.path.join(h_root, *(list(rel_project) + ["scenes", login]))


def list_h_assets(h_root, film):
    """Every asset folder on the H drive for this film, as
    [(asset_type, asset), ...]. These folders are named from the ShotGrid
    assets (§3f), so this is the list of assets that can be published to."""
    assets_dir = os.path.join(h_root, film, "maya", "assets")
    found = []
    if not os.path.isdir(assets_dir):
        return found
    for asset_type in sorted(os.listdir(assets_dir)):
        type_dir = os.path.join(assets_dir, asset_type)
        if not os.path.isdir(type_dir):
            continue
        for asset in sorted(os.listdir(type_dir), key=str.lower):
            if os.path.isdir(os.path.join(type_dir, asset)):
                found.append((asset_type, asset))
    return found


def plan_publish(scene_path, h_root, scratch_root, code, target=None):
    """Work out where a publish would go, without touching anything.

    target: optional (asset_type, asset) to publish to a different asset
    than the one whose folder the scene is in. 'asset' in the result is
    the target; 'source_asset'/'asset_project' stay the scene's own."""
    h_root, scratch_root = resolve_root(h_root), resolve_root(scratch_root)
    check_roots(h_root, scratch_root)
    ctx = asset_context(scene_path)
    if ctx["ext"] not in SCENE_EXTS:
        raise PublishError("Only .ma / .mb scenes can be published.")
    if not _same_path(ctx["root"], scratch_root):
        where = "the H drive" if _same_path(ctx["root"], h_root) else ctx["root"]
        raise PublishError(
            "This scene isn't on your scratch drive (%s), it's on %s.\n"
            "Work from scratch and publish from there." % (scratch_root, where))

    ctx["source_asset"] = (ctx["asset_type"], ctx["asset"])
    if target and tuple(target) != ctx["source_asset"]:
        # Different asset: publish into its scenes folder.
        ctx["asset_type"], ctx["asset"] = target
        ctx["rel_folder"] = [ctx["film"], "maya", "assets",
                             target[0], target[1], "scenes"]
        if not os.path.isdir(os.path.join(h_root, *ctx["rel_folder"][:5])):
            raise PublishError("No folder for asset '%s' on the H drive." % target[1])
    ctx["is_source_asset"] = (ctx["asset_type"], ctx["asset"]) == ctx["source_asset"]

    # Wherever the working file sits on scratch, the publish goes in the
    # person's own folder: <asset>\scenes\<login>\.
    login = who()
    h_folder = personal_folder(h_root, [ctx["film"], "maya", "assets",
                                        ctx["asset_type"], ctx["asset"]], login)
    versions = published_versions(h_folder, ctx["asset"], login, code)
    version = (versions[-1] + 1) if versions else 1
    name = published_name(ctx["asset"], login, code, version, ctx["ext"])
    ctx.update({
        "login": login,
        "code": code,
        "h_folder": h_folder,
        "version": version,
        "dest": os.path.join(h_folder, name),
    })
    return ctx


# ---------------------------------------------------------------------------
# Unassigned shaders (DECIDED 2026-10-19: no publish carries them, and Build
# clears them out of the way). Deliberately narrow so it's safe for rigs:
# only shading engines with no members, materials used by nothing else, and
# texture/utility nodes that feed only those. Never DAG nodes, anim curves
# or anything referenced. A fuller rig clean-up is its own job (OPEN).
# ---------------------------------------------------------------------------

_KEEP_SHADING = ("initialShadingGroup", "initialParticleSE", "lambert1",
                 "standardSurface1", "particleCloud1")
_DEFAULT_LISTS = ("defaultShaderList1", "defaultTextureList1",
                  "defaultRenderUtilityList1", "renderPartition", "lightLinker1")


def _shading_kind(node):
    classes = " ".join(cmds.getClassification(cmds.nodeType(node)) or [])
    return any(word in classes for word in ("shader", "texture", "utility"))


def _keepable(node):
    return (node in _KEEP_SHADING or ":" + node in _KEEP_SHADING
            or cmds.referenceQuery(node, isNodeReferenced=True)
            or cmds.lockNode(node, query=True, lock=True)[0])


def unused_shading_nodes(namespace=None):
    """Shading nodes nothing in the scene uses: shading groups with no
    members (plus their materialInfo), materials whose only shading groups
    are those (or that have none), and texture/utility nodes feeding only
    those. namespace limits it to nodes in that namespace (e.g. 'backpack')."""
    unused = set()
    for sg in cmds.ls(type="shadingEngine") or []:
        if _keepable(sg) or cmds.sets(sg, query=True):
            continue
        unused.add(sg)
        unused.update(cmds.listConnections(sg + ".message", type="materialInfo") or [])
    for material in cmds.ls(materials=True) or []:
        if _keepable(material):
            continue
        sgs = set(cmds.listConnections(material, source=False, destination=True,
                                       type="shadingEngine") or [])
        if sgs <= unused:
            unused.add(material)
    changed = True
    while changed:      # upstream nodes that feed only unused ones
        changed = False
        for node in list(unused):
            for up in set(cmds.listConnections(node, source=True, destination=False) or []):
                if up in unused or _keepable(up) or not _shading_kind(up):
                    continue
                downstream = [d for d in set(cmds.listConnections(up, source=False,
                                                                  destination=True) or [])
                              if d not in _DEFAULT_LISTS]
                if downstream and set(downstream) <= unused:
                    unused.add(up)
                    changed = True
    nodes = sorted(n for n in unused if cmds.objExists(n))
    if namespace:
        nodes = [n for n in nodes if n.lstrip(":").startswith(namespace + ":")]
    return nodes


class _WithoutUnusedShading(object):
    """While inside, unassigned shaders are deleted from the working scene,
    so a whole-scene export leaves them out; on the way out they're put back
    with Maya's undo. self.removed: what was left out."""

    def __enter__(self):
        self.removed = unused_shading_nodes()
        self._undo_was_on = cmds.undoInfo(query=True, state=True)
        if self.removed:
            cmds.undoInfo(state=True)
            cmds.undoInfo(openChunk=True, chunkName="pipeLeaveOutUnusedShading")
            try:
                cmds.delete(self.removed)
            finally:
                cmds.undoInfo(closeChunk=True)
        return self

    def __exit__(self, *exc):
        if self.removed:
            cmds.undo()
            cmds.undoInfo(state=self._undo_was_on)
            missing = [n for n in self.removed if not cmds.objExists(n)]
            if missing:
                raise PublishError(
                    "The publish worked, but these unused shaders weren't put back in your "
                    "scene: %s\nReopen your scene without saving to get them back."
                    % ", ".join(missing))
        return False


def copy_to_h_drive(scene_path, plan):
    """Copy the saved scene file to plan['dest'] and make it read-only."""
    if not os.path.isfile(scene_path):
        raise PublishError("Scene file not found on disk: %s" % scene_path)
    if os.path.exists(plan["dest"]):
        # Can only happen if someone published in between plan and copy.
        raise PublishError("%s already exists — try again." % plan["dest"])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])
    shutil.copy2(scene_path, plan["dest"])
    _lock(plan["dest"])


def namespaced_nodes():
    """Nodes in the scene with a namespace that the publish can rename:
    not from a reference, not locked, not Maya's own defaults."""
    found = []
    for node in cmds.ls(recursive=True) or []:
        short = node.split("|")[-1]
        if ":" not in short.lstrip(":"):
            continue
        if cmds.referenceQuery(node, isNodeReferenced=True):
            continue
        if cmds.lockNode(node, query=True, lock=True)[0]:
            continue
        found.append(node)
    return found


class _NoNamespaces(object):
    """While inside, every renameable namespaced node has its namespace
    taken off (backpack:backPack_geo -> backPack_geo), so what gets
    exported has clean names. On the way out every name is put back, found
    by node UUID, so the working scene ends exactly as it was. Nothing is
    deleted or merged. self.namespaces: the namespaces that were removed."""

    def __enter__(self):
        self.renamed = []
        self.namespaces = set()
        # Work by UUID: renaming one node can change another's path.
        for uuid in cmds.ls(namespaced_nodes(), uuid=True):
            node = cmds.ls(uuid, long=True)[0]
            short = node.split("|")[-1]
            self.namespaces.add(short.rsplit(":", 1)[0].lstrip(":"))
            cmds.rename(node, ":" + short.rsplit(":", 1)[1], ignoreShape=True)
            self.renamed.append((uuid, short))
        return self

    def __exit__(self, *exc):
        for uuid, short in reversed(self.renamed):
            node = cmds.ls(uuid)
            if node:
                cmds.rename(node[0], ":" + short.lstrip(":"), ignoreShape=True)
        return False


# Every rig publish must contain this set, made by hand by the rigger: it
# names the geometry a shot publish caches (spec §4 "What an animation
# publish puts out" -> cache_SET).
CACHE_SET = "cache_SET"
RIG_CODE = "rig"
MODEL_CODE = "model"
GEOMETRY_TYPES = ("mesh", "nurbsSurface", "subdiv")


def _under(node, roots):
    """True if node is one of roots or below one of them."""
    path = (cmds.ls(node, long=True) or [""])[0]
    for root in roots:
        root_path = (cmds.ls(root, long=True) or [""])[0]
        if root_path and (path == root_path or path.startswith(root_path + "|")):
            return True
    return False


def check_cache_set(objects):
    """A Rigging publish needs exactly one cache_SET (made by the rigger,
    never by the tool) holding geometry, all of it inside what's being
    published. Returns the set's name; raises PublishError explaining what
    to fix."""
    how = ("\n\nRig publishes need a %s: an object set listing the geometry a "
           "shot publish will cache. Create it by hand (select the render "
           "geometry, Create > Sets > Set, name it %s), then publish again."
           % (CACHE_SET, CACHE_SET))
    sets = [s for s in cmds.ls(type="objectSet") or []
            if s.split(":")[-1] == CACHE_SET
            and not cmds.referenceQuery(s, isNodeReferenced=True)]
    if not sets:
        raise PublishError("This rig has no %s." % CACHE_SET + how)
    if len(sets) > 1:
        raise PublishError("This scene has more than one %s (%s). Keep just one."
                           % (CACHE_SET, ", ".join(sets)))
    cache_set = sets[0]
    members = cmds.sets(cache_set, query=True) or []
    if not members:
        raise PublishError("%s is empty. Add the geometry to cache to it." % cache_set + how)
    geometry = []
    for m in members:
        if cmds.nodeType(m) in GEOMETRY_TYPES:
            geometry.append(m)
        else:
            geometry += cmds.listRelatives(m, allDescendents=True, fullPath=True,
                                           type=GEOMETRY_TYPES) or []
    if not geometry:
        raise PublishError("%s has no geometry in it (only %s). Add the meshes to cache."
                           % (cache_set, ", ".join(members[:5])) + how)
    if objects:
        outside = [m for m in members if not _under(m, objects)]
        if outside:
            raise PublishError(
                "%s holds things that aren't in this publish: %s\n"
                "Publish the whole rig (or include them), or take them out of the set."
                % (cache_set, ", ".join(outside[:5])))
    return cache_set


# Script nodes run code when a scene opens, which is how Maya scene viruses
# spread (spec §4 "Shot (animation) publish v0", item 8: on 2026-10-15 a
# student scene carried maya_secure_system). A published file reaches the
# shared H drive and every shot built from it, so publishing refuses any
# script node but Maya's own two, and those two only with ordinary MEL in
# them.
STANDARD_SCRIPT_NODES = ("uiConfigurationScriptNode", "sceneConfigurationScriptNode")
SUSPICIOUS_SCRIPT_TEXT = re.compile(
    r"python\s*\(|\bimport\s+\w|exec\s*\(|eval\s*\(|base64|b64decode|zlib|"
    r"userSetup|scriptJob|maya_secure_system|vaccine|leukocyte|fuckVirus",
    re.IGNORECASE)


def check_script_nodes():
    """Refuse a scene with a script node that isn't Maya's own (in this
    scene or in anything it references). Raises PublishError naming each
    node and how to get rid of it."""
    bad = []
    for node in cmds.ls(type="script") or []:
        short = node.split("|")[-1].split(":")[-1]
        code = "%s\n%s" % (cmds.getAttr(node + ".before") or "",
                           cmds.getAttr(node + ".after") or "")
        if short in STANDARD_SCRIPT_NODES and not SUSPICIOUS_SCRIPT_TEXT.search(code):
            continue
        where = ""
        if cmds.referenceQuery(node, isNodeReferenced=True):
            where = " (from the reference %s)" % os.path.basename(
                cmds.referenceQuery(node, filename=True, withoutCopyNumber=True))
        bad.append(node + where)
    if bad:
        raise PublishError(
            "This scene contains script nodes, which run code when the scene is "
            "opened, so it can't be published:\n  %s\n\n"
            "Scene viruses hide in script nodes, and a publish goes to the shared "
            "H drive and into everyone's shots. If you didn't add these on purpose, "
            "delete them (Windows > General Editors > Expression Editor > Select "
            "Filter > By Script Node Name), save, and publish again. If one comes "
            "from a reference, fix that file first. Ask your teacher if you're unsure."
            % "\n  ".join(bad))


def export_to_h_drive(objects, plan):
    """Export only the given objects (and their children) to plan['dest'].
    objects empty = the whole scene. Published files never carry a
    namespace (spec §3i); the working scene isn't changed."""
    missing = [o for o in objects if not cmds.objExists(o)]
    if missing:
        raise PublishError("Not in the scene any more: %s" % ", ".join(missing))
    if os.path.exists(plan["dest"]):
        raise PublishError("%s already exists — try again." % plan["dest"])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])
    file_type = "mayaAscii" if plan["ext"] == ".ma" else "mayaBinary"
    selection = cmds.ls(selection=True)
    uuids = cmds.ls(objects, uuid=True) if objects else []
    try:
        with _NoNamespaces() as clean:
            if objects:
                cmds.select(cmds.ls(uuids), replace=True)
                if plan.get("cache_set_uuid"):
                    # The set itself, not its members (a rig's cache_SET).
                    cmds.select(cmds.ls(plan["cache_set_uuid"]), add=True, noExpand=True)
                cmds.file(plan["dest"], exportSelected=True, type=file_type,
                          constructionHistory=True, channels=True, constraints=True,
                          expressions=True, shader=True, preserveReferences=True,
                          force=True)
            else:
                # Whole scene: everything except unassigned shaders.
                with _WithoutUnusedShading() as unused:
                    cmds.file(plan["dest"], exportAll=True, type=file_type,
                              preserveReferences=True, force=True)
                plan["unused_shading_left_out"] = unused.removed
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    _lock(plan["dest"])
    plan["namespaces_removed"] = sorted(clean.namespaces)


# ---------------------------------------------------------------------------
# Pipe group (spec §4 item 6a "Model publish clean-up + pipe group",
# DECIDED 2026-10-19): every model publish is wrapped in <asset>_<code>_GRP,
# which carries the publish's identity. It replaces the publishInfo node.
# ---------------------------------------------------------------------------

PIPE_ATTR_PREFIX = "pipe_"
ID_ATTR = PIPE_ATTR_PREFIX + "sgAssetId"


def pipe_group_name(asset, code):
    return "%s_%s_GRP" % (asset, code)


def is_pipe_group(node):
    return bool(cmds.objExists(node) and cmds.attributeQuery(ID_ATTR, node=node, exists=True))


def artist_name(login):
    """The person's name from ShotGrid, found by RMIT ID (sg_rmit_id) or
    login. "" if ShotGrid can't say; the publish doesn't depend on it."""
    try:
        sg = _shotgrid().get_connection()
        for field in ("sg_rmit_id", "login"):
            user = sg.find_one("HumanUser", [[field, "is", login]], ["name"])
            if user:
                return user["name"] or ""
    except Exception:
        pass
    return ""


def pipe_group_info(plan, scene_path):
    """What the pipe group records, in the order it's added."""
    return [
        ("sgAssetId", (plan.get("sg_asset") or {}).get("id") or 0),
        ("asset", plan["asset"]),
        ("assetType", plan["asset_type"]),
        ("department", plan["code"]),
        ("version", plan["version"]),
        ("artistId", plan["login"]),
        ("artistName", artist_name(plan["login"])),
        ("published", datetime.now().isoformat(timespec="seconds")),
        ("sourceScene", os.path.normpath(scene_path)),
    ]


def _stamp(group, info):
    for name, value in info:
        attr = PIPE_ATTR_PREFIX + name
        if isinstance(value, int):
            cmds.addAttr(group, longName=attr, attributeType="long")
            cmds.setAttr("%s.%s" % (group, attr), value)
        else:
            cmds.addAttr(group, longName=attr, dataType="string")
            cmds.setAttr("%s.%s" % (group, attr), value, type="string")
        cmds.setAttr("%s.%s" % (group, attr), lock=True)


def _model_roots(objects):
    """The transforms a model publish takes: the given ones (nothing given
    = every top-level object except Maya's default cameras), without any
    that sit below another one, and with an existing pipe group swapped for
    its contents (republishing a scene built from a publish)."""
    if objects:
        nodes = cmds.ls(objects, long=True, type="transform") or []
    else:
        nodes = [n for n in cmds.ls(assemblies=True, long=True) or []
                 if not any(cmds.camera(s, query=True, startupCamera=True)
                            for s in cmds.listRelatives(n, shapes=True, fullPath=True,
                                                        type="camera") or [])]
    roots = []
    for node in nodes:
        if is_pipe_group(node):
            roots += cmds.listRelatives(node, children=True, fullPath=True,
                                        type="transform") or []
        else:
            roots.append(node)
    roots = [r for r in roots if not any(r.startswith(o + "|") for o in roots if o != r)]
    if not roots:
        raise PublishError("There's nothing to publish: no objects in the scene/selection.")
    return roots


def export_model_to_h_drive(objects, plan, scene_path):
    """Model publish: the published file holds a clean copy of the model,
    transforms frozen and history deleted, inside <asset>_model_GRP with
    the publish's identity stamped on it. Done on duplicates; the working
    scene ends exactly as it was (names, transforms, history, selection).
    objects empty = every top-level object."""
    missing = [o for o in objects if not cmds.objExists(o)]
    if missing:
        raise PublishError("Not in the scene any more: %s" % ", ".join(missing))
    if os.path.exists(plan["dest"]):
        raise PublishError("%s already exists — try again." % plan["dest"])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])
    file_type = "mayaAscii" if plan["ext"] == ".ma" else "mayaBinary"
    group_name = pipe_group_name(plan["asset"], plan["code"])
    info = pipe_group_info(plan, scene_path)
    selection = cmds.ls(selection=True)
    uuids = cmds.ls(objects, uuid=True) if objects else []
    moved, made = [], []      # (uuid, name) renamed out of the way; temp nodes
    try:
        with _NoNamespaces() as clean:
            try:
                # By UUID: renaming things out of the way changes paths.
                roots = cmds.ls(_model_roots(cmds.ls(uuids) if objects else []), uuid=True)
                # The copies take the originals' names, so the published
                # file reads the same as the scene; the originals step aside.
                for node in cmds.ls(group_name, long=True) or []:
                    moved.append((cmds.ls(node, uuid=True)[0], node.split("|")[-1]))
                    cmds.rename(node, "pipeTmp_" + node.split("|")[-1])
                copies = []
                for uuid in roots:
                    root = cmds.ls(uuid, long=True)[0]
                    short = root.split("|")[-1]
                    copy = cmds.duplicate(root, returnRootsOnly=True)[0]
                    made.append(cmds.ls(copy, uuid=True)[0])
                    moved.append((uuid, short))
                    cmds.rename(cmds.ls(uuid)[0], "pipeTmp_" + short)
                    copy = cmds.rename(copy, short)
                    if cmds.listRelatives(copy, parent=True):
                        copy = cmds.parent(copy, world=True)[0]
                    copies.append(cmds.ls(copy, uuid=True)[0])
                copy_nodes = cmds.ls(copies, long=True)
                everything = copy_nodes + (cmds.listRelatives(
                    copy_nodes, allDescendents=True, fullPath=True) or [])
                cmds.delete(everything, constructionHistory=True)
                leftovers = [s for s in cmds.ls(everything, shapes=True, long=True) or []
                             if cmds.objExists(s) and cmds.getAttr(s + ".intermediateObject")]
                if leftovers:
                    cmds.delete(leftovers)     # e.g. "Orig" shapes from deformers
                cmds.makeIdentity(copy_nodes, apply=True, translate=True, rotate=True,
                                  scale=True, normal=0, preserveNormals=True)
                group = cmds.group(empty=True, world=True, name=group_name)
                made.append(cmds.ls(group, uuid=True)[0])
                cmds.parent(cmds.ls(copies, long=True), group)
                _stamp(group, info)
                cmds.select(group, replace=True)
                cmds.file(plan["dest"], exportSelected=True, type=file_type,
                          constructionHistory=True, channels=True, constraints=True,
                          expressions=True, shader=True, preserveReferences=True,
                          force=True)
            finally:
                # Copies and group gone, originals back to their names,
                # before the namespaces are put back.
                if cmds.ls(made):
                    cmds.delete(cmds.ls(made))
                for uuid, short in reversed(moved):
                    if cmds.ls(uuid):
                        cmds.rename(cmds.ls(uuid)[0], short)
    finally:
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    _lock(plan["dest"])
    plan["namespaces_removed"] = sorted(clean.namespaces)
    plan["pipe_group"] = group_name


def _lock(path):
    # "Locked" for now = read-only file attribute (spec §4: locking OPEN).
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


# ---------------------------------------------------------------------------
# ShotGrid — film folder -> Project (pipeline.json), asset folder -> Asset
# ---------------------------------------------------------------------------

def _match_key(name):
    """Folder names are camelCase versions of ShotGrid codes (§3f), so
    compare with case, spaces and punctuation stripped:
    'Backpack' == 'backpack', 'bakedBeans_Can' == 'bakedBeansCan'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_film_config(h_root, film):
    path = os.path.join(h_root, film, FILM_CONFIG_NAME)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        raise PublishError(
            "No %s found in the film folder on the H drive:\n%s\n"
            "It says which ShotGrid project this film belongs to."
            % (FILM_CONFIG_NAME, path))


def _shotgrid():
    try:
        import shotgridConnect
    except ImportError:
        raise PublishError("shotgridConnect isn't installed (it comes with shotSub).")
    if not shotgridConnect.has_known_identity():
        raise PublishError(
            "ShotGrid doesn't know who you are yet.\n"
            "Open shotSub once and enter your student ID, then publish again.")
    return shotgridConnect


def find_shotgrid_asset(plan, h_root):
    """Return the ShotGrid Asset whose code matches the asset folder."""
    film_config = load_film_config(h_root, plan["film"])
    sgc = _shotgrid()
    sg = sgc.get_connection()
    project = {"type": "Project", "id": film_config["shotgrid_project_id"]}
    assets = sg.find("Asset", [["project", "is", project]], ["id", "code"])
    matches = [a for a in assets if _match_key(a["code"]) == _match_key(plan["asset"])]
    if not matches:
        raise PublishError(
            "No ShotGrid asset matches the folder '%s' in %s."
            % (plan["asset"], film_config.get("shotgrid_project_name", project)))
    if len(matches) > 1:
        raise PublishError(
            "More than one ShotGrid asset matches '%s': %s"
            % (plan["asset"], ", ".join(a["code"] for a in matches)))
    return matches[0]


# ---------------------------------------------------------------------------
# Playblast (shotSub-style JPEG frames, encoded + uploaded by shotgridConnect)
# ---------------------------------------------------------------------------

def _model_panel():
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    visible = [p for p in (cmds.getPanel(visiblePanels=True) or [])
               if cmds.getPanel(typeOf=p) == "modelPanel"]
    return visible[0] if visible else None


def playblast_frames(plan, frame_count, objects=None, camera=None):
    """Playblast frame_count frames from the playback start (None = the
    whole playback range) into
    <scene's asset project>/images/publish/<asset>/<code>_v###/ on scratch.
    If objects are given, only they are shown (isolate select). If camera
    is given, the playblast looks through it.
    Returns (folder, files)."""
    version_name = "%s_v%03d" % (plan["code"], plan["version"])
    folder = os.path.join(plan["asset_project"], "images", "publish",
                          plan["asset"], version_name)
    if os.path.isdir(folder):
        shutil.rmtree(folder)       # leftovers from a failed attempt
    os.makedirs(folder)

    start = int(cmds.playbackOptions(query=True, minTime=True))
    if frame_count is None:
        end = int(cmds.playbackOptions(query=True, maxTime=True))
    else:
        end = start + max(1, frame_count) - 1
    width = cmds.getAttr("defaultResolution.width")
    height = cmds.getAttr("defaultResolution.height")
    panel = _model_panel() if (objects or camera) else None
    selection = cmds.ls(selection=True)
    previous_camera = None
    isolated = False
    try:
        if panel and camera:
            previous_camera = cmds.modelPanel(panel, query=True, camera=True)
            cmds.modelPanel(panel, edit=True, camera=camera)
        elif panel:
            cmds.select(objects, replace=True)
            cmds.isolateSelect(panel, state=True)
            isolated = True
            cmds.isolateSelect(panel, addSelected=True)
        # Nothing selected while playblasting, so the ShotGrid movie doesn't
        # show the green selection highlight. Put back afterwards.
        cmds.select(clear=True)
        cmds.playblast(
            format="image", compression="jpg", quality=90, percent=100,
            filename=os.path.join(folder, "%s_%s" % (plan["asset"], version_name)),
            startTime=start, endTime=end,
            framePadding=4, sequenceTime=False, clearCache=True, viewer=False,
            showOrnaments=False, offScreen=True, forceOverwrite=True,
            widthHeight=[width, height])
        files = sorted(glob.glob(os.path.join(folder, "*.jpg")))
        if not files:
            raise PublishError("The playblast didn't produce any frames.")
    except Exception:
        # e.g. cancelled half way: no frames left on scratch.
        remove_frames(folder, plan["asset_project"])
        raise
    finally:
        if previous_camera:
            cmds.modelPanel(panel, edit=True, camera=previous_camera)
        elif isolated:
            cmds.isolateSelect(panel, state=False)
        cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
    return folder, files


# ---------------------------------------------------------------------------
# One-click publish
# ---------------------------------------------------------------------------

def scene_audio(start_frame):
    """(audio file, offset in seconds) for the publish movie, or (None, 0.0).

    Lip sync needs sound in the review movie (spec §4 "Final publish movie
    for the edit"), so it works the way shotSub does: the sound shown on
    Maya's time slider, offset so it lines up with the first playblast
    frame. Without the time slider (headless, later a farm), a scene with
    exactly one sound node uses that one."""
    node = None
    if not cmds.about(batch=True):
        try:
            import maya.mel as mel
            slider = mel.eval("$tmpVar=$gPlayBackSlider")
            node = cmds.timeControl(slider, query=True, sound=True) if slider else None
        except Exception:
            node = None
    if not node:
        sounds = cmds.ls(type="audio") or []
        node = sounds[0] if len(sounds) == 1 else None
    if not node:
        return None, 0.0
    path = cmds.getAttr(node + ".filename") or ""
    if path and not os.path.isabs(path):
        path = cmds.workspace(expandName=path)
    if not os.path.isfile(path):
        return None, 0.0
    offset_frames = cmds.getAttr(node + ".offset")
    return path, (offset_frames - start_frame) / _scene_fps()


# ---------------------------------------------------------------------------
# Approval (spec §4 item 6a, DECIDED 2026-10-19): a shot can only be
# pipe-published after shotSub review gets it Approved in ShotGrid, and what
# it may publish depends on the task the approval is on: Layout -> the
# camera, Blocking -> keys + full file, Final -> also caches.
# ---------------------------------------------------------------------------

APPROVED = "apr"


def approved_tasks(sg_entity):
    """{task name (lower case): that Task} for every Task on the Shot that
    has an Approved Version linked to it. Versions with no task (from
    before shotSub linked them) don't count."""
    sg = _shotgrid().get_connection()
    versions = sg.find("Version", [["entity", "is", {"type": sg_entity.get("type", "Shot"),
                                                     "id": sg_entity["id"]}],
                                   ["sg_status_list", "is", APPROVED]],
                       ["sg_task", "sg_task.Task.content"])
    found = {}
    for v in versions:
        name = (v.get("sg_task.Task.content") or "").strip().lower()
        if name and v.get("sg_task"):
            found[name] = v["sg_task"]
    return found


def task_on(sg_entity, name):
    """The Task called name (any case) on a Shot/Asset, or None."""
    sg = _shotgrid().get_connection()
    for task in sg.find("Task", [["entity", "is", {"type": sg_entity.get("type", "Shot"),
                                                   "id": sg_entity["id"]}]], ["content"]):
        if (task["content"] or "").strip().lower() == name.lower():
            return {"type": "Task", "id": task["id"], "content": task["content"]}
    return None


def link_version_to_task(plan, task):
    """Point the publish's ShotGrid Version at its Task. Best effort: the
    publish itself is already done."""
    version = plan.get("sg_version")
    if not (version and task):
        return
    try:
        _shotgrid().get_connection().update(
            "Version", version["id"], {"sg_task": {"type": "Task", "id": task["id"]}})
    except Exception as e:
        plan.setdefault("warnings", []).append(
            "The ShotGrid Version wasn't linked to the %s task: %s" % (task.get("content"), e))


def upload_with_audio(sg, plan, audio_path, audio_offset, *args, **kwargs):
    """upload_playblast with the sound added when there is one. An older
    installed shotgridConnect (before shotSub's audio support) doesn't take
    audio: publish without it and warn, rather than failing the upload."""
    if audio_path:
        import inspect
        params = inspect.signature(sg.upload_playblast).parameters
        if "audio_path" in params:
            kwargs.update(audio_path=audio_path, audio_offset_seconds=audio_offset)
        else:
            plan.setdefault("warnings", []).append(
                "The ShotGrid movie has no sound: this machine's shotgridConnect is "
                "older than shotSub's audio support. Reinstall mpToolSet to fix.")
    return sg.upload_playblast(*args, **kwargs)


def publish(scene_path, h_root, scratch_root, code, frame_count=2, notes="",
            objects=None, target=None):
    """Playblast -> H drive -> ShotGrid Version on the Asset.

    objects: publish only these (exported); empty/None = the whole scene
    file. target: (asset_type, asset) to publish to a different asset than
    the scene's own folder.

    Anything that can fail cleanly (ShotGrid lookup, playblast) happens
    before the H-drive write. Returns the plan dict plus 'sg_asset',
    'sg_version' and 'sg_error' (set if only the ShotGrid upload failed,
    after the H-drive write succeeded)."""
    h_root = resolve_root(h_root)
    check_script_nodes()
    plan = plan_publish(scene_path, h_root, scratch_root, code, target=target)
    plan["objects"] = list(objects or [])
    if code == RIG_CODE:
        # Checked before anything is made or uploaded.
        plan["cache_set"] = check_cache_set(plan["objects"])
        plan["cache_set_uuid"] = cmds.ls(plan["cache_set"], uuid=True)[0]
    plan["sg_asset"] = find_shotgrid_asset(plan, h_root)
    check_rv()
    plan["frames_folder"], files = playblast_frames(plan, frame_count, plan["objects"])

    plan["namespaces_removed"] = []
    try:
        if code == MODEL_CODE:
            # Always a clean copy in its pipe group (spec §4 item 6a).
            export_model_to_h_drive(plan["objects"], plan, scene_path)
        elif plan["objects"] or namespaced_nodes() or unused_shading_nodes():
            # Selected objects, or a whole scene that needs its namespaces
            # or unassigned shaders taken off: export. A clean whole scene
            # is copied as it is.
            export_to_h_drive(plan["objects"], plan)
        else:
            copy_to_h_drive(scene_path, plan)
    except Exception:
        # Nothing was published, so this attempt's frames are no use:
        # don't leave them on scratch.
        remove_frames(plan["frames_folder"], plan["asset_project"])
        raise
    if plan["namespaces_removed"]:
        plan.setdefault("warnings", []).append(
            "Namespace %s taken off in the published file (your scene is unchanged)."
            % ", ".join("'%s:'" % n for n in plan["namespaces_removed"]))
    if plan.get("unused_shading_left_out"):
        plan.setdefault("warnings", []).append(
            "Unused shaders left out of the published file (your scene is unchanged): %s"
            % ", ".join(plan["unused_shading_left_out"]))

    what = ("%d object(s): %s" % (len(plan["objects"]), ", ".join(plan["objects"]))
            if plan["objects"] else "whole scene")
    note = "Published %s v%03d to the H drive:\n%s\n(from %s, %s)" % (
        code, plan["version"], plan["dest"], os.path.basename(scene_path), what)
    if notes.strip():
        # The student's own words first, the file details underneath.
        note = notes.strip() + "\n\n---\n" + note
    plan["sg_version"] = plan["sg_error"] = None
    rvio = find_rvio()
    plan["movie_warning"] = None if rvio else (
        "RV's rvio wasn't found on this machine, so ShotGrid got a thumbnail "
        "but no playable movie.")
    plan["audio"], audio_offset = scene_audio(int(cmds.playbackOptions(query=True, minTime=True)))
    try:
        plan["sg_version"] = upload_with_audio(
            _shotgrid(), plan, plan["audio"], audio_offset,
            "Asset", plan["sg_asset"]["id"], plan["frames_folder"],
            files=files, notes=note, fps=_scene_fps(), rvio_path=rvio,
            machine_diagnostic=plan["movie_warning"])
    except Exception as e:     # H-drive copy already done; report, don't lose it
        plan["sg_error"] = str(e)
    else:
        if not note_no_movie(plan):
            # ShotGrid has the frames/movie now, so the local copies on
            # scratch are no longer needed. Kept if the upload failed or
            # the movie couldn't be made.
            remove_frames(plan["frames_folder"], plan["asset_project"])
    return plan


def check_rv():
    """Refuse to publish while RV can't make movies (e.g. not signed in to
    ShotGrid): caught before the playblast and any H-drive write, so the
    student signs in and publishes again instead of ShotGrid silently
    getting a thumbnail only. No RV at all stays a warning, as before."""
    rvio = find_rvio()
    sgc = _shotgrid()
    if rvio and hasattr(sgc, "check_rvio"):
        problem = sgc.check_rvio(rvio)
        if problem:
            raise PublishError(problem)


def note_no_movie(plan):
    """If ShotGrid got no movie, say why in plan['movie_warning'] and
    return True."""
    problem = (plan.get("sg_version") or {}).get("movie_problem")
    if problem:
        plan["movie_warning"] = ("ShotGrid got a thumbnail only, no movie. %s\n"
                                 "The frames are kept in %s." % (problem, plan["frames_folder"]))
    return bool(problem)


def remove_frames(frames_folder, asset_project):
    """Delete a publish's local frames folder, then any parent folders it
    leaves empty, up to (not including) the asset project's images folder."""
    shutil.rmtree(frames_folder, ignore_errors=True)
    stop = os.path.normcase(os.path.join(asset_project, "images"))
    parent = os.path.dirname(frames_folder)
    while os.path.normcase(parent).startswith(stop + os.sep) and not os.listdir(parent):
        os.rmdir(parent)
        parent = os.path.dirname(parent)


def find_rvio():
    """RV's rvio, which shotgridConnect needs to encode the movie (it never
    looks for it itself). Same search order as shotSub's
    find_rv_executable(): SHOTSUB_RV_HOME, PATH, the Windows registry, then
    the usual install folders; newest RV wins. "" if not found."""
    exe = "rvio.exe" if os.name == "nt" else "rvio"
    env_home = os.environ.get("SHOTSUB_RV_HOME")
    if env_home:
        for candidate in (os.path.join(env_home, exe), os.path.join(env_home, "bin", exe)):
            if os.path.isfile(candidate):
                return candidate
    found = shutil.which("rvio")
    if found:
        return found

    candidates = []
    for install_root in _rv_install_roots_from_registry():
        for candidate in (os.path.join(install_root, exe),
                          os.path.join(install_root, "bin", exe)):
            if os.path.isfile(candidate):
                candidates.append(candidate)
    for pattern in (r"C:\Program Files\Autodesk\RV-*\bin\rvio.exe",
                    r"C:\Program Files\Shotgun\RV-*\bin\rvio.exe",
                    r"C:\Program Files\ShotGrid\RV-*\bin\rvio.exe",
                    "/Applications/RV*.app/Contents/MacOS/rvio",
                    "/Applications/Autodesk/RV-*.app/Contents/MacOS/rvio"):
        candidates.extend(glob.glob(pattern))
    if not candidates:
        return ""

    def version_key(path):
        m = re.search(r"RV-([\d.]+)", path)
        return tuple(int(p) for p in m.group(1).split(".") if p) if m else (0,)
    return sorted(candidates, key=version_key)[-1]


def _rv_install_roots_from_registry():
    try:
        import winreg
    except ImportError:
        return []
    roots = []
    for hive, key_path in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                name = winreg.QueryValueEx(sub, "DisplayName")[0]
                if re.search(r"\bRV\b|Shotgun|ShotGrid|Flow Production Tracking", name, re.I):
                    location = winreg.QueryValueEx(sub, "InstallLocation")[0]
                    if location:
                        roots.append(location)
            except OSError:
                continue
    return roots


def _scene_fps():
    rates = {"film": 24, "pal": 25, "ntsc": 30, "game": 15,
             "show": 48, "palf": 50, "ntscf": 60}
    unit = cmds.currentUnit(query=True, time=True)
    if unit in rates:
        return rates[unit]
    m = re.match(r"^([\d.]+)fps$", unit)
    return float(m.group(1)) if m else 24

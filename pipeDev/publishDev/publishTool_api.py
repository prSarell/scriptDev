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
import tempfile
from datetime import datetime

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# Departments — (tab label, code). The code is used in published filenames
# and as the department subfolder in a shot (§3i). Order = tab order.
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    ("Modeling", "model"),
    ("Environment", "env"),     # spec §4c: publishTool_env
    ("Rigging",  "rig"),
    ("Anim",     "anim"),
    ("Creature", "creature"),
    ("LookDev",  "lookDev"),
    ("FX",       "fx"),
    ("Lighting", "lighting"),   # was Render; Previs dropped (user, 2026-10-28)
]

# Film folders are named <FILM>_<TYPE>, TYPE a three-letter code (§3f).
FILM_FOLDER_RE = re.compile(r"^[A-Za-z0-9]+_[A-Z]{3}$")

SCENE_EXTS = (".ma", ".mb")
CONFIG_NAME = "pipeline_config.json"     # per machine, Maya prefs folder
FILM_CONFIG_NAME = "pipeline.json"       # per film, in the H-drive film folder


class PublishError(Exception):
    """A problem the student can fix (unsaved scene, wrong folder...)."""


class PublishCancelled(PublishError):
    """The student watched the movie and chose not to publish."""


# ---------------------------------------------------------------------------
# Settings — where the H drive is. Drive letters differ between setups
# (home test rig, RMIT), so it's a setting, never hard-coded (§3h).
# ---------------------------------------------------------------------------

def _config_path():
    return os.path.join(cmds.internalVar(userPrefDir=True), CONFIG_NAME)


def _carry_forward(path):
    """A new Maya version starts with empty prefs (maya\\2027\\prefs), so the
    first time the pipe runs there it copies the settings from the newest
    other version's prefs (the move to 2027, 2026-10-28). Only for the real
    prefs location (<maya>\\<version>\\prefs). Returns True if copied."""
    prefs = os.path.dirname(path)
    version_dir = os.path.dirname(prefs)
    if os.path.basename(prefs).lower() != "prefs" or not os.path.basename(version_dir).isdigit():
        return False
    others = [p for p in glob.glob(os.path.join(os.path.dirname(version_dir), "*", "prefs", CONFIG_NAME))
              if os.path.basename(os.path.dirname(os.path.dirname(p))).isdigit()
              and not _same_path(p, path)]
    if not others:
        return False
    try:
        shutil.copy2(max(others, key=os.path.getmtime), path)
    except (IOError, OSError):
        return False
    return True


def load_config():
    path = _config_path()
    if not os.path.isfile(path):
        _carry_forward(path)
    try:
        with open(path, "r") as f:
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
# whose Windows login isn't their RMIT one; failing that "shotgrid_as" (the
# Project Tool's RMIT ID setting), so staff set their e-number once and it
# names their folders too (user, 2026-10-28: "scout" read as the character).
PUBLISH_AS = "publish_as"
SHOTGRID_AS = "shotgrid_as"
# Every asset's scenes folder has these working folders, each holding one
# folder per person (scenes\model\s1234567\): model, rig and lookdev
# iteration and development (user, 2026-10-28). Named by department code.
# Publishes still go in scenes\<login>\.
WORK_FOLDERS = ("model", "rig", "lookDev")
# Every shot's scenes folder has the same, for shot departments
# (scenes\anim\s1234567\), so a shot can be built for rendering (user,
# 2026-10-28).
SHOT_WORK_FOLDERS = ("layout", "anim", "fx", "lighting")


def clean_login(name):
    """Logins go in file names between underscores: letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def who():
    """The login publishes are made under, e.g. 's1234567'."""
    import getpass
    config = load_config()
    login = clean_login(config.get(PUBLISH_AS, "")) or clean_login(config.get(SHOTGRID_AS, ""))
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


def set_maya_project(path):
    """Set the Maya project the way File > Set Project does, for the Build
    and Project tools. A bare `workspace -openWorkspace` (what both used
    to do) leaves File > Open in the old project, and the project isn't in
    Recent Projects or remembered next time, so it looked like it hadn't
    been set (user, 2026-10-21). A folder without a workspace.mel gets
    Maya's default one, as Set Project does. Raises PublishError if the
    project didn't change."""
    import maya.mel as mel
    if not os.path.isdir(path):
        raise PublishError("Can't set the Maya project: %s isn't there." % path)
    mel_path = os.path.normpath(path).replace("\\", "/")
    if cmds.about(batch=True):
        # No UI (mayapy): Set Project's file-browser and menu steps don't apply.
        if not os.path.isfile(os.path.join(path, "workspace.mel")):
            mel.eval('source "setProject.mel"')
            mel.eval('sp_createAndSetDefaultProject("%s", false)' % mel_path)
        cmds.workspace(mel_path, openWorkspace=True)
    else:
        mel.eval('setProject "%s"' % mel_path)
    now = cmds.workspace(query=True, rootDirectory=True) or ""
    if not _same_path(now, path):
        raise PublishError("Maya didn't switch project (it's still %s). Try File > Set "
                           "Project and pick %s." % (now, path))
    return path


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


# ---------------------------------------------------------------------------
# The open scene vs the Maya project (user, 2026-10-28: "I keep changing the
# project expecting that to effect where the build tool is building from and
# where the publish tool is publishing to ... that's why I keep sending stuff
# to the wrong place"). Build and Publish go by the open scene; when it's in
# a different shot or asset from the Maya project they say so loudly, and
# let the artist carry on.
# ---------------------------------------------------------------------------

def pipe_place(path):
    """The shot or asset folder a path is in (a scene, or a project folder
    itself): {"film", "kind" ("shot"/"asset"), "group", "name", "folder"},
    or None outside the pipe's <film>\\maya\\sequences|assets layout."""
    if not path:
        return None
    try:
        root, rel = find_film_folder(os.path.normpath(path))
    except PublishError:
        return None
    if len(rel) < 5 or rel[1].lower() != "maya" or rel[2].lower() not in ("sequences", "assets"):
        return None
    return {"film": rel[0], "kind": "shot" if rel[2].lower() == "sequences" else "asset",
            "group": rel[3], "name": rel[4], "folder": os.path.join(root, *rel[:5])}


def place_label(place):
    return "%s %s" % (place["kind"], place["name"])


def project_mismatch():
    """{"scene": place, "project": place} when the open scene is in one shot
    or asset and the Maya project is set to another, else None. Untitled
    scenes, and scenes or projects outside the pipe, never count."""
    scene = cmds.file(query=True, sceneName=True) or ""
    project = cmds.workspace(query=True, rootDirectory=True) or ""
    s, p = pipe_place(scene), pipe_place(project)
    # The same shot or asset on another drive (a shot carried to a new
    # scratch drive) isn't a mismatch: Build and Publish follow the scene.
    same = lambda a, b: all(a[k].lower() == b[k].lower() for k in ("film", "kind", "group", "name"))
    if not (s and p) or same(s, p):
        return None
    return {"scene": s, "project": p}


def mismatch_text(mismatch, verb):
    """The banner: 'Your open scene is in shot SEQ010_140, but your Maya
    project is asset shed. <verb> uses the open scene: shot SEQ010_140.'"""
    return ("Your open scene is in <b>%s</b>, but your Maya project is <b>%s</b>.<br>"
            "%s uses the open scene: <b>%s</b>." % (
                place_label(mismatch["scene"]), place_label(mismatch["project"]),
                verb, place_label(mismatch["scene"])))


def latest_scene(project):
    """The newest .ma/.mb under a project's scenes folder, or None."""
    found = []
    for dirpath, _, filenames in os.walk(os.path.join(project, "scenes")):
        found += [os.path.join(dirpath, n) for n in filenames
                  if os.path.splitext(n)[1].lower() in (".ma", ".mb")]
    return max(found, key=os.path.getmtime) if found else None


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


def work_folder(project, code, login):
    """Where one person's working scenes go in an asset or shot project:
    scenes\\<code>\\<login> for the WORK_FOLDERS departments (model, rig,
    lookDev) and SHOT_WORK_FOLDERS (layout, anim, fx, render), else
    scenes\\<login>."""
    if code in WORK_FOLDERS + SHOT_WORK_FOLDERS:
        return os.path.join(project, "scenes", code, login)
    return os.path.join(project, "scenes", login)


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


def list_films(root):
    """Film folders (<FILM>_<TYPE>) under a drive root."""
    if not root or not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root)
                  if FILM_FOLDER_RE.match(n) and os.path.isdir(os.path.join(root, n)))


def list_shots(root, film):
    """[(sequence, shot), ...] from <root>/<film>/maya/sequences."""
    seq_dir = os.path.join(root, film, "maya", "sequences")
    shots = []
    if not os.path.isdir(seq_dir):
        return shots
    for seq in sorted(os.listdir(seq_dir)):
        seq_path = os.path.join(seq_dir, seq)
        if not os.path.isdir(seq_path):
            continue
        for shot in sorted(os.listdir(seq_path)):
            if os.path.isdir(os.path.join(seq_path, shot)):
                shots.append((seq, shot))
    return shots


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


def unknown_nodes():
    """Nodes from plug-ins that aren't loaded (Maya shows them as "unknown"),
    e.g. old Node Editor bookmarks, Redshift settings, editor tab info. Never
    part of an asset, and their data stops Maya writing a .ma at all ("This
    file contains unknown data..."). Referenced ones are left alone."""
    return [n for n in cmds.ls(type=["unknown", "unknownDag", "unknownTransform"]) or []
            if not cmds.referenceQuery(n, isNodeReferenced=True)
            and not cmds.lockNode(n, query=True, lock=True)[0]]


def _not_loaded(plugin):
    if plugin == "maya":
        return False
    try:
        return not cmds.pluginInfo(plugin, query=True, loaded=True)
    except RuntimeError:
        return True


def drop_unknown_requires(path):
    """Take `requires "<plugin>" ...;` lines for plug-ins that aren't loaded
    in this Maya (e.g. an old stereoCamera or Redshift) out of a published
    .ma, so opening the publish doesn't error "Plug-in ... was not found".
    Their nodes are already left out (they'd be unknown nodes), so nothing
    in the file needs them. Only the file's header is touched; the working
    scene is never changed (Maya can't undo removing a plug-in
    requirement). .mb files are left as they are. Returns what was taken out."""
    if not path.lower().endswith(".ma"):
        return []
    tmp = path + ".tmp"
    dropped, statement, header = [], [], True
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as src, \
            open(tmp, "w", encoding="utf-8", errors="surrogateescape", newline="") as out:
        for line in src:
            if header and (statement or line.startswith("requires")):
                statement.append(line)
                if line.rstrip().endswith(";"):
                    quoted = re.findall(r'"([^"]*)"', "".join(statement))
                    plugin = quoted[-2] if len(quoted) >= 2 else None
                    if plugin and _not_loaded(plugin):
                        dropped.append(plugin)
                    else:
                        out.writelines(statement)
                    statement = []
                continue
            if header and line.startswith(("createNode", "fileInfo", "currentUnit", "file ")):
                header = False
            out.write(line)
    os.replace(tmp, path)
    return sorted(set(dropped))


class _LeftOutForExport(object):
    """While inside, the nodes find() returns are deleted from the working
    scene so an export leaves them out; on the way out they're put back with
    Maya's undo. Nothing else undoable may happen inside. self.removed:
    what was left out."""

    what = "nodes"

    def __init__(self, find=None):
        self._find = find or (lambda: unused_shading_nodes() + unknown_nodes())

    def __enter__(self):
        self.removed = sorted(set(self._find()))
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
                    "The publish worked, but these %s weren't put back in your "
                    "scene: %s\nReopen your scene without saving to get them back."
                    % (self.what, ", ".join(missing)))
        return False


class _WithoutUnusedShading(_LeftOutForExport):
    """Whole-scene exports: unassigned shaders and unknown plug-in nodes
    left out (unused shaders DECIDED 2026-10-19)."""
    what = "unused shaders / unknown nodes"


class _WithoutUnknownData(_LeftOutForExport):
    """Model exports: unknown plug-in nodes left out (the model's own
    shaders travel with the copy, so only unknown nodes matter here)."""
    what = "unknown plug-in nodes"

    def __init__(self):
        super(_WithoutUnknownData, self).__init__(unknown_nodes)


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
ENV_CODE = "env"
GEOMETRY_TYPES = ("mesh", "nurbsSurface", "subdiv")
# A Model publish freezes transforms and deletes history, which would wreck
# a rig (user, 2026-10-20), so it refuses anything carrying these.
RIG_NODE_TYPES = ("joint", "skinCluster", "blendShape", "ikHandle", "constraint")


def rig_parts(objects):
    """{node type: count} of rig nodes in what's being published (objects,
    their children and their history; empty = the whole scene)."""
    if objects:
        nodes = cmds.ls(objects, long=True) or []
        nodes += cmds.listRelatives(nodes, allDescendents=True, fullPath=True) or []
        if nodes:
            nodes += cmds.listHistory(nodes) or []
    else:
        nodes = cmds.ls() or []
    found = {}
    for node_type in RIG_NODE_TYPES:
        count = len(set(cmds.ls(nodes, type=node_type) or []))
        if count:
            found[node_type] = count
    return found


def check_not_a_rig(objects):
    """Refuse a Model publish of a rig: freezing and deleting history on
    the copy would break it."""
    found = rig_parts(objects)
    if found:
        raise PublishError(
            "This looks like a rig (%s). A Modeling publish freezes transforms and "
            "deletes history, which would break it.\nChoose Rigging in Department."
            % ", ".join("%d %s" % (n, t) for t, n in sorted(found.items())))


def _under(node, roots):
    """True if node is one of roots or below one of them."""
    path = (cmds.ls(node, long=True) or [""])[0]
    for root in roots:
        root_path = (cmds.ls(root, long=True) or [""])[0]
        if root_path and (path == root_path or path.startswith(root_path + "|")):
            return True
    return False


def cache_transforms(members):
    """The transforms a cache_SET's members stand for (long names, no
    repeats): a shape or a component counts as its transform. What a shot
    publish gives Alembic as roots, so the rig check and the shot cache
    read the set the same way."""
    found = []
    for node in cmds.ls(members, objectsOnly=True, long=True) or []:
        if cmds.objectType(node, isAType="shape"):
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
        if cmds.objectType(node, isAType="transform") and node not in found:
            found.append(node)
    return found


def nested_in(nodes):
    """The nodes (long names) that sit below another one of them."""
    return [n for n in nodes if any(n.startswith(o + "|") for o in nodes if o != n)]


def check_cache_set(objects):
    """A Rigging publish needs exactly one cache_SET (made by the rigger,
    never by the tool) holding geometry, all of it inside what's being
    published. Returns the set's name; raises PublishError explaining what
    to fix."""
    how = ("\n\nRig publishes need a %s: an object set listing the geometry that "
           "gets rendered, which is what a shot publish caches. Rig helpers (NURBS "
           "surfaces that drive joints, collision geometry...) stay out of it. Create "
           "it by hand (select the render geometry, Create > Sets > Set, name it %s), "
           "then publish again." % (CACHE_SET, CACHE_SET))
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
    # Alembic can't take a group and something inside it as separate roots,
    # so a shot's cache of this rig would fail.
    nested = nested_in(cache_transforms(members))
    if nested:
        raise PublishError(
            "%s holds both groups and things inside them: %s\nA shot's cache can't take "
            "both. Keep the group or the meshes inside it in %s, not both."
            % (cache_set, ", ".join(n.split("|")[-1] for n in nested[:5]), CACHE_SET))
    if objects:
        outside = [m for m in members if not _under(m, objects)]
        if outside:
            raise PublishError(
                "%s holds things that aren't in this publish: %s\n"
                "Publish the whole rig (or include them), or take them out of the set."
                % (cache_set, ", ".join(outside[:5])))
    return cache_set


# ---------------------------------------------------------------------------
# Rig control sets (spec §4 "Rig sets: controls and render geo", DECIDED
# 2026-10-20): the rigger makes body_controls_SET (+ face_controls_SET, +
# any custom sets); a rig publish is refused without them. Sets can hold
# sets, so mGear's or Advanced Skeleton's own sets go inside. A MetaHuman
# face's controls count as face controls automatically. Publish gathers
# the pipe's sets into RMIT_publishSet (user, 2026-10-20). The names
# Publish recognises live in rig_rules.py.
# ---------------------------------------------------------------------------

PUBLISH_SET = "RMIT_publishSet"
BODY_CONTROLS_SET = "body_controls_SET"
FACE_CONTROLS_SET = "face_controls_SET"


def _short(node):
    return node.split("|")[-1].split(":")[-1]


def _own_sets(name):
    """Object sets called name (any namespace), not from a reference."""
    return [s for s in cmds.ls(type="objectSet") or []
            if _short(s) == name and not cmds.referenceQuery(s, isNodeReferenced=True)]


def set_tree(object_set):
    """object_set and every set nested inside it."""
    found, todo = [], [object_set]
    while todo:
        s = todo.pop()
        if s in found:
            continue
        found.append(s)
        todo += [m for m in cmds.sets(s, query=True) or [] if cmds.nodeType(m) == "objectSet"]
    return found


def set_controls(object_set):
    """The transforms in a set, following sets nested inside it (long names)."""
    controls = set()
    for s in set_tree(object_set):
        for m in cmds.sets(s, query=True) or []:
            if cmds.nodeType(m) == "transform" or cmds.nodeType(m) == "joint":
                controls.add(cmds.ls(m, long=True)[0])
    return sorted(controls)


def metahuman_face_controls():
    """None if the rig has no MetaHuman (no DNA node), else the face
    controls by rig_rules.METAHUMAN: CTRL_ transforms under the face GUI
    group, minus the board and utility nodes (long names; may be empty if
    MetaHuman renamed things)."""
    import rig_rules
    rules = rig_rules.METAHUMAN
    try:
        dna = cmds.ls(type=rules["dna_node_type"]) or []
    except RuntimeError:
        dna = []        # node type unknown: the plug-in isn't loaded
    if not dna:
        return None
    skip = set(rules["not_controls"])
    found = set()
    for group in cmds.ls(type="transform", long=True) or []:
        if _short(group) != rules["face_gui_group"]:
            continue
        for node in cmds.listRelatives(group, allDescendents=True, fullPath=True,
                                       type="transform") or []:
            short = _short(node)
            if short.startswith(rules["control_prefix"]) and short not in skip:
                found.add(node)
    return sorted(found)


def _known_set_hints():
    """'rig1_controllers_grp: mGear's controllers set: ...' for sets other
    tools made that are in the scene, to say what goes where."""
    import fnmatch
    import rig_rules
    hints = []
    for s in cmds.ls(type="objectSet") or []:
        for pattern, text in rig_rules.KNOWN_SETS:
            if fnmatch.fnmatchcase(_short(s), pattern):
                hints.append("%s: %s" % (s, text))
                break
    return ("\n\nFound in this scene:\n  " + "\n  ".join(hints)) if hints else ""


def _one_set(name, how):
    sets = _own_sets(name)
    if not sets:
        raise PublishError("This rig has no %s." % name + how)
    if len(sets) > 1:
        raise PublishError("This scene has more than one %s (%s). Keep just one."
                           % (name, ", ".join(sets)))
    return sets[0]


def check_control_sets(objects):
    """A Rigging publish needs the rigger's control sets. Returns
    {body, face, metahuman_missing, metahuman_count, sets} where
    metahuman_missing are MetaHuman face controls not yet in the face set
    (Publish adds them to the published file only) and sets is every set
    to export with the rig. Raises PublishError explaining what to fix."""
    how = ("\n\nRig publishes need control sets, made by hand:\n"
           "  %s   (body controls; required)\n  %s   (face controls; required "
           "for a MetaHuman, optional otherwise)\n"
           "Create > Sets > Set for each. Sets can hold sets, so you can put an existing "
           "set (e.g. mGear's rig_controllers_grp) inside instead of the controls. "
           "Publish puts them in %s itself."
           % (BODY_CONTROLS_SET, FACE_CONTROLS_SET, PUBLISH_SET))
    how += _known_set_hints()
    body = _one_set(BODY_CONTROLS_SET, how)
    if not set_controls(body):
        raise PublishError("%s has no controls in it." % body + how)
    face = _own_sets(FACE_CONTROLS_SET)
    face = _one_set(FACE_CONTROLS_SET, how) if face else None
    metahuman = metahuman_face_controls()
    missing = []
    if metahuman is not None:
        import rig_rules
        rules = rig_rules.METAHUMAN
        if not metahuman:
            raise PublishError(
                "This rig has MetaHuman DNA (%s) but no %s face controls under %s. "
                "MetaHuman may have renamed them: put the face controls in %s yourself, "
                "or update rig_rules.py." % (rules["dna_node_type"], rules["control_prefix"],
                                             rules["face_gui_group"], FACE_CONTROLS_SET))
        if not face:
            raise PublishError("This is a MetaHuman rig, so it needs a %s (it can be "
                               "empty: Publish adds the MetaHuman face controls)."
                               % FACE_CONTROLS_SET + how)
        have = set(set_controls(face))
        missing = [c for c in metahuman if c not in have]
    elif face and not set_controls(face):
        raise PublishError("%s is empty. Add the face controls, or delete the set if "
                           "this rig has no face." % face + how)
    if objects:
        for s in (body, face):
            outside = [c for c in set_controls(s) if not _under(c, objects)] if s else []
            if outside:
                raise PublishError(
                    "%s holds controls that aren't in this publish: %s\n"
                    "Publish the whole rig (or include them), or take them out of the set."
                    % (s, ", ".join(_short(c) for c in outside[:5])))
    sets = set_tree(body) + (set_tree(face) if face else [])
    return {"body": body, "face": face,
            "metahuman_missing": missing,
            "metahuman_count": len(metahuman) if metahuman is not None else 0,
            "sets": [s for i, s in enumerate(sets) if s not in sets[:i]]}


class _PublishSet(object):
    """For the length of the export, RMIT_publishSet holds exactly the
    pipe's sets (cache_SET, body_controls_SET, face_controls_SET). Made by
    Publish (user, 2026-10-20); if the scene already has one, its members
    are swapped for the export and put back after, so the working scene
    ends as it was. Exported with the rig via plan["set_uuids"]."""

    def __init__(self, plan, members):
        self.plan, self.members = plan, [m for m in members if m]
        self.made, self.existing, self.before = None, None, []

    def __enter__(self):
        own = _own_sets(PUBLISH_SET)
        if own:
            self.existing = own[0]
            self.before = cmds.sets(self.existing, query=True) or []
            if self.before:
                cmds.sets(self.before, remove=self.existing)
            cmds.sets(self.members, add=self.existing)
            node = self.existing
        else:
            node = self.made = cmds.sets(self.members, name=PUBLISH_SET)
        self.plan["set_uuids"] = list(self.plan.get("set_uuids") or []) + \
            cmds.ls(node, uuid=True)
        return self

    def __exit__(self, *exc):
        if self.made and cmds.objExists(self.made):
            cmds.delete(self.made)
        if self.existing and cmds.objExists(self.existing):
            now = cmds.sets(self.existing, query=True) or []
            if now:
                cmds.sets(now, remove=self.existing)
            if self.before:
                cmds.sets(self.before, add=self.existing)
        return False


class _AddedToSet(object):
    """Add nodes to a set for the length of an export, then take them out
    again, so the working scene ends as it was (MetaHuman face controls
    into face_controls_SET for the published file only)."""

    def __init__(self, object_set, nodes):
        self.object_set, self.nodes = object_set, list(nodes or [])

    def __enter__(self):
        if self.object_set and self.nodes:
            cmds.sets(self.nodes, add=self.object_set)
        return self

    def __exit__(self, *exc):
        if self.object_set and self.nodes and cmds.objExists(self.object_set):
            cmds.sets(self.nodes, remove=self.object_set)
        return False


# ---------------------------------------------------------------------------
# Rig publish group (user, 2026-10-20): like the model and camera, the
# published rig sits in <asset>_rig_GRP (pipe icon, locked at the origin),
# whose stamp also lists the rig's textures, MetaHuman DNA files, plug-ins
# and control-set details. Made in the published file only: a rig can't be
# duplicated like a model, so its top nodes are parented under the group
# for the export and put back afterwards.
# ---------------------------------------------------------------------------

def required_plugins():
    """[name, version] of loaded plug-ins whose node types the scene uses
    (not counting referenced nodes): what the rig needs to work elsewhere."""
    found = []
    for plugin in sorted(cmds.pluginInfo(query=True, listPlugins=True) or []):
        types = cmds.pluginInfo(plugin, query=True, dependNode=True) or []
        if any(n for t in types for n in (cmds.ls(type=t) or [])
               if not cmds.referenceQuery(n, isNodeReferenced=True)):
            found.append([plugin, cmds.pluginInfo(plugin, query=True, version=True)])
    return found


class _RigGroup(object):
    """For the length of the export, parent the rig's top nodes (relative,
    so their own values don't change) under a stamped <asset>_rig_GRP;
    afterwards put them back where they were and delete the group. An
    existing node with the group's name steps aside meanwhile."""

    def __init__(self, plan, objects, info):
        self.plan, self.objects, self.info = plan, objects, info
        self.group, self.roots, self.aside = None, [], None

    def __enter__(self):
        name = pipe_group_name(self.plan["asset"], RIG_CODE)
        roots = cmds.ls(_model_roots(self.objects), uuid=True)
        if cmds.objExists(name):
            self.aside = cmds.ls(name, uuid=True)[0]
            cmds.rename(name, "pipeTmp_" + name)
        for uuid in roots:
            node = cmds.ls(uuid, long=True)[0]
            parent = cmds.listRelatives(node, parent=True, fullPath=True)
            self.roots.append((uuid, cmds.ls(parent[0], uuid=True)[0] if parent else None))
        group = make_pipe_group(name)
        self.group = cmds.ls(group, long=True)[0]
        try:
            cmds.parent(cmds.ls(roots, long=True), self.group, relative=True)
            self.group = cmds.ls(cmds.ls(group, uuid=True)[0], long=True)[0]
            _stamp(self.group, self.info)
            finish_pipe_group(self.group)
        except Exception:
            self._undo()
            raise
        return self

    def _undo(self):
        group_uuid = cmds.ls(self.group, uuid=True) if self.group and cmds.objExists(self.group) else []
        for uuid, parent in self.roots:
            node = cmds.ls(uuid, long=True)
            if not node:
                continue
            current = cmds.listRelatives(node[0], parent=True, fullPath=True)
            if parent:
                if not current or cmds.ls(current[0], uuid=True)[0] != parent:
                    cmds.parent(node[0], cmds.ls(parent, long=True)[0], relative=True)
            elif current:
                cmds.parent(node[0], world=True, relative=True)
        if group_uuid and cmds.ls(group_uuid):
            delete_pipe_group(cmds.ls(group_uuid)[0])   # the rig itself stays
        if self.aside and cmds.ls(self.aside):
            cmds.rename(cmds.ls(self.aside)[0], pipe_group_name(self.plan["asset"], RIG_CODE))

    def __exit__(self, *exc):
        self._undo()
        return False


def rig_group_info(plan, scene_path, files):
    """The rig group's stamp: the model group's fields plus the rig's
    textures, DNA files (portable paths, read by pipeEnv.fix_dna_paths),
    plug-ins and control-set details. Lists are JSON text."""
    import rig_rules
    sets = plan.get("control_sets") or {}
    return pipe_group_info(plan, scene_path) + [
        ("textures", json.dumps(files.stamp_textures)),
        ("dna", json.dumps(files.stamp_dna)),
        ("plugins", json.dumps(required_plugins())),
        ("rigRulesVersion", rig_rules.VERSION),
        ("metahumanFaceControls", sets.get("metahuman_count", 0)),
        ("faceControlsAdded", len(sets.get("metahuman_missing") or [])),
    ]


def export_rig_to_h_drive(objects, plan, scene_path, textures=(), dna=(), face_fill=(None, [])):
    """Rig publish: textures and DNA copied to the version's folder on the H
    drive, MetaHuman face controls added to face_controls_SET, the pipe's
    sets gathered in RMIT_publishSet, the rig in a stamped <asset>_rig_GRP,
    all in the published file only; the working scene ends as it was.
    objects empty = the whole scene."""
    import publishTool_textures as tex
    # DNA nodes go with a selected-objects export even if nothing selected
    # connects to them (a real one is wired to the joints anyway).
    plan["set_uuids"] = list(plan.get("set_uuids") or []) + [d["uuid"] for d in dna or []]
    sets = plan.get("control_sets") or {}
    pipe_sets = [plan.get("cache_set"), sets.get("body"), sets.get("face")]
    with _AddedToSet(*face_fill), _PublishSet(plan, pipe_sets), \
            tex.PublishedTextures(textures, plan, dna) as files:
        with _RigGroup(plan, objects, rig_group_info(plan, scene_path, files)) as rig:
            export_to_h_drive([rig.group] if objects else [], plan)
    if files.stamp_dna:
        plan.setdefault("warnings", []).append(
            "MetaHuman DNA published: %s. Check head and body point at the right files."
            % ", ".join("%s -> %s" % (d["node"], d["file"]) for d in files.stamp_dna))


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
                if plan.get("set_uuids"):
                    # The sets themselves, not just their members (a rig's
                    # cache_SET and control sets, nested ones included).
                    cmds.select(cmds.ls(plan["set_uuids"]), add=True, noExpand=True)
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
                drop_unknown_requires(plan["dest"])
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
# Outliner icon on every pipe group, so it reads as "from the pipe" (user,
# 2026-10-20). Just the file name: Maya finds it in the prefs icons folder
# the pipe installer copies to (shelfDev/mpPipe/icons). Missing icon = the
# normal container icon, nothing breaks. Only shown on a container, hence
# make_pipe_group.
PIPE_ICON = "iconPipeOutliner.png"
GROUP_CHANNELS = ("translateX", "translateY", "translateZ", "rotateX", "rotateY",
                  "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility")


def pipe_group_name(asset, code):
    return "%s_%s_GRP" % (asset, code)


def make_pipe_group(name):
    """An empty pipe group at the world root. A dagContainer (Maya's own
    "asset" node, no plug-in needed) rather than a plain group, because the
    Outliner only shows a custom iconName on a container (tested
    2026-10-20). It moves and parents like a group; children parented
    under it become its members, and stop being when parented out."""
    return cmds.container(type="dagContainer", name=name)


def delete_pipe_group(group):
    """Delete a pipe group but never its members: anything still inside is
    taken out of the container first (cmds.delete on a container would
    take its members with it)."""
    members = []
    if cmds.nodeType(group) == "dagContainer":
        members = cmds.container(group, query=True, nodeList=True) or []
    if members:
        cmds.container(group, edit=True, removeNode=members)
    cmds.delete(group)


def finish_pipe_group(group):
    """Every published asset's top group (user, 2026-10-20): the pipe icon
    in the Outliner, and locked at the world origin with its channels
    hidden so it can't be moved by accident. Only the group: what's inside
    it (the model's own transforms, a rig's controls) stays free."""
    cmds.setAttr(group + ".iconName", PIPE_ICON, type="string")
    for attr in GROUP_CHANNELS:
        plug = "%s.%s" % (group, attr)
        cmds.setAttr(plug, 1 if attr.startswith("scale") or attr == "visibility" else 0)
        cmds.setAttr(plug, lock=True, keyable=False, channelBox=False)


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


def _shown(node):
    """Is this one node switched on: its own visibility, LOD visibility,
    and any display layer it's in."""
    if not cmds.getAttr(node + ".visibility"):
        return False
    if cmds.attributeQuery("lodVisibility", node=node, exists=True) and \
            not cmds.getAttr(node + ".lodVisibility"):
        return False
    for layer in cmds.listConnections(node + ".drawOverride", source=True, destination=False,
                                      type="displayLayer") or []:
        if not cmds.getAttr(layer + ".visibility"):
            return False
    return True


def visible_in_scene(node):
    """Shown in the viewport: the node and every parent above it switched on."""
    path = (cmds.ls(node, long=True) or [""])[0]
    parts = path.split("|")
    return all(_shown("|".join(parts[:i])) for i in range(2, len(parts) + 1))


def hidden_inside(root):
    """Paths below root (e.g. '|door001') of transforms and geometry shapes
    that are hidden, so a model publish can leave them out (user,
    2026-10-19). Only the top-most hidden thing of a branch is listed."""
    found = []
    for node in sorted(cmds.listRelatives(root, allDescendents=True, fullPath=True) or [], key=len):
        if any(node.startswith(root + h + "|") for h in found):
            continue
        is_geo = cmds.nodeType(node) in GEOMETRY_TYPES
        if (cmds.nodeType(node) == "transform" or is_geo) and not _shown(node):
            if not (is_geo and cmds.getAttr(node + ".intermediateObject")):
                found.append(node[len(root):])
    return found


def _remove_empty_groups(nodes):
    """Delete transforms under (and including) nodes that hold no shape at
    all any more. Returns their short names."""
    removed = []
    candidates = []
    for node in cmds.ls(nodes, long=True) or []:
        candidates.append(node)
        candidates += cmds.listRelatives(node, allDescendents=True, fullPath=True,
                                         type="transform") or []
    for node in sorted(set(candidates), key=len, reverse=True):     # deepest first
        if cmds.objExists(node) and cmds.nodeType(node) == "transform" and \
                not cmds.listRelatives(node, allDescendents=True, type="shape"):
            removed.append(node.split("|")[-1])
            cmds.delete(node)
    return sorted(removed)


def export_model_to_h_drive(objects, plan, scene_path, textures=()):
    """Model publish: the published file holds a clean copy of the model,
    transforms frozen and history deleted, inside <asset>_model_GRP with
    the publish's identity stamped on it. Done on duplicates; the working
    scene ends exactly as it was (names, transforms, history, selection).
    objects empty = every top-level object. textures (from
    publishTool_textures.collect) are copied to the version's folder on
    the H drive like a rig's (user, 2026-10-28); none = an untextured
    model, published as before."""
    import publishTool_textures as tex
    missing = [o for o in objects if not cmds.objExists(o)]
    if missing:
        raise PublishError("Not in the scene any more: %s" % ", ".join(missing))
    if os.path.exists(plan["dest"]):
        raise PublishError("%s already exists — try again." % plan["dest"])
    if not os.path.isdir(plan["h_folder"]):
        os.makedirs(plan["h_folder"])
    # The copies share the originals' shaders, so pointing the file nodes
    # at the H drive copies for the export is enough.
    with tex.PublishedTextures(textures, plan) as files:
        info = pipe_group_info(plan, scene_path)
        if files.stamp_textures:
            info.append(("textures", json.dumps(files.stamp_textures)))
        _export_model(objects, plan, info)


def _export_model(objects, plan, info):
    file_type = "mayaAscii" if plan["ext"] == ".ma" else "mayaBinary"
    group_name = pipe_group_name(plan["asset"], plan["code"])
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
                # What's hidden is worked out on the originals (layers,
                # parents above the selection), then left out of the copies.
                hidden_roots = [cmds.ls(u, long=True)[0] for u in roots
                                if not visible_in_scene(cmds.ls(u, long=True)[0])]
                if hidden_roots and len(hidden_roots) == len(roots):
                    raise PublishError("Everything selected is hidden: %s"
                                       % ", ".join(r.split("|")[-1] for r in hidden_roots))
                roots = [u for u in roots if cmds.ls(u, long=True)[0] not in hidden_roots]
                left_out = [r.split("|")[-1] for r in hidden_roots]
                hidden = dict((u, hidden_inside(cmds.ls(u, long=True)[0])) for u in roots)
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
                    copy = cmds.ls(copy, long=True)[0]
                    for suffix in hidden[uuid]:
                        if cmds.objExists(copy + suffix):
                            cmds.delete(copy + suffix)
                            left_out.append(suffix.split("|")[-1])
                    copies.append(cmds.ls(copy, uuid=True)[0])
                empties = _remove_empty_groups(cmds.ls(copies, long=True))
                copies = [u for u in copies if cmds.ls(u)]
                if not copies:
                    raise PublishError("Nothing left to publish: everything selected is "
                                       "hidden or an empty group.")
                plan["left_out"] = {"hidden": sorted(left_out), "empty": empties}
                copy_nodes = cmds.ls(copies, long=True)
                # Invalid / unused components (Mesh Cleanup) make Maya warn
                # "errors have occurred while reading this scene" on every
                # open of the publish. Cleaned on the copies only.
                meshes = [m for m in cmds.listRelatives(copy_nodes, allDescendents=True,
                                                        fullPath=True, type="mesh") or []
                          if not cmds.getAttr(m + ".intermediateObject")]
                for mesh in meshes:     # one at a time: one bad mesh mustn't stop the rest
                    try:
                        cmds.polyClean(mesh, cleanEdges=True, cleanVertices=True)
                    except RuntimeError:
                        pass        # nothing to clean / not cleanable: publish as is
                everything = copy_nodes + (cmds.listRelatives(
                    copy_nodes, allDescendents=True, fullPath=True) or [])
                cmds.delete(everything, constructionHistory=True)
                leftovers = [s for s in cmds.ls(everything, shapes=True, long=True) or []
                             if cmds.objExists(s) and cmds.getAttr(s + ".intermediateObject")]
                if leftovers:
                    cmds.delete(leftovers)     # e.g. "Orig" shapes from deformers
                cmds.makeIdentity(copy_nodes, apply=True, translate=True, rotate=True,
                                  scale=True, normal=0, preserveNormals=True)
                group = make_pipe_group(group_name)
                made.append(cmds.ls(group, uuid=True)[0])
                cmds.parent(cmds.ls(copies, long=True), group)
                _stamp(group, info)
                finish_pipe_group(group)
                cmds.select(group, replace=True)
                # Unknown plug-in data (old editor bookmarks, Redshift...)
                # never belongs to a model and stops a .ma being written.
                with _WithoutUnknownData() as unknown:
                    cmds.file(plan["dest"], exportSelected=True, type=file_type,
                              constructionHistory=True, channels=True, constraints=True,
                              expressions=True, shader=True, preserveReferences=True,
                              force=True)
                plan["left_out"]["unknown"] = len(unknown.removed)
                plan["left_out"]["requires"] = drop_unknown_requires(plan["dest"])
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
    <scene's asset project>/images/publish/<asset>/<login>_<code>_v###/ on
    scratch. If objects are given, only they are shown (isolate select). If
    camera is given, the playblast looks through it.
    Returns (folder, files).

    The folder's name is the ShotGrid Version's name after the entity
    (Shed_e131988_env_v002, like the file on H). Without the login, version
    numbers restarting for a new login (scout -> e131988) found and reused
    the old person's Versions, replacing their movies (2026-10-28)."""
    version_name = "%s_v%03d" % (plan["code"], plan["version"])
    if plan.get("login"):
        version_name = "%s_%s" % (plan["login"], version_name)
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
        try:
            burn_in(files, burn_in_text(plan, camera))
        except Exception as e:      # a movie without burn-ins beats no publish
            cmds.warning("Publish: burn-ins not drawn: %s" % e)
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


# Burn-ins on publish movies (user, 2026-10-20: "published shotsubs are
# missing burn ins"). Same layout as shotSub's: frame rate top left, name
# top middle (here the shot or asset name),
# frame number top right, focal length bottom left, artist bottom right.

def burn_in_text(plan, camera=None):
    """{corner: text} for a publish's burn-ins. Frame numbers are per file.
    Top middle is the shot or asset name, not the file name (user,
    2026-10-28)."""
    name = plan.get("asset") or os.path.splitext(os.path.basename(plan.get("dest") or ""))[0]
    login = plan.get("login") or ""
    artist = artist_name(login) if login else ""
    focal = ""
    shapes = []
    if camera:
        shapes = cmds.listRelatives(camera, shapes=True, type="camera") or []
    if shapes:
        focal = "%.0fmm" % cmds.getAttr(shapes[0] + ".focalLength")
    return {"top_left": "%g fps" % _scene_fps(),
            "top_middle": name,
            "bottom_left": focal,
            "bottom_right": ("%s (%s)" % (artist, login)) if artist else login}


def burn_in(files, text):
    """Draw text (from burn_in_text) onto each JPEG, plus its frame number
    top right, white with a drop shadow, as shotSub does. Needs Qt's
    application (there in Maya; headless callers make one)."""
    from PySide6 import QtCore, QtGui
    if QtGui.QGuiApplication.instance() is None:
        raise RuntimeError("no Qt application (headless Maya)")
    for path in files:
        image = QtGui.QImage(path)
        if image.isNull():
            continue
        width, height = image.width(), image.height()
        margin = max(36, int(width * 0.04))
        band = max(34, int(height * 0.055))
        inset = max(28, int(height * 0.04))
        top, bottom = inset, height - inset - band
        frame = re.search(r"\.(\d+)\.jpg$", path, re.IGNORECASE)
        quarter, half = int(width * 0.25), int(width * 0.5)
        middle = QtCore.Qt.AlignVCenter
        left, centre, right = (int(QtCore.Qt.AlignLeft | middle), int(QtCore.Qt.AlignHCenter | middle),
                               int(QtCore.Qt.AlignRight | middle))
        blocks = [
            (QtCore.QRect(margin, top, quarter - margin, band), text.get("top_left"), left),
            (QtCore.QRect(quarter, top, half, band), text.get("top_middle"), centre),
            (QtCore.QRect(width - quarter, top, quarter - margin, band),
             frame.group(1) if frame else "", right),
            (QtCore.QRect(margin, bottom, quarter - margin, band), text.get("bottom_left"), left),
            # Doesn't clip: "Name (login)" is often wider than a quarter.
            (QtCore.QRect(width - quarter, bottom, quarter - margin, band),
             text.get("bottom_right"),
             int(QtCore.Qt.AlignRight | middle | QtCore.Qt.TextDontClip)),
        ]
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        font = QtGui.QFont("Arial", max(12, int(height * 0.022)))
        font.setBold(True)
        painter.setFont(font)
        for rect, words, align in blocks:
            if not words:
                continue
            painter.setPen(QtGui.QColor(0, 0, 0, 180))
            painter.drawText(rect.translated(2, 2), align, words)
            painter.setPen(QtGui.QColor(255, 255, 255, 230))
            painter.drawText(rect, align, words)
        painter.end()
        image.save(path, "JPG", 95)


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
# Approval (spec §3c, rule 2026-10-23): approval blocks no publish; it only
# triggers caches. A final publish is an iterative publish plus the
# department's caches, made when the newest Version on the Final task is
# Approved. Final isn't a state the shot keeps (user, 2026-10-28: "once a
# final publish has occurred it's not an ongoing set state"): each publish
# makes a new Version, Pending Review, so the one after it is iterative
# again unless that Version is approved too.
# ---------------------------------------------------------------------------

APPROVED = "apr"


def approved_tasks(sg_entity):
    """{task name (lower case): that Task} for every Task on the Shot whose
    newest linked Version is Approved. Versions with no task (shotSub's)
    don't count."""
    sg = _shotgrid().get_connection()
    versions = sg.find("Version", [["entity", "is", {"type": sg_entity.get("type", "Shot"),
                                                     "id": sg_entity["id"]}],
                                   ["sg_task", "is_not", None]],
                       ["sg_task", "sg_task.Task.content", "sg_status_list"],
                       order=[{"field_name": "created_at", "direction": "desc"},
                              {"field_name": "id", "direction": "desc"}])
    found, seen = {}, set()
    for v in versions:              # newest first: only each task's newest counts
        task = v.get("sg_task")
        if not task or task["id"] in seen:
            continue
        seen.add(task["id"])
        name = (v.get("sg_task.Task.content") or "").strip().lower()
        if name and v.get("sg_status_list") == APPROVED:
            found[name] = task
    return found


def task_on(sg_entity, name):
    """The Task called name (any case) on a Shot/Asset, or None."""
    sg = _shotgrid().get_connection()
    for task in sg.find("Task", [["entity", "is", {"type": sg_entity.get("type", "Shot"),
                                                   "id": sg_entity["id"]}]], ["content"]):
        if (task["content"] or "").strip().lower() == name.lower():
            return {"type": "Task", "id": task["id"], "content": task["content"]}
    return None


def newest_approved(sg_entity, task):
    """True when the newest Version on task (a Task on sg_entity) is
    Approved: the publish going on that task is a Final publish (user,
    2026-10-28). Shots: caches; assets and Layout: no caches, but a green
    thumbnail border, and whatever Final triggers later."""
    if not task:
        return False
    return any(t["id"] == task["id"] for t in approved_tasks(sg_entity).values())


# Each asset department's publishes go on a Task of this name on the
# ShotGrid Asset (user, 2026-10-28: department Tasks, like the shots'
# Final task). desktopDev/asset_tasks.py makes them.
ASSET_TASKS = {"model": "Model", "rig": "Rig", "creature": "Creature",
               "lookDev": "LookDev", "env": "Environment"}


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
    # The movie made for review (review_before_publish) is the one uploaded.
    import inspect
    if plan.get("movie_path") and "movie_path" in inspect.signature(sg.upload_playblast).parameters:
        kwargs["movie_path"] = plan["movie_path"]
    version = sg.upload_playblast(*args, **kwargs)
    upload_bordered_thumbnail(sg, plan, version, args[0], args[1], kwargs.get("files"))
    return version


# Publish thumbnail borders (user, 2026-10-28): a pipe publish's ShotGrid
# thumbnail gets a dark blue border when it's iterative and a bright green
# one when it's Final, so they stand out from plain shotSub Versions (no
# border). Only the thumbnail: the movie stays as it is.
BORDER_ITERATIVE = (25, 45, 120)
BORDER_FINAL = (40, 230, 70)


def bordered_thumbnail(path, final):
    """A copy of the JPEG at path with a blue (iterative) or green (final)
    border, in a new temp folder. Returns the copy's path."""
    from PySide6 import QtGui
    image = QtGui.QImage(path)
    if image.isNull():
        raise RuntimeError("couldn't read %s" % path)
    width, height = image.width(), image.height()
    edge = max(8, int(min(width, height) * 0.05))
    colour = QtGui.QColor(*(BORDER_FINAL if final else BORDER_ITERATIVE))
    painter = QtGui.QPainter(image)
    for x, y, w, h in ((0, 0, width, edge), (0, height - edge, width, edge),
                       (0, 0, edge, height), (width - edge, 0, edge, height)):
        painter.fillRect(x, y, w, h, colour)
    painter.end()
    out = os.path.join(tempfile.mkdtemp(prefix="pipeThumb_"), os.path.basename(path))
    if not image.save(out, "JPG", 95):
        raise RuntimeError("couldn't write %s" % out)
    return out


def upload_bordered_thumbnail(sgc, plan, version, entity_type, entity_id, files):
    """Replace the thumbnail upload_playblast just set (its middle frame, on
    the Version and its Shot/Asset) with the same frame bordered. Uploaded
    after the movie, so ShotGrid's own thumbnail from the movie doesn't come
    later. Publishes without plan['final'] (shotSub never has one) are left
    alone; a failure is a warning, never a failed publish."""
    if "final" not in plan or not (version and files):
        return
    try:
        thumb = bordered_thumbnail(files[len(files) // 2], plan["final"])
        try:
            sg = sgc.get_connection()
            sg.upload_thumbnail("Version", version["id"], thumb)
            sg.upload_thumbnail(entity_type, entity_id, thumb)
        finally:
            shutil.rmtree(os.path.dirname(thumb), ignore_errors=True)
    except Exception as e:
        plan.setdefault("warnings", []).append(
            "The ShotGrid thumbnail has no %s border: %s"
            % ("Final (green)" if plan["final"] else "iterative (blue)", e))


def review_before_publish(plan, review, project, audio_path=None, audio_offset=0.0):
    """Make the movie straight after the playblast, before anything is
    written, and let the student watch it: review(movie_path or None, plan)
    returns True to publish. On cancel the frames are removed and
    PublishCancelled is raised. review=None (headless) skips the question;
    the movie is still made here and uploaded as it is."""
    plan["movie_path"] = None
    rvio = find_rvio()
    encode = getattr(_shotgrid(), "_encode_to_mp4", None)
    if rvio and encode:
        import inspect
        kwargs = {}
        if audio_path and "audio_path" in inspect.signature(encode).parameters:
            kwargs = dict(audio_path=audio_path, audio_offset_seconds=audio_offset)
        plan["movie_path"] = encode(plan["frames_folder"], _scene_fps(), rvio, **kwargs)
    if review and not review(plan["movie_path"], plan):
        remove_frames(plan["frames_folder"], project)
        raise PublishCancelled("Cancelled after watching the movie: nothing was published.")


def find_rv():
    """RV itself (to watch a movie), next to rvio. "" if not found."""
    rvio = find_rvio()
    if not rvio:
        return ""
    folder = os.path.dirname(rvio)
    for name in ("rv.exe", "rv", "RV"):
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return ""


def publish(scene_path, h_root, scratch_root, code, frame_count=2, notes="",
            objects=None, target=None, review=None):
    """Playblast -> watch the movie -> H drive -> ShotGrid Version on the Asset.

    objects: publish only these (exported); empty/None = the whole scene
    file. target: (asset_type, asset) to publish to a different asset than
    the scene's own folder. review: see review_before_publish.

    Anything that can fail cleanly (ShotGrid lookup, playblast) happens
    before the H-drive write. Returns the plan dict plus 'sg_asset',
    'sg_version' and 'sg_error' (set if only the ShotGrid upload failed,
    after the H-drive write succeeded)."""
    h_root = resolve_root(h_root)
    check_script_nodes()
    environment = None
    if code == ENV_CODE:
        # From a shot's layout scene or an asset scene, to an environment
        # asset, by its sets (spec §4c).
        import publishTool_env as env
        import publishTool_textures as tex
        plan = env.plan_environment(scene_path, h_root, scratch_root, target)
        environment = env.check_environment(h_root, plan["film"])
        plan.setdefault("warnings", []).extend(environment["warnings"])
        # A missing picture stops the publish here, before anything is made.
        tex.collect(environment[env.LANDSCAPE] + environment[env.BUILDINGS]
                    + environment[env.SKY], image_planes=True)
    else:
        plan = plan_publish(scene_path, h_root, scratch_root, code, target=target)
    plan["objects"] = list(objects or [])
    face_fill = (None, [])
    textures, dna = [], []
    if code == MODEL_CODE:
        check_not_a_rig(plan["objects"])
        # The model's textures travel with it, found through its shaders
        # like the rig's (user, 2026-10-28); a missing one stops the
        # publish here. No textures is fine.
        import publishTool_textures as tex
        textures = tex.collect(_model_roots(plan["objects"]))
    if code == RIG_CODE:
        # Checked before anything is made or uploaded.
        import publishTool_textures as tex
        plan["cache_set"] = check_cache_set(plan["objects"])
        plan["control_sets"] = check_control_sets(plan["objects"])
        plan["set_uuids"] = cmds.ls([plan["cache_set"]] + plan["control_sets"]["sets"], uuid=True)
        face_fill = (plan["control_sets"]["face"], plan["control_sets"]["metahuman_missing"])
        # The rig's textures and MetaHuman DNA travel with it (spec §4
        # "Texture workflow through rigging"); a missing one stops the
        # publish here.
        textures = tex.collect(plan["objects"])
        dna = tex.collect_dna()
    plan["sg_asset"] = find_shotgrid_asset(plan, h_root)
    check_rv()
    shown = plan["objects"]
    if environment:
        shown = environment[env.LANDSCAPE] + environment[env.BUILDINGS] + environment[env.SKY]
    plan["frames_folder"], files = playblast_frames(plan, frame_count, shown)
    plan["audio"], audio_offset = scene_audio(int(cmds.playbackOptions(query=True, minTime=True)))
    review_before_publish(plan, review, plan["asset_project"], plan["audio"], audio_offset)

    plan["namespaces_removed"] = []
    try:
        if environment:
            env.export_environment_to_h_drive(plan, scene_path, environment,
                                              plan.setdefault("warnings", []))
        elif code == MODEL_CODE:
            # Always a clean copy in its pipe group (spec §4 item 6a).
            export_model_to_h_drive(plan["objects"], plan, scene_path, textures)
        elif code == RIG_CODE:
            # Always exported: in its pipe group, with textures and DNA.
            export_rig_to_h_drive(plan["objects"], plan, scene_path, textures, dna, face_fill)
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
            "Unused shaders / unknown plug-in nodes left out of the published file "
            "(your scene is unchanged): %d" % len(plan["unused_shading_left_out"]))
    left_out = plan.get("left_out") or {}
    if left_out.get("hidden"):
        plan.setdefault("warnings", []).append(
            "Hidden objects left out of the published file (your scene is unchanged): %s"
            % ", ".join(left_out["hidden"]))
    if left_out.get("empty"):
        plan.setdefault("warnings", []).append(
            "Empty groups left out: %s" % ", ".join(left_out["empty"]))
    if left_out.get("unknown"):
        plan.setdefault("warnings", []).append(
            "%d unknown plug-in node(s) left out (old editor/renderer data, not part "
            "of the model)." % left_out["unknown"])
    if left_out.get("requires"):
        plan.setdefault("warnings", []).append(
            "The published file no longer asks for plug-ins that aren't installed: %s"
            % ", ".join(left_out["requires"]))

    what = ("%d object(s): %s" % (len(plan["objects"]), ", ".join(plan["objects"]))
            if plan["objects"] else "whole scene")
    note = "Published %s v%03d to the H drive:\n%s\n(from %s, %s)" % (
        code, plan["version"], plan["dest"], os.path.basename(scene_path), what)
    if plan.get("textures"):
        note += "\nTextures: %d file(s), MetaHuman DNA: %d, in %s" % (
            plan["textures"]["files"], plan["textures"].get("dna", 0), plan["textures"]["folder"])
    if notes.strip():
        # The student's own words first, the file details underneath.
        note = notes.strip() + "\n\n---\n" + note
    plan["sg_version"] = plan["sg_error"] = None
    rvio = find_rvio()
    plan["movie_warning"] = None if rvio else (
        "RV's rvio wasn't found on this machine, so ShotGrid got a thumbnail "
        "but no playable movie.")
    # The department's Task on the Asset; Final when its newest Version is
    # Approved (user, 2026-10-28). No Task yet: iterative, Version unlinked.
    plan["sg_task"], plan["final"] = None, False
    try:
        plan["sg_task"] = task_on(plan["sg_asset"], ASSET_TASKS.get(code, code))
        plan["final"] = newest_approved(plan["sg_asset"], plan["sg_task"])
    except Exception as e:
        plan.setdefault("warnings", []).append(
            "Couldn't check ShotGrid for a Final approval (published as iterative): %s" % e)
    try:
        plan["sg_version"] = upload_with_audio(
            _shotgrid(), plan, plan["audio"], audio_offset,
            "Asset", plan["sg_asset"]["id"], plan["frames_folder"],
            files=files, notes=note, fps=_scene_fps(), rvio_path=rvio,
            machine_diagnostic=plan["movie_warning"])
    except Exception as e:     # H-drive copy already done; report, don't lose it
        plan["sg_error"] = str(e)
    else:
        if plan["sg_task"]:
            link_version_to_task(plan, plan["sg_task"])
        else:
            plan.setdefault("warnings", []).append(
                "The ShotGrid Asset has no %s task, so this publish can't be approved "
                "for Final yet (staff: run desktopDev/asset_tasks.py)."
                % ASSET_TASKS.get(code, code))
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

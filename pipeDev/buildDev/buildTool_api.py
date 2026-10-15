"""
Build Tool — core
Pulls published assets from the H drive into a shot on scratch, keeps
track of which version each shot has, and manages what's on scratch.
No UI, so it can be tested under mayapy.

Design: pipeDev/filmPipeline_spec.md §3e (Build owns scratch), §3h
(drives, 1:1 mirror) and §3i (Build Shot workflow, department codes,
scratch management).

    H drive  G:\\H\\NWF_SHF\\maya\\assets\\prop\\backpack\\scenes\\s1234567\\backpack_s1234567_model_v002.ma
    scratch  G:\\scratch\\NWF_SHF\\maya\\publish\\assets\\prop\\backpack\\scenes\\s1234567\\backpack_s1234567_model_v002.ma
             (one copy per version, shared by every shot; each shot's
             assets\\build_manifest.json records the version it uses)
    camera   ...\\sequences\\EAP_010\\EAP_010_010\\assets\\camera\\cam.ma  (stays in its shot)

Shares drive settings, department codes and film-folder helpers with the
Publish tool (pipeDev/publishDev/publishTool_api.py).
"""

import os
import re
import sys
import json
import stat
import ctypes
import shutil
from datetime import datetime

import maya.cmds as cmds

_PUBLISH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "publishDev")
if os.path.isdir(_PUBLISH_DIR) and _PUBLISH_DIR not in sys.path:
    sys.path.append(_PUBLISH_DIR)

import publishTool_api as pub
from publishTool_api import PublishError as BuildError   # same "student can fix" error
import pipeEnv                                            # $PIPE_SCRATCH reference paths

MANIFEST_NAME = "build_manifest.json"   # in <shot>/assets/, records what was pulled
KEEP_FILES = ("workspace.mel",)          # never removed from scratch

# <asset>_<login>_<code>_v###.<ext>, in <asset>\scenes\<login>\ (spec §4
# "Personal work folders": publishes are personal, DECIDED 2026-10-15).
PUBLISHED_RE = re.compile(r"^(?P<asset>.+)_(?P<login>[a-z0-9]+)_(?P<code>[A-Za-z]+)"
                          r"_v(?P<version>\d{3})\.(?P<ext>ma|mb)$", re.IGNORECASE)
DEPT_CODES = [code for _, code in pub.DEPARTMENTS]
DEPT_LABELS = dict((code, label) for label, code in pub.DEPARTMENTS)
DEPT_LABELS["cam"] = "Camera"


# ---------------------------------------------------------------------------
# Films and shots
# ---------------------------------------------------------------------------

def list_films(root):
    """Film folders (<FILM>_<TYPE>) under a drive root."""
    if not root or not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root)
                  if pub.FILM_FOLDER_RE.match(n) and os.path.isdir(os.path.join(root, n)))


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


def shot_folder(root, film, seq, shot):
    return os.path.join(root, film, "maya", "sequences", seq, shot)


def shot_of_scene(scene_path, scratch_root):
    """(film, seq, shot) if the scene is inside a shot on scratch, else None."""
    try:
        root, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if (not pub._same_path(root, scratch_root) or len(rel) < 5
            or rel[1] != "maya" or rel[2] != "sequences"):
        return None
    return rel[0], rel[3], rel[4]


# ---------------------------------------------------------------------------
# Published assets on the H drive
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Version ids. Publishes are personal, so a version is a person + number
# ("scout/v003"): two people can both have a v003. The latest is the most
# recently published, whoever published it (spec §4 "Personal work
# folders": "Time stamp of the asset defines if it is the latest").
# ---------------------------------------------------------------------------

def version_id(login, version):
    return "%s/v%03d" % (login or "?", version)


def entry_version_id(entry):
    """The version id a manifest entry records. Entries from before personal
    publishes have no login and match no current version."""
    return version_id(entry.get("login"), entry["version"])


def version_label(published, vid, mark_latest=True):
    """'v003 (s1234567)', plus '  (latest)' for the newest."""
    info = published.get("info", {}).get(vid)
    if not info:
        return vid
    text = "v%03d (%s)" % (info["version"], info["login"])
    if mark_latest and vid == published.get("latest"):
        text += "  (latest)"
    return text


def newer_available(published, entry):
    """True if the published entry has something newer than what the
    manifest entry records."""
    if not entry:
        return False
    current = entry_version_id(entry)
    info = published.get("info", {})
    if current not in info:
        return True     # an old or removed version: anything on the H drive is newer
    return info[published["latest"]]["time"] > info[current]["time"]


def _add_version(entry, login, version, path, time_path=None):
    vid = version_id(login, version)
    entry["versions"][vid] = path
    entry["info"][vid] = {"login": login, "version": version,
                          "time": publish_time(time_path or path)}


def _finish(entry):
    entry["latest"] = max(entry["info"], key=lambda v: entry["info"][v]["time"])
    return entry


def sorted_versions(published):
    """Version ids, newest first."""
    return sorted(published["versions"], key=lambda v: published["info"][v]["time"],
                  reverse=True)


def list_published(h_root, film):
    """Every published asset on the H drive, grouped by asset + department.

    Returns a list of dicts sorted by type/asset/department:
      {asset_type, asset, code, versions: {vid: path},
       info: {vid: {login, version, time}}, latest: vid}
    """
    assets_dir = os.path.join(h_root, film, "maya", "assets")
    groups = {}
    for asset_type, asset in pub.list_h_assets(h_root, film):
        scenes = os.path.join(assets_dir, asset_type, asset, "scenes")
        for dirpath, _, filenames in os.walk(scenes):
            login = os.path.basename(dirpath)
            for name in filenames:
                m = PUBLISHED_RE.match(name)
                # Only in the publisher's own folder, named for this asset.
                if (not m or m.group("asset").lower() != asset.lower()
                        or m.group("login").lower() != login.lower()):
                    continue
                code = m.group("code")
                key = (asset_type, asset, code)
                entry = groups.setdefault(key, {
                    "asset_type": asset_type, "asset": asset, "code": code,
                    "versions": {}, "info": {}})
                _add_version(entry, login.lower(), int(m.group("version")),
                             os.path.join(dirpath, name))
    result = []
    for key in sorted(groups, key=lambda k: (k[0], k[1].lower(),
                                             DEPT_CODES.index(k[2]) if k[2] in DEPT_CODES else 99)):
        result.append(_finish(groups[key]))
    return result


CAMERA_TYPE = "camera"              # asset_type used for a shot's camera
CAMERA_CODE = "cam"
CAMERA_NAME = "camera1"             # the shot camera is always live as camera1
OLD_CAMERA_NAME = "camera1_old"     # what an existing camera1 is renamed to
SHOT_ATTR = "pipeShot"              # stamped on camera1 at build
VERSION_ATTR = "pipeCameraVersion"
CURVE_KEY_ATTRS = ("ktv", "kix", "kiy", "kox", "koy", "kit", "kot", "kwl", "tan", "wgt")
CAMERA_FILES = {"camera": "assets/camera/cam.ma",
                "keys": "assets/camera/camAnim.ma",
                "map": "assets/camera/camAnim.json"}
BY_ATTR = "pipeCameraBy"            # who published the built camera
CAMERA_RE = re.compile(r"^(?P<shot>.+)_(?P<login>[a-z0-9]+)_(?P<code>cam|camAnim)"
                       r"_v(?P<version>\d{3})\.(?P<ext>ma|json)$", re.IGNORECASE)


def list_shot_cameras(h_root, film, seq, shot):
    """The shot's published cameras on the H drive (everyone's, from each
    person's scenes\\<login>\\), as a list with at most one entry shaped
    like list_published()'s, plus 'kind': 'camera' and
    'files': {vid: {camera, keys, map}}. Only complete versions (all three
    files) count. The latest is the newest by publish time."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    for dirpath, _, filenames in os.walk(scenes):
        login = os.path.basename(dirpath).lower()
        for name in filenames:
            m = CAMERA_RE.match(name)
            if (not m or m.group("shot").lower() != shot.lower()
                    or m.group("login").lower() != login):
                continue
            part = ("camera" if m.group("code").lower() == "cam" else
                    "keys" if m.group("ext").lower() == "ma" else "map")
            found.setdefault((login, int(m.group("version"))), {})[part] = \
                os.path.join(dirpath, name)
    entry = {"kind": "camera", "asset_type": CAMERA_TYPE, "asset": shot,
             "code": CAMERA_CODE, "files": {}, "versions": {}, "info": {}}
    for (login, version), files in found.items():
        if len(files) == 3:
            _add_version(entry, login, version, files["camera"])
            entry["files"][version_id(login, version)] = files
    return [_finish(entry)] if entry["files"] else []


def publish_time(path):
    """When a file was published. copy2 keeps the source's modified time,
    so use the H-drive file's creation time (Windows) where available."""
    st = os.stat(path)
    return st.st_ctime if os.name == "nt" else st.st_mtime


# ---------------------------------------------------------------------------
# Pulling into the shared publish folder on scratch (spec §3i "One shared
# publish folder on scratch"): one copy per version, used by every shot
# ---------------------------------------------------------------------------

PUBLISH_FOLDER = "publish"      # <scratch>/<film>/maya/publish, mirrors the H drive's maya/


def maya_dir_of_shot(shot_dir):
    """<root>/<film>/maya for a shot folder <root>/<film>/maya/sequences/<seq>/<shot>."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(shot_dir))))


def publish_dir(maya_dir):
    return os.path.join(maya_dir, PUBLISH_FOLDER)


def _maya_rel(h_path):
    """The part of an H-drive path below <film>/maya, e.g.
    'assets/prop/backpack/scenes/backpack_model_v002.ma'."""
    _, rel = pub.find_film_folder(h_path)
    if len(rel) < 3 or rel[1] != "maya":
        raise BuildError("Not inside a film's maya folder: %s" % h_path)
    return "/".join(rel[2:])


def legacy_rel_path(asset_type, asset, code, ext):
    """Where Build Shot used to copy an asset inside the shot (fixed name,
    before the shared publish folder). Only used to find and repoint old
    references."""
    parts = ["assets", asset_type, asset]
    if code != "model":
        parts.append(code)
    parts.append(asset + ext)
    return "/".join(parts)


def entry_path(shot_dir, entry):
    """Full path of what a manifest entry points at: the shared publish
    folder for assets, the shot itself for cameras (and old entries)."""
    if entry.get("shared"):
        return os.path.join(publish_dir(maya_dir_of_shot(shot_dir)), *entry["shared"].split("/"))
    return os.path.join(shot_dir, *entry["file"].split("/"))


def _manifest_path(shot_dir):
    return os.path.join(shot_dir, "assets", MANIFEST_NAME)


def read_manifest(shot_dir):
    try:
        with open(_manifest_path(shot_dir), "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def _write_manifest(shot_dir, manifest):
    path = _manifest_path(shot_dir)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def manifest_key(asset_type, asset, code):
    return "%s/%s/%s" % (asset_type, asset, code)


def copy_published(source, maya_dir):
    """Copy one published file from the H drive into the shared publish
    folder under the same path and name, unless an identical copy is
    already there. Read-only, like the publish. Returns (dest, copied)."""
    dest = os.path.join(publish_dir(maya_dir), *_maya_rel(source).split("/"))
    if os.path.isfile(dest) and os.path.getsize(dest) == os.path.getsize(source):
        return dest, False
    if not os.path.isdir(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    if os.path.isfile(dest):
        os.chmod(dest, stat.S_IWRITE)
    shutil.copy2(source, dest)
    os.chmod(dest, stat.S_IREAD)
    return dest, True


def pull(shot_dir, published, vid):
    """Make sure one published version (a version id, e.g. 'scout/v003')
    is in the shared publish folder and record that this shot uses it.
    Other shots' versions are untouched. Returns the path in the publish
    folder."""
    if vid not in published["versions"]:
        raise BuildError("%s of %s %s isn't on the H drive."
                         % (vid, published["asset"], published["code"]))
    source = published["versions"][vid]
    dest, _ = copy_published(source, maya_dir_of_shot(shot_dir))

    info = published["info"][vid]
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    manifest = read_manifest(shot_dir)
    manifest[key] = {
        "version": info["version"],
        "login": info["login"],
        "shared": _maya_rel(source),
        "source": source,
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    _write_manifest(shot_dir, manifest)
    return dest


def scene_references():
    """[(reference node, path as written, full path, resolved path)] for
    the open scene's top-level references, loaded or not, including ones
    whose file is missing. 'As written' is exactly what the scene stores
    (e.g. '$PIPE_SCRATCH/NWF_SHF/...'); 'full path' is that with the
    variable and any project-relative part filled in."""
    found = []
    for node in cmds.ls(type="reference") or []:
        if node == "sharedReferenceNode" or "_UNKNOWN_REF_NODE_" in node:
            continue
        try:
            if cmds.referenceQuery(node, parent=True, referenceNode=True):
                continue    # nested: it comes with its parent's file
            written = cmds.referenceQuery(node, filename=True, unresolvedName=True,
                                          withoutCopyNumber=True)
            resolved = cmds.referenceQuery(node, filename=True, withoutCopyNumber=True)
        except RuntimeError:
            continue
        found.append((node, written, _absolute(written), _absolute(resolved)))
    return found


def _absolute(path):
    """Fill in $PIPE_SCRATCH, and resolve project-relative reference paths
    (e.g. 'assets/prop/backpack/backpack.ma', as older builds wrote them)
    against the current Maya project."""
    path = os.path.expandvars(path) if path else path
    if path and not os.path.isabs(path):
        workspace = cmds.workspace(query=True, rootDirectory=True) or ""
        return os.path.normpath(os.path.join(workspace, path))
    return path


def referenced_nodes(path):
    """Reference nodes in the open scene that point at path."""
    target = os.path.normcase(os.path.normpath(path))
    return [node for node, _, full, resolved in scene_references()
            if target in (os.path.normcase(os.path.normpath(resolved)),
                          os.path.normcase(os.path.normpath(full)))]


def written_path(ref_node):
    """The reference's path exactly as the scene stores it."""
    return cmds.referenceQuery(ref_node, filename=True, unresolvedName=True,
                               withoutCopyNumber=True)


def repoint_reference(ref_node, path):
    """Swap a reference to another file ("Replace Reference"). Keys and
    other changes made on top of it carry over where node names match.
    path may use $PIPE_SCRATCH."""
    cmds.file(path, loadReference=ref_node)


def reload_references_to(path):
    """Reload any reference in the open scene that points at path, so an
    update shows up straight away. Returns the reference nodes reloaded."""
    nodes = referenced_nodes(path)
    for node in nodes:
        if cmds.referenceQuery(node, isLoaded=True):
            cmds.file(unloadReference=node)
        cmds.file(loadReference=node)
    return nodes


def namespace_for(asset, code):
    return asset if code == "model" else "%s_%s" % (asset, code)


def _old_paths(shot_dir, published, entry):
    """Files an existing reference to this asset might point at: the
    version the shot had, and the fixed-name copy Build Shot used to keep
    inside the shot (so old scenes get repointed too)."""
    paths = [entry_path(shot_dir, entry)] if entry else []
    for ext in (".ma", ".mb"):
        paths.append(os.path.join(shot_dir, *legacy_rel_path(
            published["asset_type"], published["asset"], published["code"], ext).split("/")))
    return paths


def build_asset(shot_dir, published, vid):
    """One click for one asset: make sure the chosen version (a version id,
    e.g. 'scout/v003') is in the shared publish folder, then make sure the
    open scene references it. A reference to another version (or to an old
    copy in the shot) is repointed, never referenced twice. Only this shot
    changes.

    Returns (list of what was done, warning or None, replaced) where
    replaced is the path of a version this shot no longer uses, or None."""
    if published.get("kind") == "camera":
        done, warning = build_camera(shot_dir, published, vid)
        return done, warning, None
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    namespace = namespace_for(published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    previous = entry_path(shot_dir, entry) if entry else None
    label = version_label(published, vid, mark_latest=False)
    done = []

    same = bool(entry) and entry_version_id(entry) == vid
    restored = bool(same and entry.get("shared") and not os.path.isfile(previous))
    dest = pull(shot_dir, published, vid)
    if not entry:
        done.append("pulled %s" % label)
    elif not same:
        done.append("%s -> %s" % (version_label(published, entry_version_id(entry), False)
                                  if entry_version_id(entry) in published["info"]
                                  else "v%03d" % entry["version"], label))
    elif restored:
        done.append("%s pulled again (it was missing)" % label)
    replaced = previous if previous and not pub._same_path(previous, dest) else None

    # References are written with $PIPE_SCRATCH so the shot opens from any
    # drive (spec "Reference paths that work on any drive"). Point the
    # variable at this shot's drive first.
    pipeEnv.set_from_path(shot_dir)
    ref_path = pipeEnv.to_var_path(dest)

    nodes = referenced_nodes(dest)
    if nodes:
        old_ns = use_clean_namespace(dest, namespace)
        if old_ns:
            done.append("renamed %s: to %s:" % (old_ns, namespace))
        rewritten = False
        for node in nodes:
            if not pipeEnv.uses_var(written_path(node)) and pipeEnv.uses_var(ref_path):
                repoint_reference(node, ref_path)   # full D:\... path -> $PIPE_SCRATCH
                rewritten = True
        if rewritten:
            done.append("reference path made drive-independent")
        elif restored:
            reload_references_to(dest)
            done.append("reloaded in scene")
        if not done:
            done.append("already up to date")
        return done, None, replaced

    for path in _old_paths(shot_dir, published, entry):
        nodes = referenced_nodes(path)
        if nodes:
            for node in nodes:
                repoint_reference(node, ref_path)
            use_clean_namespace(dest, namespace)
            done.append("scene reference switched to %s" % label)
            return done, None, replaced

    reference_into_scene(ref_path, namespace)
    done.append("referenced into scene")
    return done, None, replaced


def shots_using(maya_dir):
    """{full path of a pulled version: [shot, ...]} from every shot's
    build manifest under one film's maya folder on scratch."""
    used = {}
    seq_dir = os.path.join(maya_dir, "sequences")
    if not os.path.isdir(seq_dir):
        return used
    for seq in os.listdir(seq_dir):
        for shot in os.listdir(os.path.join(seq_dir, seq)) if os.path.isdir(
                os.path.join(seq_dir, seq)) else []:
            shot_dir = os.path.join(seq_dir, seq, shot)
            for entry in read_manifest(shot_dir).values():
                if entry.get("shared"):
                    path = os.path.normcase(os.path.normpath(entry_path(shot_dir, entry)))
                    used.setdefault(path, []).append(shot)
    return used


def unused_versions(paths, maya_dir):
    """The paths (pulled versions in the publish folder) that no shot's
    manifest uses and the open scene doesn't reference."""
    used = shots_using(maya_dir)
    in_scene = set(os.path.normcase(os.path.normpath(r)) for _, _, _, r in scene_references())
    result = []
    for path in paths:
        key = os.path.normcase(os.path.normpath(path))
        if os.path.isfile(path) and key not in used and key not in in_scene \
                and key.startswith(os.path.normcase(publish_dir(maya_dir)) + os.sep):
            result.append(path)
    return result


# ---------------------------------------------------------------------------
# Repair: pull back anything the open scene references that's missing
# ---------------------------------------------------------------------------

def repair_scene(h_root):
    """For every reference in the open scene whose file is missing: if it
    points into a publish folder on scratch, copy that exact version back
    from the H drive and load it. Old in-shot copies can't be repaired
    this way (their version isn't known): Build Shot repoints those.

    Returns (fixed, not_fixed) as lists of messages."""
    fixed, not_fixed = [], []
    for node, written, full, resolved in scene_references():
        path = resolved if os.path.isfile(resolved) else full
        if os.path.isfile(path):
            continue
        if pipeEnv.uses_var(written) and not pipeEnv.current():
            not_fixed.append("%s: %s isn't set, so this scene can't tell which drive to "
                             "look on. Is mpPipe installed? Reopen the scene after "
                             "installing." % (os.path.basename(written), pipeEnv.VAR))
            continue
        name = os.path.basename(path)
        try:
            root, rel = pub.find_film_folder(path)
        except BuildError:
            not_fixed.append("%s: not in a film folder, can't tell where it came from." % name)
            continue
        if len(rel) > 3 and rel[1] == "maya" and rel[2] == PUBLISH_FOLDER:
            source = os.path.join(h_root, rel[0], "maya", *rel[3:])
            if not os.path.isfile(source):
                not_fixed.append("%s: not on the H drive either (%s)." % (name, source))
                continue
            dest, _ = copy_published(source, os.path.join(root, rel[0], "maya"))
            # Keep the path as the scene wrote it ($PIPE_SCRATCH stays).
            cmds.file(written if pipeEnv.uses_var(written) else dest, loadReference=node)
            fixed.append("%s: pulled again from the H drive and loaded." % name)
        elif len(rel) > 5 and rel[1] == "maya" and rel[2] == "sequences" and rel[5] == "assets":
            not_fixed.append("%s: an old copy kept inside the shot. Add %s in Build Shot "
                             "and build to switch it to a published version."
                             % (name, rel[7] if len(rel) > 8 else os.path.splitext(name)[0]))
        else:
            not_fixed.append("%s: missing, and not a pulled publish (%s)." % (name, path))
    return fixed, not_fixed


# ---------------------------------------------------------------------------
# Shot camera: imported live (not referenced) as camera1, keys connected
# and locked (spec §3i "Cameras": camera and keys are stored separately)
# ---------------------------------------------------------------------------

def pull_camera(shot_dir, published, vid):
    """Copy one camera version's three files into the shot under fixed
    names and record it in the manifest. Returns the camera file path."""
    if vid not in published["files"]:
        raise BuildError("Camera %s of %s isn't on the H drive."
                         % (vid, published["asset"]))
    for part, rel in CAMERA_FILES.items():
        dest = os.path.join(shot_dir, *rel.split("/"))
        if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        if os.path.isfile(dest):
            os.chmod(dest, stat.S_IWRITE)
        shutil.copy2(published["files"][vid][part], dest)
        os.chmod(dest, stat.S_IWRITE)

    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    manifest = read_manifest(shot_dir)
    info = published["info"][vid]
    manifest[key] = {
        "version": info["version"],
        "login": info["login"],
        "file": CAMERA_FILES["camera"],
        "extra_files": [CAMERA_FILES["keys"], CAMERA_FILES["map"]],
        "source": published["files"][vid]["camera"],
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    _write_manifest(shot_dir, manifest)
    return os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))


def shot_camera():
    """The built shot camera in the open scene: (transform, version id) or
    (None, None). It's the top-level camera1 carrying the build stamp.
    Cameras built before personal publishes have no BY_ATTR, so their id
    matches no current version and a rebuild replaces them."""
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        if node == "|" + CAMERA_NAME and cmds.attributeQuery(VERSION_ATTR, node=node, exists=True):
            by = (cmds.getAttr("%s.%s" % (node, BY_ATTR))
                  if cmds.attributeQuery(BY_ATTR, node=node, exists=True) else None)
            return node, version_id(by, cmds.getAttr("%s.%s" % (node, VERSION_ATTR)))
    return None, None


def _camera_curves(transform):
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    curves = set()
    for node in [transform] + shape:
        curves.update(cmds.listConnections(node, source=True, destination=False,
                                           type="animCurve") or [])
    return sorted(curves)


def set_camera_locked(transform, locked):
    """Lock (or unlock) the camera so its keys can't be edited by accident:
    the channels, the curves' key data (so the Graph Editor can't move keys
    either) and the curve nodes themselves (so they can't be deleted)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    curves = _camera_curves(transform)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    for node in (transform, shape):
        for attr in cmds.listAttr(node, keyable=True) or []:
            try:
                cmds.setAttr("%s.%s" % (node, attr), lock=locked)
            except RuntimeError:
                pass    # compound children etc.
    for curve in curves:
        for attr in CURVE_KEY_ATTRS:
            if cmds.attributeQuery(attr, node=curve, exists=True):
                cmds.setAttr("%s.%s" % (curve, attr), lock=locked)
        if locked:
            cmds.lockNode(curve, lock=True)


def _move_out_of_the_way(node):
    """Rename an existing camera1 (and its shape and our curves) to
    camera1_old, camera1_old1, ... Nothing is deleted. Returns the new name."""
    curves = _camera_curves(node)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    new = cmds.rename(node, OLD_CAMERA_NAME)
    for shape in cmds.listRelatives(new, shapes=True, fullPath=True) or []:
        cmds.rename(shape, new.split("|")[-1] + "Shape")
    prefix = CAMERA_NAME + "_"
    for curve in curves:
        if curve.startswith(prefix):
            curve = cmds.rename(curve, new.split("|")[-1] + "_" + curve[len(prefix):])
        if cmds.getAttr(curve + ".ktv", lock=True):
            cmds.lockNode(curve, lock=True)     # it was protected; keep it so
    return new.split("|")[-1]


def _import_into_root(path, prefix):
    """Import a file through a temporary namespace (so its names can't
    clash with what's in the scene), then move everything to the root.
    Returns {name in the file: node now in the scene}."""
    ns = prefix
    i = 1
    while cmds.namespace(exists=":" + ns):
        ns, i = "%s%d" % (prefix, i), i + 1
    new = cmds.file(path, i=True, type="mayaAscii", namespace=ns,
                    returnNewNodes=True, preserveReferences=False) or []
    found = dict((n.split("|")[-1].split(":")[-1], n) for n in new if cmds.objExists(n))
    return ns, found


def _drop_namespace(ns):
    if cmds.namespace(exists=":" + ns):
        cmds.namespace(removeNamespace=":" + ns, mergeNamespaceWithRoot=True)


def import_camera(shot_dir, version, login):
    """Import the pulled camera as a live camera1, connect its keys, stamp
    and lock it. Returns the transform."""
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    keys_path = os.path.join(shot_dir, *CAMERA_FILES["keys"].split("/"))
    with open(os.path.join(shot_dir, *CAMERA_FILES["map"].split("/")), "r") as f:
        mapping = json.load(f)

    ns, nodes = _import_into_root(cam_path, "buildCam")
    transform = nodes.get(mapping.get("camera", "shotCam"))
    if not transform or cmds.nodeType(transform) != "transform":
        raise BuildError("The camera file has no %s camera: %s"
                         % (mapping.get("camera", "shotCam"), cam_path))
    transform = cmds.rename(transform, ":" + CAMERA_NAME)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    cmds.rename(shape, ":" + CAMERA_NAME.replace("camera", "cameraShape"))
    _drop_namespace(ns)
    transform = cmds.ls("|" + CAMERA_NAME, long=True)[0]
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]

    ns, curves = _import_into_root(keys_path, "buildCamKeys")
    for curve, (where, attr) in mapping["curves"].items():
        if curve not in curves:
            raise BuildError("The keys file is missing curve %s." % curve)
        node = shape if where == "shape" else transform
        cmds.setAttr("%s.%s" % (node, attr), lock=False)
        cmds.connectAttr(curves[curve] + ".output", "%s.%s" % (node, attr), force=True)
        cmds.rename(curves[curve], ":%s_%s%s" % (CAMERA_NAME, "shape_" if where == "shape" else "", attr))
    _drop_namespace(ns)

    # Stamp: which shot and version this camera is (how a rebuild knows).
    for attr, value in ((SHOT_ATTR, mapping.get("shot", "")), (VERSION_ATTR, version),
                        (BY_ATTR, login)):
        if not cmds.attributeQuery(attr, node=transform, exists=True):
            if attr == VERSION_ATTR:
                cmds.addAttr(transform, longName=attr, attributeType="long")
            else:
                cmds.addAttr(transform, longName=attr, dataType="string")
        if attr == VERSION_ATTR:
            cmds.setAttr("%s.%s" % (transform, attr), value)
        else:
            cmds.setAttr("%s.%s" % (transform, attr), value, type="string")
        cmds.setAttr("%s.%s" % (transform, attr), lock=True)
    set_camera_locked(transform, True)
    return transform


def build_camera(shot_dir, published, vid):
    """One click for the shot camera: pull (or update), then import it live
    as camera1 with its keys, locked. An existing camera1 is renamed
    camera1_old first. Returns (done, warning)."""
    key = manifest_key(CAMERA_TYPE, published["asset"], CAMERA_CODE)
    entry = read_manifest(shot_dir).get(key)
    done = []
    files_there = all(os.path.isfile(os.path.join(shot_dir, *r.split("/")))
                      for r in CAMERA_FILES.values())
    label = version_label(published, vid, mark_latest=False)
    if not entry or entry_version_id(entry) != vid or not files_there:
        pull_camera(shot_dir, published, vid)
        done.append(("updated to %s" if entry else "pulled %s") % label)

    current, current_vid = shot_camera()
    if current and current_vid == vid:
        done.append("already up to date")
        return done, None

    # Cameras used to be referenced: turn an old reference into live nodes
    # so it can be moved aside like any other camera1.
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    for ref_node in referenced_nodes(cam_path):
        cams = [cmds.listRelatives(n, parent=True, fullPath=True)[0]
                for n in cmds.referenceQuery(ref_node, nodes=True, dagPath=True) or []
                if cmds.nodeType(n) == "camera"]
        cmds.file(cmds.referenceQuery(ref_node, filename=True), importReference=True)
        for node in cmds.ls(cams, long=True):
            done.append("old referenced camera %s made live and renamed %s"
                        % (node.split("|")[-1], _move_out_of_the_way(node)))
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        if node == "|" + CAMERA_NAME:
            done.append("existing camera1 renamed %s" % _move_out_of_the_way(node))
    info = published["info"][vid]
    import_camera(shot_dir, info["version"], info["login"])
    done.append("camera1 %s imported and locked" % label)
    return done, None


def free_namespace(namespace):
    """Make sure the clean namespace (e.g. backpack:) can be used. An empty
    leftover namespace is removed; one that still holds nodes is a real
    clash, explained rather than quietly becoming backpack1:."""
    if not cmds.namespace(exists=":" + namespace):
        return
    contents = cmds.namespaceInfo(":" + namespace, listNamespace=True, recurse=True) or []
    if contents:
        raise BuildError(
            "The name '%s:' is already used in this scene by %s.\n"
            "Rename or remove those first, then Build Shot again."
            % (namespace, ", ".join(sorted(contents)[:3]) + (" ..." if len(contents) > 3 else "")))
    cmds.namespace(removeNamespace=":" + namespace)


def use_clean_namespace(path, namespace):
    """If an existing reference to path has a different namespace (e.g.
    backpack1: from before this rule), move it to the clean one when that's
    free. Returns the old namespace if it was changed, else None."""
    for ref_node in referenced_nodes(path):
        current = cmds.referenceQuery(ref_node, namespace=True).lstrip(":")
        if current == namespace:
            continue
        try:
            free_namespace(namespace)
        except BuildError:
            return None     # something else uses the name; leave this one be
        cmds.file(cmds.referenceQuery(ref_node, filename=True), edit=True,
                  namespace=namespace)
        return current
    return None


def reference_into_scene(path, namespace):
    """Reference a pulled file into the open scene under its clean
    namespace. path is normally a $PIPE_SCRATCH path (see pipeEnv), since
    the shared publish folder is outside the shot project."""
    free_namespace(namespace)
    cmds.file(path, reference=True, namespace=namespace, mergeNamespacesOnClash=False)
    return path


def set_maya_project(shot_dir):
    cmds.workspace(shot_dir, openWorkspace=True)


def ensure_maya_project(shot_dir):
    """Make the shot the Maya project if it isn't already (spec §3f: Build
    sets the project so students don't switch by hand). True if changed."""
    workspace = cmds.workspace(query=True, rootDirectory=True)
    if workspace and pub._same_path(workspace, shot_dir):
        return False
    set_maya_project(shot_dir)
    return True


# ---------------------------------------------------------------------------
# What's on my scratch
# ---------------------------------------------------------------------------

SAFE, CHANGED, UNPUBLISHED = "safe", "changed", "unpublished"


def _files(folder):
    found = []
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            if dirpath == folder and name in KEEP_FILES:
                continue
            found.append(os.path.join(dirpath, name))
    return sorted(found)


def scratch_items(scratch_root, h_root, film):
    """Everything on scratch that holds files, with how safe it is to remove.

    Each item: {kind ('asset'|'shot'), label, folder, files, size,
    status (SAFE/CHANGED/UNPUBLISHED), latest (text), risky: [files]}.
    """
    items = []
    published = list_published(h_root, film) if h_root and os.path.isdir(h_root) else []

    # Assets: safe if every file is a scene older than the newest publish.
    for asset_type, asset in pub.list_h_assets(scratch_root, film):
        folder = os.path.join(scratch_root, film, "maya", "assets", asset_type, asset)
        files = _files(folder)
        if not files:
            continue
        pubs = [p for p in published if p["asset_type"] == asset_type and p["asset"] == asset]
        newest = None
        latest_text = "never published"
        for p in pubs:
            path = p["versions"][p["latest"]]
            t = publish_time(path)
            if newest is None or t > newest[0]:
                newest = (t, p)
        if newest:
            t, p = newest
            latest_text = "%s %s, %s" % (DEPT_LABELS.get(p["code"], p["code"]),
                                          version_label(p, p["latest"], mark_latest=False),
                                          datetime.fromtimestamp(t).strftime("%d %b %H:%M"))
        scenes = os.path.normcase(os.path.join(folder, "scenes")) + os.sep
        risky = []
        for f in files:
            if newest is None or not os.path.normcase(f).startswith(scenes) \
                    or os.path.getmtime(f) > newest[0]:
                risky.append(f)
        status = SAFE if not risky else (UNPUBLISHED if newest is None else CHANGED)
        items.append(_item("asset", "%s  (%s)" % (asset, asset_type), folder,
                           files, status, latest_text, risky))

    # Shots: pulled copies can always be pulled again; anything else isn't
    # backed up anywhere yet (shot publishing isn't built).
    for seq, shot in list_shots(scratch_root, film):
        folder = shot_folder(scratch_root, film, seq, shot)
        files = _files(folder)
        if not files:
            continue
        manifest = read_manifest(folder)
        pulled = set(os.path.normcase(os.path.join(folder, *rel.split("/")))
                     for e in manifest.values()
                     for rel in ([e["file"]] if "file" in e else []) + e.get("extra_files", []))
        pulled.add(os.path.normcase(_manifest_path(folder)))
        risky = [f for f in files if os.path.normcase(f) not in pulled]
        status = SAFE if not risky else UNPUBLISHED
        latest = "%d pulled asset(s)" % len(manifest) if manifest else "-"
        items.append(_item("shot", "%s / %s" % (seq, shot), folder,
                           files, status, latest, risky))
    return items


def _item(kind, label, folder, files, status, latest, risky):
    return {"kind": kind, "label": label, "folder": folder, "files": files,
            "size": sum(os.path.getsize(f) for f in files),
            "status": status, "latest": latest, "risky": risky}


def removal_check(folder, h_root, scratch_root):
    """Refuse anything that isn't an asset/shot folder on scratch."""
    h_root, scratch_root = pub.resolve_root(h_root), pub.resolve_root(scratch_root)
    pub.check_roots(h_root, scratch_root)
    root, rel = pub.find_film_folder(os.path.join(folder, "x"))
    is_asset = len(rel) == 6 and rel[1:3] == ["maya", "assets"]
    is_shot = len(rel) == 6 and rel[1:3] == ["maya", "sequences"]
    if not (is_asset or is_shot):
        raise BuildError("Not an asset or shot folder: %s" % folder)
    if not pub._same_path(root, scratch_root):
        raise BuildError("Refusing to remove anything outside the scratch drive (%s)."
                         % scratch_root)


def send_to_recycle_bin(paths):
    """Move files to the Recycle Bin (Windows), so a mistake can be undone.
    Returns True on success. Folders are left in place (1:1 mirror)."""
    if not paths:
        return True
    if os.name != "nt":
        raise BuildError("Recycle Bin removal is only set up for Windows.")
    for p in paths:
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                    ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", ctypes.c_wchar_p)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = \
        3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = "\0".join(os.path.abspath(p) for p in paths) + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0 and not op.fAnyOperationsAborted


def format_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0

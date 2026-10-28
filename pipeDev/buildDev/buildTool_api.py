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
    rig      ...\\sequences\\EAP_010\\EAP_010_010\\assets\\character\\scout\\rig\\scout_rig.ma
             (fixed name the shot references, hardlinked to a version in
             publish\\; spec §4a, option C)
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

# Shared with the Publish tool's picker.
list_films = pub.list_films
list_shots = pub.list_shots


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
# Build by department (spec §4 "Build by department", user 2026-10-28): the
# artist's department decides what Build offers, "it would basically filter
# out rigs for the lighting team". Only what Build can build today is
# listed; caches, lights and lookDev shaders on caches come later, and FX
# and Lighting with them.
# ---------------------------------------------------------------------------

CAMERA_CODE = "cam"
ENV_CODE = pub.ENV_CODE
# (label, department code, what it builds: published department codes,
# "cam" for the shot camera, "env" for environments; None = coming soon).
BUILD_FOR = [
    ("Modeling", "model", ["model"]),
    ("Rigging", "rig", ["model"]),
    ("Creature", "creature", ["model", "rig", "creature", "lookDev", ENV_CODE, CAMERA_CODE]),
    ("LookDev", "lookDev", ["model", "lookDev"]),
    ("Layout", "layout", ["model", "rig", ENV_CODE, CAMERA_CODE]),
    ("Animation", "anim", ["model", "rig", ENV_CODE, CAMERA_CODE]),
    ("FX", "fx", None),
    ("Lighting", "lighting", None),
]
BUILD_FOR_LABELS = dict((code, label) for label, code, _ in BUILD_FOR)


def builds_for(department):
    """What a department's Build offers (codes, see BUILD_FOR); [] for one
    that's coming soon or unknown."""
    return next((list(t or []) for _, c, t in BUILD_FOR if c == department), [])


def live_departments():
    return [c for _, c, t in BUILD_FOR if t]


def department_of_scene(scene_path):
    """The department the open scene is worked in, from its working folder
    (scenes\\<department>\\<login>\\, spec "Shot working folders" and
    "Asset working folders"), else from its file name (scout_rig_v002 ->
    rig, as the Publish tool does), else Animation for a shot and Modeling
    for an asset. Never a coming-soon department: a lighting scene starts
    on Layout until Lighting builds. None outside the pipe."""
    try:
        _, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if len(rel) < 6 or rel[1] != "maya" or rel[2] not in ("sequences", "assets"):
        return None
    shot = rel[2] == "sequences"
    live = live_departments()
    found = None
    if len(rel) > 7 and rel[5] == "scenes":
        found = next((c for c in BUILD_FOR_LABELS if c.lower() == rel[6].lower()), None)
    if not found:
        words = re.split(r"[_.]", os.path.basename(scene_path).lower())
        found = next((c for c in BUILD_FOR_LABELS if c.lower() in words), None)
    if found in live:
        return found
    return "layout" if shot and found else "anim" if shot else "model"


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
        for dirpath, dirnames, filenames in os.walk(scenes):
            if os.path.normcase(dirpath) == os.path.normcase(scenes):
                # scenes\model\, rig\, lookDev\ hold working files, not publishes.
                work = [w.lower() for w in pub.WORK_FOLDERS]
                dirnames[:] = [d for d in dirnames if d.lower() not in work]
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
CAMERA_NAME = "camera1"             # the shot camera is always live as camera1
OLD_CAMERA_NAME = "camera1_old"     # what an existing camera1 is renamed to
DATA_NAME = CAMERA_NAME + "_DATA"   # holds the keys, drives camera1 1:1
CAMERA_MAP_FORMAT = 2               # camera group + data node (2026-10-20)
CURVE_KEY_ATTRS = ("ktv", "kix", "kiy", "kox", "koy", "kit", "kot", "kwl", "tan", "wgt")
CAMERA_FILES = {"camera": "assets/camera/cam.ma",
                "keys": "assets/camera/camAnim.ma",
                "map": "assets/camera/camAnim.json"}
# The published <shot>_cam_GRP's stamp says which version is built.
DEPT_STAMP, VERSION_STAMP, BY_STAMP = "pipe_department", "pipe_version", "pipe_artistId"
CAMERA_RE = re.compile(r"^(?P<shot>.+)_(?P<login>[a-z0-9]+)_(?P<code>cam|camAnim)"
                       r"_v(?P<version>\d{3})\.(?P<ext>ma|json)$", re.IGNORECASE)


def _walk_shot_publishes(scenes):
    """os.walk over a shot's scenes folder, minus scenes\\layout\\, anim\\,
    fx\\ and lighting\\: they hold working files, not publishes."""
    work = [w.lower() for w in pub.SHOT_WORK_FOLDERS]
    for dirpath, dirnames, filenames in os.walk(scenes):
        if os.path.normcase(dirpath) == os.path.normcase(scenes):
            dirnames[:] = [d for d in dirnames if d.lower() not in work]
        yield dirpath, filenames


def list_shot_cameras(h_root, film, seq, shot):
    """The shot's published cameras on the H drive (everyone's, from each
    person's scenes\\<login>\\), as a list with at most one entry shaped
    like list_published()'s, plus 'kind': 'camera' and
    'files': {vid: {camera, keys, map}}. Only complete versions (all three
    files) in the camera group format count; older publishes are left out
    and need republishing (user, 2026-10-20). The latest is the newest by
    publish time."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    for dirpath, filenames in _walk_shot_publishes(scenes):
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
        if len(files) == 3 and _camera_map_format(files["map"]) == CAMERA_MAP_FORMAT:
            _add_version(entry, login, version, files["camera"])
            entry["files"][version_id(login, version)] = files
    return [_finish(entry)] if entry["files"] else []


def _camera_map_format(path):
    try:
        with open(path, "r") as f:
            return json.load(f).get("format", 1)
    except (IOError, OSError, ValueError):
        return None


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
    """Full path of what the shot's scenes reference for a manifest entry:
    the rig's fixed name in the shot for linked departments, the shared
    publish folder for other assets, the shot itself for cameras (and old
    entries)."""
    if entry.get("link"):
        return os.path.join(shot_dir, *entry["link"].split("/"))
    return shared_path(shot_dir, entry)


def shared_path(shot_dir, entry):
    """Full path of the version file a manifest entry uses (in the shared
    publish folder), or the in-shot file for cameras and old entries."""
    if entry.get("shared"):
        return os.path.join(publish_dir(maya_dir_of_shot(shot_dir)), *entry["shared"].split("/"))
    return os.path.join(shot_dir, *entry["file"].split("/"))


# ---------------------------------------------------------------------------
# Rigs: a fixed name per shot, hardlinked to a version in the publish folder
# (spec §4a, option C, built 2026-10-20). The shot's reference path never
# changes, so updating or rolling back is a relink plus a reload, never a
# Replace Reference. Every shot follows an update by default; one shot can
# be rolled back on its own. Where the drive can't hardlink (exFAT, network
# shares) the fixed name is a read-only copy instead (option B): same path,
# more disk.
# ---------------------------------------------------------------------------

LINKED_CODES = ("rig",)
LINKED, COPY, MISSING, STALE = "linked", "copy", "missing", "stale"


def link_rel_path(asset_type, asset, code, ext):
    """The fixed name inside the shot, e.g.
    'assets/character/scout/rig/scout_rig.ma'."""
    return "/".join(["assets", asset_type, asset, code,
                     "%s_%s.%s" % (asset, code, ext.lstrip(".").lower())])


def _is_current(link, source):
    """True if link already holds source: the same data (hardlink), or a
    copy made from it (copy2 keeps size and modified time)."""
    if not (os.path.isfile(link) and os.path.isfile(source)):
        return False
    if os.path.samefile(link, source):
        return True
    a, b = os.stat(link), os.stat(source)
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def _lock_publish_folder(maya_dir):
    """Make every file in the publish folder read-only again. Windows keeps
    read-only per piece of data, not per name, so removing a hardlink (which
    needs it writable) unlocks the version it pointed at too."""
    for dirpath, _, filenames in os.walk(publish_dir(maya_dir)):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.access(path, os.W_OK):
                os.chmod(path, stat.S_IREAD)


def _drive_can_link(path):
    """True if path's drive is NTFS (hardlinks work). Only used to decide
    whether to turn an existing copy back into a link; os.link failing is
    what decides when making one."""
    if os.name != "nt":
        return True
    name = ctypes.create_unicode_buffer(32)
    drive = os.path.splitdrive(os.path.abspath(path))[0] + "\\"
    if not ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive), None, 0, None, None, None, name, len(name)):
        return False
    return name.value.upper() == "NTFS"


def _remove_name(path):
    if os.path.isfile(path):
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


def link_version(source, link, maya_dir):
    """Point the shot's fixed name at one version in the publish folder:
    a hardlink where the drive allows, else a read-only copy. Returns True
    if hardlinked."""
    if _is_current(link, source):
        if os.path.samefile(link, source):
            return True
        if not _drive_can_link(link):
            return False    # a copy is the best this drive can do
    try:
        _remove_name(link)
    except OSError as e:
        raise BuildError("Couldn't replace %s (%s). Is it open in another Maya?"
                         % (os.path.basename(link), e.strerror or e))
    finally:
        _lock_publish_folder(maya_dir)
    if not os.path.isdir(os.path.dirname(link)):
        os.makedirs(os.path.dirname(link))
    try:
        os.link(source, link)
        return True
    except OSError:
        shutil.copy2(source, link)
        os.chmod(link, stat.S_IREAD)
        return False


def link_state(shot_dir, entry):
    """LINKED, COPY (works, but uses its own disk), MISSING or STALE (holds
    something other than the version the manifest records, e.g. after the
    shot folder was copied from elsewhere). None for entries without a
    link. Build Shot fixes MISSING and STALE by building the asset again."""
    if not entry or not entry.get("link"):
        return None
    link, source = entry_path(shot_dir, entry), shared_path(shot_dir, entry)
    if not os.path.isfile(link):
        return MISSING
    if not os.path.isfile(source):
        return COPY     # version cleared from publish\: the shot still has the data
    if os.path.samefile(link, source):
        return LINKED
    return COPY if _is_current(link, source) else STALE


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


# The shot's build list on the H drive (user, 2026-10-23): one list per
# shot, shared by everyone building it, so the list comes back on any
# machine or scratch drive. Just which assets (manifest keys): versions start
# at the latest and keys at the shot's latest keys. Saved on Build Shot and
# when "-" takes an asset off.
SHOT_LIST_NAME = "build_list.json"


def shot_list_path(h_root, film, seq, shot):
    return os.path.join(shot_folder(h_root, film, seq, shot), SHOT_LIST_NAME)


def read_shot_list(h_root, film, seq, shot):
    """The shot's saved list of manifest keys, or None if it has none yet."""
    try:
        with open(shot_list_path(h_root, film, seq, shot), "r") as f:
            return list(json.load(f).get("assets", []))
    except (IOError, OSError, ValueError, AttributeError):
        return None


def write_shot_list(h_root, film, seq, shot, keys):
    """Save the shot's list (manifest keys, in list order) to the H drive."""
    path = shot_list_path(h_root, film, seq, shot)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    if os.path.exists(path):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    try:
        login = pub.who()
    except BuildError:
        login = ""
    with open(path, "w") as f:
        json.dump({"assets": list(keys), "saved_by": login,
                   "saved": datetime.now().isoformat(timespec="seconds")}, f, indent=2)


def texture_folder_of(path):
    """The texture folder that goes with a published file (H drive or
    scratch publish folder): <asset>\\sourceimages\\<login>\\<file name
    without extension> beside <asset>\\scenes\\<login>\\<file> (publishTool_
    textures, 2026-10-20). It may not exist (nothing textured)."""
    login_dir = os.path.dirname(path)
    asset_dir = os.path.dirname(os.path.dirname(login_dir))
    return os.path.join(asset_dir, "sourceimages", os.path.basename(login_dir),
                        os.path.splitext(os.path.basename(path))[0])


# Files published beside a version under the same name: an environment's
# one-frame reference cache (spec §4c). Pulled and cleared with it.
SIDE_FILES = (".abc",)


def side_files(path):
    stem = os.path.splitext(path)[0]
    return [stem + ext for ext in SIDE_FILES if os.path.isfile(stem + ext)]


def version_files(path):
    """A pulled version in the publish folder plus its textures and side
    files: what clearing that version removes (spec "Clearing old
    versions": its textures go with it)."""
    found = [path] + side_files(path)
    for dirpath, _, filenames in os.walk(texture_folder_of(path)):
        found += [os.path.join(dirpath, n) for n in filenames]
    return found


def _copy_if_changed(source, dest):
    if os.path.isfile(dest) and os.path.getsize(dest) == os.path.getsize(source):
        return False
    if not os.path.isdir(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))
    if os.path.isfile(dest):
        os.chmod(dest, stat.S_IWRITE)
    shutil.copy2(source, dest)
    os.chmod(dest, stat.S_IREAD)
    return True


def copy_published(source, maya_dir):
    """Copy one published file from the H drive into the shared publish
    folder under the same path and name, unless an identical copy is
    already there, plus the textures published with it. Read-only, like
    the publish. Returns (dest, copied)."""
    dest = os.path.join(publish_dir(maya_dir), *_maya_rel(source).split("/"))
    textures = texture_folder_of(source)
    for dirpath, _, filenames in os.walk(textures):
        for name in filenames:
            src = os.path.join(dirpath, name)
            _copy_if_changed(src, os.path.join(texture_folder_of(dest),
                                               os.path.relpath(src, textures)))
    for side in side_files(source):
        _copy_if_changed(side, os.path.splitext(dest)[0] + os.path.splitext(side)[1])
    return dest, _copy_if_changed(source, dest)


def pull(shot_dir, published, vid):
    """Make sure one published version (a version id, e.g. 'scout/v003')
    is in the shared publish folder and record that this shot uses it.
    Other shots' versions are untouched. Returns the path in the publish
    folder."""
    if vid not in published["versions"]:
        raise BuildError("%s of %s %s isn't on the H drive."
                         % (vid, published["asset"], published["code"]))
    source = published["versions"][vid]
    maya_dir = maya_dir_of_shot(shot_dir)
    dest, _ = copy_published(source, maya_dir)

    info = published["info"][vid]
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    manifest = read_manifest(shot_dir)
    entry = {
        "version": info["version"],
        "login": info["login"],
        "shared": _maya_rel(source),
        "source": source,
        "pulled": datetime.now().isoformat(timespec="seconds"),
    }
    if published["code"] in LINKED_CODES:
        entry["link"] = link_rel_path(published["asset_type"], published["asset"],
                                      published["code"], os.path.splitext(dest)[1])
        entry["hardlink"] = link_version(dest, entry_path(shot_dir, entry), maya_dir)
    manifest[key] = entry
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


def any_version_references(shot_dir, published):
    """Reference nodes pointing at any version of this asset + department
    in the shot's publish folder, whatever the manifest says: old-style
    names (backpack_model_v003.ma) as well as personal ones
    (scenes\\<login>\\backpack_scout_model_v005.ma). Catches a scene whose
    reference the manifest no longer remembers, e.g. another scene in the
    same shot, or one saved before personal publishes."""
    folder = os.path.normcase(os.path.join(
        publish_dir(maya_dir_of_shot(shot_dir)), "assets",
        published["asset_type"], published["asset"], "scenes"))
    name = re.compile(r"^%s_(?:[^_]+_)?%s_v\d{3}\.(ma|mb)$"
                      % (re.escape(published["asset"]), re.escape(published["code"])),
                      re.IGNORECASE)
    found = []
    for node, _, full, resolved in scene_references():
        for path in (resolved, full):
            path = os.path.normcase(os.path.normpath(path or ""))
            if path.startswith(folder + os.sep) and name.match(os.path.basename(path)):
                found.append(node)
                break
    return found


def scene_version(shot_dir, published):
    """What the open scene has of this asset + department: its version id,
    '' if it's there at a version that can't be told (old names, old camera
    stamps), or None if it isn't in the scene. Build Shot leaves anything
    already in the scene alone unless the student picks another version
    (user, 2026-10-20: adding an asset must not rebuild the others)."""
    if published.get("kind") == "camera":
        node, vid = shot_camera()
        return (vid or "") if node else None
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    entry = read_manifest(shot_dir).get(key)
    if entry and referenced_nodes(entry_path(shot_dir, entry)):
        return entry_version_id(entry)
    for node in any_version_references(shot_dir, published):
        m = PUBLISHED_RE.match(os.path.basename(_absolute(written_path(node))))
        return version_id(m.group("login").lower(), int(m.group("version"))) if m else ""
    if any(referenced_nodes(p) for p in _old_paths(shot_dir, published, entry)):
        return ""
    return None


# Files from a newer Maya (the move to 2027, 2026-10-28): Maya opens older
# scenes, not reliably newer ones, so while some machines are on 2025 and
# some on 2027 Build says when a publish was saved in a newer Maya. Read
# from the "requires maya" line every .ma carries, so it works for
# publishes made before this check.

_REQUIRES_MAYA = re.compile(r'^requires maya "(\d{4})')


def saved_in_maya(path):
    """The Maya version (e.g. 2027) a .ma was saved in, or None."""
    if not path.lower().endswith(".ma") or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", errors="replace") as f:
            for i, line in enumerate(f):
                m = _REQUIRES_MAYA.match(line)
                if m:
                    return int(m.group(1))
                if i > 500 or line.startswith("createNode"):
                    break
    except (IOError, OSError):
        pass
    return None


def newer_maya_warning(path):
    """A warning if path was saved in a newer Maya than this one, else None."""
    made = saved_in_maya(path)
    this = int(cmds.about(majorVersion=True))
    if made and made > this:
        return ("published from Maya %d, newer than this Maya (%d): it may not load "
                "correctly here. Open this in Maya %d, or ask for it to be published "
                "from Maya %d." % (made, this, made, this))
    return None


def build_asset(shot_dir, published, vid):
    """Build one asset (see _build_asset), then point any MetaHuman DNA
    nodes it brought at their files on this drive (pipeEnv.fix_dna_paths:
    DNA nodes can't read $PIPE_SCRATCH)."""
    done, warning, replaced = _build_asset(shot_dir, published, vid)
    if published.get("kind") != "camera":
        fixed = pipeEnv.fix_dna_paths()
        if fixed:
            if done == ["already up to date"]:
                done = []
            done.append("MetaHuman DNA pointed at this drive (%d)" % len(fixed))
    return done, warning, replaced


def _build_asset(shot_dir, published, vid):
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
    previous = shared_path(shot_dir, entry) if entry else None
    linked = published["code"] in LINKED_CODES
    label = version_label(published, vid, mark_latest=False)
    done = []
    # Leftover unassigned shaders holding the asset's name (e.g. from an
    # old import whose geometry was deleted) are cleared, not a clash.
    cleared = pub.unused_shading_nodes(namespace)
    if cleared:
        cmds.delete(cleared)
        done.append("removed unused shader leftovers %s" % ", ".join(cleared))

    same = bool(entry) and entry_version_id(entry) == vid
    restored = bool(same and entry.get("shared") and not os.path.isfile(previous))
    relinked = bool(same and not restored and link_state(shot_dir, entry) in (MISSING, STALE))
    dest = pull(shot_dir, published, vid)
    if not entry:
        done.append("pulled %s" % label)
    elif not same:
        done.append("%s -> %s" % (version_label(published, entry_version_id(entry), False)
                                  if entry_version_id(entry) in published["info"]
                                  else "v%03d" % entry["version"], label))
    elif restored:
        done.append("%s pulled again (it was missing)" % label)
    elif relinked:
        done.append("%s relinked in this shot (it was missing or out of date)" % label)
    replaced = previous if previous and not pub._same_path(previous, dest) else None

    # What the shot's scenes reference: the fixed name in the shot for rigs,
    # the version in the publish folder for everything else.
    new_entry = read_manifest(shot_dir)[key]
    target = entry_path(shot_dir, new_entry)
    warning = newer_maya_warning(dest)
    if linked and not new_entry.get("hardlink"):
        warning = " ".join(w for w in (warning, "this drive can't hardlink, so the rig is a "
                                       "full copy in this shot (works the same, uses more disk).")
                           if w)

    # References are written with $PIPE_SCRATCH so the shot opens from any
    # drive (spec "Reference paths that work on any drive"). Point the
    # variable at this shot's drive first.
    pipeEnv.set_from_path(shot_dir)
    ref_path = pipeEnv.to_var_path(target)

    nodes = referenced_nodes(target)
    if nodes:
        old_ns = use_clean_namespace(target, namespace)
        if old_ns:
            done.append("renamed %s: to %s:" % (old_ns, namespace))
        rewritten = False
        for node in nodes:
            if not pipeEnv.uses_var(written_path(node)) and pipeEnv.uses_var(ref_path):
                repoint_reference(node, ref_path)   # full D:\... path -> $PIPE_SCRATCH
                rewritten = True
        if rewritten:
            done.append("reference path made drive-independent")
        elif restored or relinked or (linked and not same):
            # Same path, new content: a reload is all a rig update needs.
            reload_references_to(target)
            done.append("reloaded in scene")
        if not done:
            done.append("already up to date")
        return done, warning, replaced

    for path in _old_paths(shot_dir, published, entry):
        nodes = referenced_nodes(path)
        if nodes:
            for node in nodes:
                repoint_reference(node, ref_path)
            use_clean_namespace(target, namespace)
            done.append("scene reference switched to %s" % label)
            return done, warning, replaced

    # Any other version of this asset already referenced (for rigs: a scene
    # from before the fixed name): switch it rather than referencing the
    # asset a second time.
    nodes = any_version_references(shot_dir, published)
    if nodes:
        for node in nodes:
            repoint_reference(node, ref_path)
        use_clean_namespace(target, namespace)
        done.append("scene reference switched to %s" % label)
        return done, warning, replaced

    reference_into_scene(ref_path, namespace)
    done.append("referenced into scene")
    return done, warning, replaced


def other_shots_using(shot_dir, published, vid):
    """Shot folders on the same scratch film, other than shot_dir, that have
    this linked asset + department on a version other than vid."""
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    film_dir = os.path.dirname(maya_dir_of_shot(shot_dir))
    found = []
    for seq, shot in list_shots(os.path.dirname(film_dir), os.path.basename(film_dir)):
        other = os.path.join(film_dir, "maya", "sequences", seq, shot)
        if pub._same_path(other, shot_dir):
            continue
        entry = read_manifest(other).get(key)
        if entry and entry.get("link") and entry_version_id(entry) != vid:
            found.append(other)
    return found


def update_shots(shot_dirs, published, vid):
    """Relink a rig in shots that aren't open (spec §4a: every shot follows
    an update by default). Their scenes load the new version the next time
    they're opened, since the path they reference doesn't change.
    Returns (updated shot names, replaced version paths)."""
    updated, replaced = [], []
    for shot_dir in shot_dirs:
        key = manifest_key(published["asset_type"], published["asset"], published["code"])
        entry = read_manifest(shot_dir).get(key)
        dest = pull(shot_dir, published, vid)
        updated.append(os.path.basename(shot_dir))
        if entry and not pub._same_path(shared_path(shot_dir, entry), dest):
            replaced.append(shared_path(shot_dir, entry))
    return updated, replaced


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
                    path = os.path.normcase(os.path.normpath(shared_path(shot_dir, entry)))
                    used.setdefault(path, []).append(shot)
    return used


def unused_versions(paths, maya_dir):
    """The paths (pulled versions in the publish folder) that no shot's
    manifest uses and the open scene doesn't reference."""
    used = shots_using(maya_dir)
    in_scene = set(os.path.normcase(os.path.normpath(r)) for _, _, _, r in scene_references())
    result, seen = [], set()
    for path in paths:
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue    # replaced by more than one shot
        seen.add(key)
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
        elif _linked_entry(root, rel, path):
            # A rig's fixed name in the shot: the manifest says which version.
            entry = _linked_entry(root, rel, path)
            source = os.path.join(h_root, rel[0], "maya", *entry["shared"].split("/"))
            if not os.path.isfile(source):
                not_fixed.append("%s: v%03d isn't on the H drive (%s)."
                                 % (name, entry["version"], source))
                continue
            maya_dir = os.path.join(root, rel[0], "maya")
            dest, _ = copy_published(source, maya_dir)
            link_version(dest, path, maya_dir)
            cmds.file(written if pipeEnv.uses_var(written) else path, loadReference=node)
            fixed.append("%s: relinked to v%03d (%s) and loaded."
                         % (name, entry["version"], entry.get("login", "?")))
        elif len(rel) > 5 and rel[1] == "maya" and rel[2] == "sequences" and rel[5] == "assets":
            not_fixed.append("%s: an old copy kept inside the shot. Add %s in Build Shot "
                             "and build to switch it to a published version."
                             % (name, rel[7] if len(rel) > 8 else os.path.splitext(name)[0]))
        else:
            not_fixed.append("%s: missing, and not a pulled publish (%s)." % (name, path))
    fixed += _repair_textures(h_root)
    fixed += ["%s: MetaHuman DNA pointed at %s" % (node, os.path.basename(path))
              for node, path in pipeEnv.fix_dna_paths()]
    return fixed, not_fixed


def _repair_textures(h_root):
    """Pulled publishes the open scene references whose textures are
    missing on scratch (e.g. after a wipe, when a rig's link in the shot
    still had its data): pull them again. Returns messages."""
    fixed = []
    for node, written, full, resolved in scene_references():
        path = resolved if os.path.isfile(resolved) else full
        if not os.path.isfile(path):
            continue
        try:
            root, rel = pub.find_film_folder(path)
        except BuildError:
            continue
        maya_dir = os.path.join(root, rel[0], "maya")
        entry = _linked_entry(root, rel, path)
        if entry:
            local = os.path.join(publish_dir(maya_dir), *entry["shared"].split("/"))
            source = os.path.join(h_root, rel[0], "maya", *entry["shared"].split("/"))
        elif len(rel) > 3 and rel[1] == "maya" and rel[2] == PUBLISH_FOLDER:
            local, source = path, os.path.join(h_root, rel[0], "maya", *rel[3:])
        else:
            continue
        on_h, here = texture_folder_of(source), texture_folder_of(local)
        wanted = [os.path.relpath(os.path.join(d, n), on_h)
                  for d, _, names in os.walk(on_h) for n in names]
        if not os.path.isfile(source) or all(os.path.isfile(os.path.join(here, w))
                                             for w in wanted):
            continue
        copy_published(source, maya_dir)
        if entry:
            link_version(local, path, maya_dir)
        fixed.append("%s: textures pulled again from the H drive." % os.path.basename(path))
    return fixed


def _linked_entry(root, rel, path):
    """The shot's manifest entry whose fixed name is path, or None."""
    if not (len(rel) > 5 and rel[1] == "maya" and rel[2] == "sequences" and rel[5] == "assets"):
        return None
    shot_dir = os.path.join(root, *rel[:5])
    for entry in read_manifest(shot_dir).values():
        if entry.get("link") and pub._same_path(entry_path(shot_dir, entry), path):
            return entry
    return None


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


def _is_camera_group(node):
    """A published <shot>_cam_GRP: its pipe stamp says department cam."""
    return (cmds.attributeQuery(DEPT_STAMP, node=node, exists=True)
            and cmds.getAttr("%s.%s" % (node, DEPT_STAMP)) == CAMERA_CODE)


def shot_camera():
    """The built shot camera in the open scene: (camera1 transform, version
    id) or (None, None). It's camera1 inside a top-level camera group; the
    group's stamp says who published which version. A camera from before
    the group (a top-level camera1) doesn't count, so a rebuild replaces it."""
    for group in cmds.ls(assemblies=True, long=True) or []:
        camera = "%s|%s" % (group, CAMERA_NAME)
        if _is_camera_group(group) and cmds.objExists(camera):
            return camera, version_id(cmds.getAttr("%s.%s" % (group, BY_STAMP)),
                                      cmds.getAttr("%s.%s" % (group, VERSION_STAMP)))
    return None, None


def _camera_data(transform):
    """The data node(s) driving the camera (camera1_DATA)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    return sorted(set(n for n in cmds.listConnections([transform] + shape, source=True,
                                                      destination=False, type="transform") or []
                      if n.split("|")[-1].endswith("_DATA")))


def _camera_curves(transform):
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera") or []
    curves = set()
    for node in [transform] + shape + _camera_data(transform):
        curves.update(cmds.listConnections(node, source=True, destination=False,
                                           type="animCurve") or [])
    return sorted(curves)


def set_camera_locked(transform, locked):
    """Lock (or unlock) the camera so its keys can't be edited by accident:
    the channels of the camera, its data node and group, the curves' key
    data (so the Graph Editor can't move keys either) and the curve nodes
    themselves (so they can't be deleted)."""
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    curves = _camera_curves(transform)
    group = (cmds.listRelatives(transform, parent=True, fullPath=True) or [None])[0]
    nodes = [transform, shape] + _camera_data(transform)
    if group and _is_camera_group(group):
        nodes.append(group)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    for node in nodes:
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


def _free_name(name):
    """name, or name1, name2, ... whichever no node in the scene uses. Maya
    allows the same short name under different parents (e.g. inside a
    camera group), but then names stop being unique."""
    candidate, i = name, 1
    while cmds.objExists(candidate):
        candidate, i = "%s%d" % (name, i), i + 1
    return candidate


def _move_out_of_the_way(node):
    """Rename an existing camera1 (and its shape, data node, camera group
    and our curves) to camera1_old, camera1_old1, ... Nothing is deleted.
    Returns the new name."""
    curves = _camera_curves(node)
    data = _camera_data(node)
    group = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    new = cmds.rename(node, _free_name(OLD_CAMERA_NAME))
    for shape in cmds.listRelatives(new, shapes=True, fullPath=True) or []:
        cmds.rename(shape, new.split("|")[-1] + "Shape")
    for d in data:
        cmds.rename(d, new.split("|")[-1] + "_DATA")
    if group and _is_camera_group(group):
        cmds.rename(group, _free_name(group.split("|")[-1] + "_old"))
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
    """Import the pulled camera group live (<shot>_cam_GRP > camera1 +
    camera1_DATA), connect its keys to the data node and lock it. The
    camera is driven 1:1 by the data node, so it behaves like a referenced
    camera with no reference path (user, 2026-10-20). The group's pipe
    stamp says which version it is. Returns camera1's transform."""
    cam_path = os.path.join(shot_dir, *CAMERA_FILES["camera"].split("/"))
    keys_path = os.path.join(shot_dir, *CAMERA_FILES["keys"].split("/"))
    with open(os.path.join(shot_dir, *CAMERA_FILES["map"].split("/")), "r") as f:
        mapping = json.load(f)
    if mapping.get("format") != CAMERA_MAP_FORMAT:
        raise BuildError("This camera was published before cameras had a group. "
                         "Republish it from the layout scene.")
    group_name = mapping["group"]
    if cmds.objExists("|" + group_name):    # not our camera group, or one with no camera1
        cmds.rename("|" + group_name, _free_name(group_name + "_old"))

    ns, nodes = _import_into_root(cam_path, "buildCam")
    missing = [n for n in (group_name, mapping["camera"], mapping["data"]) if n not in nodes]
    if missing:
        raise BuildError("The camera file is missing %s: %s" % (", ".join(missing), cam_path))
    cmds.rename(nodes[mapping["data"]], ":" + DATA_NAME)
    transform = cmds.rename(nodes[mapping["camera"]], ":" + CAMERA_NAME)
    shape = cmds.listRelatives(transform, shapes=True, fullPath=True, type="camera")[0]
    cmds.rename(shape, ":" + CAMERA_NAME.replace("camera", "cameraShape"))
    group = cmds.rename(cmds.listRelatives(transform, parent=True, fullPath=True)[0],
                        ":" + group_name)
    _drop_namespace(ns)
    group = cmds.ls(group, long=True)[0]
    transform = "%s|%s" % (group, CAMERA_NAME)
    data = "%s|%s" % (group, DATA_NAME)

    ns, curves = _import_into_root(keys_path, "buildCamKeys")
    for curve, attr in mapping["curves"].items():
        if curve not in curves:
            raise BuildError("The keys file is missing curve %s." % curve)
        cmds.setAttr("%s.%s" % (data, attr), lock=False)
        cmds.connectAttr(curves[curve] + ".output", "%s.%s" % (data, attr), force=True)
        cmds.rename(curves[curve], ":%s_%s" % (DATA_NAME, attr))
    _drop_namespace(ns)
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
        done += apply_camera_range(shot_dir)
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
    # Any existing camera1 (an older build in its group, one from before
    # camera groups, or the student's own) is kept, renamed out of the way.
    for node in cmds.ls(CAMERA_NAME, long=True, type="transform") or []:
        done.append("existing camera1 renamed %s" % _move_out_of_the_way(node))
    info = published["info"][vid]
    import_camera(shot_dir, info["version"], info["login"])
    done.append("camera1 %s imported and locked" % label)
    done += apply_camera_range(shot_dir)
    return done, None


def apply_camera_range(shot_dir):
    """The shot's frame range is the one its camera was published with
    (the map's start/end): set the playback and animation range to it
    (user, 2026-10-26: SEQ010_160 built without its range). Returns what
    was done, as lines."""
    try:
        with open(os.path.join(shot_dir, *CAMERA_FILES["map"].split("/")), "r") as f:
            mapping = json.load(f)
        start, end = int(mapping["start"]), int(mapping["end"])
    except (IOError, OSError, ValueError, KeyError, TypeError):
        return []
    current = (cmds.playbackOptions(query=True, minTime=True),
               cmds.playbackOptions(query=True, maxTime=True),
               cmds.playbackOptions(query=True, animationStartTime=True),
               cmds.playbackOptions(query=True, animationEndTime=True))
    if current == (start, end, start, end):
        return []
    cmds.playbackOptions(minTime=start, maxTime=end,
                         animationStartTime=start, animationEndTime=end)
    return ["frame range set to %d-%d, from the camera publish" % (start, end)]


# ---------------------------------------------------------------------------
# Shot keys (spec §4 item 7 "Build Shot pulling animation back in", DECIDED
# 2026-10-23): a Layout or Animation publish writes each item's keys (a .ma
# of curves + a .json map) to the shot's scenes\<login>\ on the H drive.
# Build puts an asset's keys back on that same asset (Scout's keys on Scout
# only), from the Keys column on its row. Layout and anim keys are one list,
# newest by publish time; the rig version is picked separately, and keys
# made on another rig version go on anyway, with what didn't match listed.
# ---------------------------------------------------------------------------

KEY_CODES = ("layout", "anim")
KEYS_RE = re.compile(r"_(?P<code>layout|anim)_v(?P<version>\d{3})\.json$", re.IGNORECASE)
TIME_CURVES = ("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT")
KEYS_RECORD = "pipe_keys"       # fileInfo: which keys Build put on each asset
KEEP_KEYS = "keep"              # leave the scene's keys alone (e.g. keyed by hand)
NO_KEYS = "none"                # no keys: the asset at its default pose


def keys_id(shot, login, code, version):
    return "%s/%s/%s/v%03d" % (shot, login, code, version)


def parse_keys_id(kid):
    """(shot, login, code, version) from a keys id."""
    shot, login, code, version = kid.split("/")
    return shot, login, code, int(version[1:])


def list_shot_keys(h_root, film, seq, shot):
    """{asset's manifest key: {keys id: info}} for every asset keys publish
    in the shot on the H drive, everyone's. info: {shot, login, code,
    version, time, keys, map, made_on}, made_on being the asset version the
    keys were published from ({version, artistId}). Items made in the shot
    (no pipe stamp) and the camera are left out."""
    scenes = os.path.join(shot_folder(h_root, film, seq, shot), "scenes")
    found = {}
    for dirpath, filenames in _walk_shot_publishes(scenes):
        login = os.path.basename(dirpath).lower()
        for name in filenames:
            m = KEYS_RE.search(name)
            if not m or not name.lower().startswith(("%s_%s_" % (shot, login)).lower()):
                continue
            path = os.path.join(dirpath, name)
            keys = path[:-len(".json")] + ".ma"
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (IOError, OSError, ValueError):
                continue
            asset = data.get("asset") or {}
            # Keys, or only unkeyed settings (an asset placed, never keyed).
            if not (((os.path.isfile(keys) and data.get("curves")) or data.get("settings"))
                    and asset.get("asset") and asset.get("assetType")
                    and asset.get("department")):
                continue
            code, version = m.group("code").lower(), int(m.group("version"))
            key = manifest_key(asset["assetType"], asset["asset"], asset["department"])
            found.setdefault(key, {})[keys_id(shot, login, code, version)] = {
                "shot": shot, "login": login, "code": code, "version": version,
                "time": publish_time(path), "keys": keys, "map": path,
                "made_on": {"version": asset.get("version"),
                            "artistId": asset.get("artistId")}}
    return found


def keys_label(kid, info=None, this_shot=None, latest=None):
    """'v005 anim (scout)', plus the shot when it isn't this one and
    '  (latest)' for the newest."""
    if kid == KEEP_KEYS:
        return "Keep scene's keys"
    if kid == NO_KEYS:
        return "None (no keys)"
    shot, login, code, version = parse_keys_id(kid)
    text = "v%03d %s (%s)" % (version, code, login)
    if this_shot and shot.lower() != this_shot.lower():
        text += "  from %s" % shot
    if latest and kid == latest:
        text += "  (latest)"
    return text


def sorted_keys(keys):
    """Keys ids of {kid: info}, newest publish first."""
    return sorted(keys, key=lambda k: keys[k]["time"], reverse=True)


def keys_record():
    """{asset's manifest key: keys id} that Build put on each asset in the
    open scene (saved with the scene)."""
    raw = cmds.fileInfo(KEYS_RECORD, query=True) or []
    record = {}
    for pair in (raw[0] if raw else "").split("|"):
        if "=" in pair:
            key, kid = pair.split("=", 1)
            record[key] = kid
    return record


def _set_keys_record(key, kid):
    record = keys_record()
    record[key] = kid
    cmds.fileInfo(KEYS_RECORD, "|".join("%s=%s" % kv for kv in sorted(record.items())))


def keys_in_scene(published):
    """The keys id Build last put on this asset in the open scene (or
    NO_KEYS), or None if Build hasn't put keys on it."""
    return keys_record().get(manifest_key(published["asset_type"], published["asset"],
                                          published["code"]))


def asset_namespace(shot_dir, published):
    """The namespace the asset is referenced under in the open scene, or
    None if it isn't there."""
    entry = read_manifest(shot_dir).get(manifest_key(
        published["asset_type"], published["asset"], published["code"]))
    nodes = referenced_nodes(entry_path(shot_dir, entry)) if entry else []
    nodes = nodes or any_version_references(shot_dir, published)
    if nodes:
        return cmds.referenceQuery(nodes[0], namespace=True).lstrip(":")
    namespace = namespace_for(published["asset"], published["code"])
    return namespace if cmds.namespace(exists=":" + namespace) else None


def _namespace_nodes(namespace):
    """{short name without namespaces: node} for everything in the
    namespace, nested namespaces included (the keys map keeps short names)."""
    nodes = cmds.namespaceInfo(":" + namespace, listOnlyDependencyNodes=True,
                               recurse=True, dagPath=True) or []
    found = {}
    for node in nodes:
        found.setdefault(node.split("|")[-1].split(":")[-1], node)
    return found


def _keys_on(namespace):
    """The animator's keys on the asset: time curves feeding its nodes
    straight in, not from the referenced file (driven keys belong to the rig)."""
    curves = set()
    for node in _namespace_nodes(namespace).values():
        for curve in cmds.listConnections(node, source=True, destination=False,
                                          type="animCurve") or []:
            if (cmds.nodeType(curve) in TIME_CURVES
                    and not cmds.referenceQuery(curve, isNodeReferenced=True)):
                curves.add(curve)
    return sorted(curves)


def clear_keys(namespace):
    """Delete the asset's keys. Returns how many curves went."""
    curves = _keys_on(namespace)
    for curve in curves:
        cmds.lockNode(curve, lock=False)
    if curves:
        cmds.delete(curves)
    return len(curves)


def apply_settings(targets, settings):
    """Set the published unkeyed settings ({node name: {attr: value}}) on
    the asset's nodes ({name: node}). A setting whose control or channel
    isn't on this rig, or can't be set (locked, driven, keyed), is left out.
    Returns (settings applied, [what didn't match])."""
    applied, unmatched = 0, []
    for node_name, attrs in sorted(settings.items()):
        node = targets.get(node_name)
        if not node:
            unmatched.append("%s (%d settings)" % (node_name, len(attrs)))
            continue
        for attr, value in sorted(attrs.items()):
            plug = "%s.%s" % (node, attr)
            try:
                if (cmds.connectionInfo(plug, isDestination=True)
                        or not cmds.getAttr(plug, settable=True)):
                    unmatched.append("%s.%s (locked or driven)" % (node_name, attr))
                    continue
                cmds.setAttr(plug, value)
            except (RuntimeError, ValueError, TypeError):
                unmatched.append("%s.%s" % (node_name, attr))
                continue
            applied += 1
    return applied, unmatched


def apply_keys(namespace, info):
    """Replace the asset's keys with a published set: import its curves,
    delete the keys already on the asset, then connect each curve to the
    same control and channel by name, on the frames it was published on,
    and set its unkeyed settings. Curves whose control or channel isn't on
    this rig (or is locked) are left out. Returns (curves applied,
    settings applied, [controls that didn't match])."""
    with open(info["map"], "r") as f:
        data = json.load(f)
    mapping = data.get("curves") or {}
    ns, curves = (_import_into_root(info["keys"], "buildKeys") if mapping
                  else (None, {}))
    applied, unmatched = 0, []
    try:
        clear_keys(namespace)
        targets = _namespace_nodes(namespace)
        for curve, (node_name, attr) in sorted(mapping.items()):
            new = curves.get(curve)
            if not new:
                unmatched.append("%s.%s (missing from the keys file)" % (node_name, attr))
                continue
            node = targets.get(node_name)
            plug = "%s.%s" % (node, attr)
            if not node or not cmds.attributeQuery(attr.split("[")[0], node=node, exists=True):
                unmatched.append("%s.%s" % (node_name, attr))
                cmds.delete(new)
                continue
            if cmds.getAttr(plug, lock=True):
                unmatched.append("%s.%s (locked)" % (node_name, attr))
                cmds.delete(new)
                continue
            cmds.connectAttr(new + ".output", plug, force=True)
            cmds.rename(new, ":%s_%s_%s" % (namespace.replace(":", "_"), node_name, attr))
            applied += 1
        set_count, set_unmatched = apply_settings(targets, data.get("settings") or {})
        unmatched += set_unmatched
    finally:
        if ns:
            _drop_namespace(ns)
    return applied, set_count, unmatched


def build_keys(shot_dir, published, kid, info=None):
    """Put the chosen keys on an asset that's in the open scene: kid a keys
    id (info from list_shot_keys) or NO_KEYS. Whatever keys the asset had
    are replaced (user, 2026-10-23). Returns (done, warning or None)."""
    namespace = asset_namespace(shot_dir, published)
    if not namespace:
        raise BuildError("%s isn't in this scene, so its keys have nowhere to go."
                         % published["asset"])
    key = manifest_key(published["asset_type"], published["asset"], published["code"])
    if kid == NO_KEYS:
        removed = clear_keys(namespace)
        _set_keys_record(key, NO_KEYS)
        return ["keys removed (%d curves)" % removed], None
    label = keys_label(kid, info, this_shot=os.path.basename(os.path.normpath(shot_dir)))
    applied, settings, unmatched = apply_keys(namespace, info)
    _set_keys_record(key, kid)
    done = ["keys %s on (%d curves%s)" % (
        label, applied, ", %d unkeyed settings" % settings if settings else "")]
    warning = None
    if unmatched:
        made_on = info.get("made_on") or {}
        entry = read_manifest(shot_dir).get(key)
        note = ""
        if entry and made_on.get("version") and (
                made_on.get("version"), (made_on.get("artistId") or "").lower()) != (
                entry["version"], (entry.get("login") or "").lower()):
            note = " (keys made on v%03d (%s), this shot has v%03d (%s))" % (
                made_on["version"], made_on.get("artistId") or "?",
                entry["version"], entry.get("login") or "?")
        shown = unmatched[:8] + (["..."] if len(unmatched) > 8 else [])
        warning = ("keys put on anyway, but %d didn't match this rig%s: %s"
                   % (len(unmatched), note, ", ".join(shown)))
    return done, warning


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


# ---------------------------------------------------------------------------
# Asset development: a published asset pulled into an asset scene is
# imported, never referenced; referencing is for building shots (user,
# 2026-10-28). It arrives as published (its stamped pipe group, no
# namespace) and its textures and DNA become this asset's own, copied into
# its sourceimages.
# ---------------------------------------------------------------------------

def asset_of_scene(scene_path, scratch_root):
    """(film, asset_type, asset) if the scene is inside an asset on scratch, else None."""
    try:
        root, rel = pub.find_film_folder(scene_path)
    except BuildError:
        return None
    if (not pub._same_path(root, scratch_root) or len(rel) < 5
            or rel[1] != "maya" or rel[2] != "assets"):
        return None
    return rel[0], rel[3], rel[4]


def asset_folder(root, film, asset_type, asset):
    return os.path.join(root, film, "maya", "assets", asset_type, asset)


def _stamp(node, name):
    plug = "%s.%s" % (node, name)
    return cmds.getAttr(plug) if cmds.objExists(plug) else None


def imported_versions(published):
    """Version ids of this asset + department already in the open scene,
    read from the stamps on their pipe groups (pipe_asset etc.)."""
    found = []
    for node in cmds.ls("*.pipe_asset", objectsOnly=True, recursive=True) or []:
        if ((_stamp(node, "pipe_asset") or "").lower() != published["asset"].lower()
                or _stamp(node, "pipe_department") != published["code"]):
            continue
        version = _stamp(node, "pipe_version")
        found.append(version_id(_stamp(node, "pipe_artistId"), int(version))
                     if version is not None else "")
    return found


def _set_string(plug, value):
    locked = cmds.getAttr(plug, lock=True)
    if locked:
        cmds.setAttr(plug, lock=False)
    cmds.setAttr(plug, value, type="string")
    if locked:
        cmds.setAttr(plug, lock=True)


def _own_files(nodes, pulled, asset_dir):
    """Copy the pulled version's texture folder (textures, DNA) into
    <asset>\\sourceimages\\<published file name>\\ and point the imported
    nodes at the copies: texture and image-plane nodes, and each rig
    group's pipe_dna list (so the DNA nodes follow it when the scene
    opens, pipeEnv.fix_dna_paths). Returns the number of nodes repointed."""
    import publishTool_textures as tex
    folder = texture_folder_of(pulled)
    if not os.path.isdir(folder):
        return 0
    own = os.path.join(asset_dir, tex.FOLDER, os.path.basename(folder))
    for dirpath, _, filenames in os.walk(folder):
        for name in filenames:
            dest = os.path.join(own, os.path.relpath(os.path.join(dirpath, name), folder))
            if not os.path.isfile(dest):
                if not os.path.isdir(os.path.dirname(dest)):
                    os.makedirs(os.path.dirname(dest))
                shutil.copyfile(os.path.join(dirpath, name), dest)     # writable: the asset's own
    key = os.path.normcase(os.path.normpath(folder)) + os.sep

    def owned(path):
        """The copy in this asset for a path inside the pulled folder, else None."""
        full = os.path.normcase(os.path.normpath(os.path.expandvars(path or "")))
        if not full.startswith(key):
            return None
        return os.path.join(own, os.path.normpath(os.path.expandvars(path))[len(key):]
                            ).replace("\\", "/")

    repointed = 0
    attrs = dict(tex.TEXTURE_NODES, **tex.IMAGE_PLANES)
    for node in set(cmds.ls(nodes, long=True) or []):
        attr = attrs.get(cmds.nodeType(node))
        if attr:
            path = owned(cmds.getAttr("%s.%s" % (node, attr)))
            if path:
                _set_string("%s.%s" % (node, attr), path)
                repointed += 1
        dna = _stamp(node, pipeEnv.DNA_STAMP)
        if dna:
            entries = json.loads(dna)
            for entry in entries:
                path = owned(entry.get("published"))
                if path:
                    entry["published"] = path
                    repointed += 1
            _set_string("%s.%s" % (node, pipeEnv.DNA_STAMP), json.dumps(entries))
    return repointed


def import_into_asset(asset_dir, published, vid):
    """Pull one published version into the scratch publish folder and
    import it into the open asset scene: no reference, no namespace, its
    pipe group and stamps as published, its textures and DNA copied into
    this asset. Returns the list of what was done."""
    if published.get("kind") == "camera":
        raise BuildError("A shot's camera only builds into its shot.")
    if vid not in published["versions"]:
        raise BuildError("%s of %s %s isn't on the H drive."
                         % (vid, published["asset"], published["code"]))
    maya_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(asset_dir))))
    pulled, _ = copy_published(published["versions"][vid], maya_dir)
    # The published file's $PIPE_SCRATCH paths, on this drive.
    pipeEnv.set_from_path(asset_dir)
    nodes = cmds.file(pulled, i=True, defaultNamespace=True, preserveReferences=False,
                      returnNewNodes=True) or []
    done = ["imported %s" % version_label(published, vid, mark_latest=False)]
    if _own_files(nodes, pulled, asset_dir):
        done.append("textures copied into this asset's sourceimages")
    if pipeEnv.fix_dna_paths():
        done.append("MetaHuman DNA pointed at this asset's copy")
    newer = newer_maya_warning(pulled)
    if newer:
        done.append(newer)
    return done


def set_maya_project(shot_dir):
    pub.set_maya_project(shot_dir)


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
                     for rel in ([e["file"]] if "file" in e else [])
                     + ([e["link"]] if "link" in e else []) + e.get("extra_files", []))
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
    # A rig's hardlink shares its read-only flag with the version in the
    # publish folder, so lock that folder again afterwards.
    relock = set()
    for p in paths:
        try:
            if os.stat(p).st_nlink > 1:
                root, rel = pub.find_film_folder(p)
                relock.add(os.path.join(root, rel[0], "maya"))
        except (OSError, BuildError):
            pass
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
    for maya_dir in relock:
        _lock_publish_folder(maya_dir)
    return result == 0 and not op.fAnyOperationsAborted


def format_size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
        n /= 1024.0
